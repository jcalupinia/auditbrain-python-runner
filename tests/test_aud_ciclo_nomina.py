"""Fase 4 — herramienta bespoke de nómina en el Command Center: panel propio + endpoints.

La cara es el panel (``assets/nomina_panel.tmpl.html``) con el encargo de la ficha inyectado;
el motor son los generadores Python (``nomina_beneficios.correr_prueba`` → 15 cédulas), que se
piden por endpoints bespoke. El flujo genérico de ``libro`` NO aplica a esta herramienta.

La paridad al centavo del motor y las 15 cédulas en LibreOffice se verifican aparte (con un
juego de datos ficticio completo, fuera de esta suite). Aquí se prueba el enganche.
"""
import re

import pytest

from tests.test_aud_ciclo_http import FICHA, _h, _staff_con_proyecto
from backend.app.aud.niif.procesadores import nomina_beneficios as nb, nomina_panel_html as np

BASE = "/api/v1/aud/ciclo"


@pytest.fixture(autouse=True)
def _requiere_plataforma(request):
    """Las pruebas HTTP necesitan la plataforma ``/api/v1`` montada. En un contenedor sin
    todas las dependencias, ``app.py`` monta solo el servicio legacy y esas rutas dan 404
    (igual que el e2e del catálogo); ahí se saltan. En CI la plataforma sí está montada."""
    if "client" in request.fixturenames:
        c = request.getfixturevalue("client")
        if c.post("/api/v1/auth/login", data={"username": "x", "password": "y"}).status_code == 404:
            pytest.skip("Plataforma /api/v1 no montada en este entorno (faltan dependencias).")


def _ficha_y_prueba_nomina(client, tok, pid, origen="proc:nomina_beneficios"):
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA).status_code == 200
    r = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": origen})
    assert r.status_code == 201, r.text
    return r.json()


# --- plantilla del panel: sin datos de cliente embebidos (privacidad) --------

# Nombres y cifras del piloto (PROPHAR) que NUNCA deben viajar en los archivos del repo.
# El contenido fijo de la plantilla (PROG/MDL) quedó como placeholder; las ventanas
# Programa/Hallazgos/Vacaciones se alimentan del motor en runtime (fase B2):
#  - Programa (DO-0)   ← prog.json  → PROG.prog / PROG.rq / PROG.norm
#  - Hallazgos (DO-12) ← do12.json  → PROG.h12 / PROG.aj / PROG.efe
#  - Vacaciones (DO-4V)← cédula VAC / kárdex RQ-008 → MDL.vacx / MDL.k08
TERMINOS_PILOTO = ("montesdeoca", "remache", "prophar", "1791859596", "24813",
                   "130720", "albiño", "quitiaquez", "robalino")


def test_plantilla_del_panel_sin_datos_de_cliente():
    import os
    tmpl = open(np._TMPL, encoding="utf-8").read()
    assert "__NOMINA_ENC__" in tmpl and "__NOMINA_API__" in tmpl
    assert "__NOMINA_MARCA__" in tmpl and "__NOMINA_VISOR__" in tmpl
    # Ningún xlsx embebido (los 5 modelos/cédulas se piden al motor) ni nombres reales.
    assert "data:application/" not in tmpl and "UEsD" not in tmpl
    for real in ("ALBIÑO", "QUITIAQUEZ", "ROBALINO", "1791859596001", "PROPHAR"):
        assert real not in tmpl, real
    # Caza explícita de los nombres/cifras del piloto en PROG/POP07/MDL (regla de privacidad).
    bajo = tmpl.lower()
    for t in TERMINOS_PILOTO:
        assert t not in bajo, t
    assert os.path.getsize(np._TMPL) < 2_000_000


def test_archivos_del_repo_de_nomina_sin_datos_del_piloto():
    """``visor.py``, la plantilla y el render no pueden traer importes ni nombres del piloto."""
    from backend.app.aud.niif.procesadores.nomina import visor as visor_mod
    fuentes = [np._TMPL, np.__file__, visor_mod.__file__]
    for ruta in fuentes:
        bajo = open(ruta, encoding="utf-8").read().lower()
        for t in TERMINOS_PILOTO:
            assert t not in bajo, f"{t} en {ruta}"
    # El HTML renderizado tampoco los expone.
    html = np.render({"client": "Comercial Andina de Ejemplo S.A.", "firm": "AuditConsulting"},
                     1, carpeta_cedulas=None).decode().lower()
    for t in TERMINOS_PILOTO:
        assert t not in html, t


def test_render_inyecta_el_encargo_de_la_ficha():
    eng = {"client": "Comercial Andina de Ejemplo S.A.", "ruc": "1790000000001", "year": 2026,
           "cutoff": "2026-12-31", "visit": "Final", "preparer": "JV", "reviewer": "Socio",
           "framework": "NIIF para las PYMES", "edition": "2015", "activity": "Comercio"}
    html = np.render(eng, 42).decode()
    assert "__NOMINA_" not in html  # no quedan placeholders
    enc = __import__("json").loads(re.search(r"let ENC=(\{.*?\});", html).group(1))
    assert enc["cliente"] == "Comercial Andina de Ejemplo S.A." and enc["ruc"] == "1790000000001"
    assert enc["corte"] == "31/12/2026" and enc["visita"] == "Final" and enc["firma"] == "audit"
    api = __import__("json").loads(re.search(r"const NOMAPI=(\{.*?\});", html).group(1))
    assert api["pruebaId"] == 42 and api["base"] == "/aud/ciclo"


# --- visor del panel: sin procesar vs procesado ------------------------------

def _carpeta_cedulas_ficticias(tmp_path):
    """Una carpeta con dos cédulas ficticias (valores literales, sin fórmulas) que el visor
    puede leer directamente, sin LibreOffice. Datos neutros: nada del piloto."""
    import openpyxl

    for pref, hoja in (("DO-2_Prueba.xlsx", "DO2 Sumaria"), ("DO-3_Prueba.xlsx", "DO3 Planillas")):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = hoja
        ws["A1"] = "Concepto"
        ws["B1"] = "Valor"
        ws["A2"] = "Sueldos"
        ws["B2"] = 1234.56
        ws["A3"] = "Empresa de Ejemplo S.A."
        wb.save(str(tmp_path / pref))
    return str(tmp_path)


def test_render_sin_procesar_no_trae_visor_ni_cifras(tmp_path):
    import re
    html = np.render({"client": "Comercial Andina de Ejemplo S.A.", "firm": "AuditConsulting"},
                     1, carpeta_cedulas=None).decode()
    # El visor va vacío: las tarjetas mostrarán «PENDIENTE DE PROCESAR» (lógica del panel).
    assert re.search(r"const VISOR_GZ=null;", html)
    assert "__NOMINA_" not in html


# --- ventanas propias alimentadas del motor (B2) -----------------------------

# JSON ficticios con la misma forma que escriben mk_pa (prog.json) y mk_do12 (do12.json).
_PROG_FICTICIO = {
    "prog": [
        {"t": "Prueba Alfa", "ref": "DO-0", "aser": "Existencia", "obj": "objetivo alfa",
         "ins": "RQ-002", "crit": "criterio", "res": "Terminada.", "hall": "H-1",
         "est": "Terminada", "pasos": [["1", "paso uno"], ["2", "paso dos"]]},
        {"t": "Prueba Beta", "ref": "DO-2", "aser": "Integridad", "obj": "objetivo beta",
         "ins": "RQ-003", "crit": "criterio", "res": "En ejecución.", "hall": "—",
         "est": "En ejecución", "pasos": [["1", "paso tres"]]},
    ],
    "rq": [["RQ-002", "Anexo", "saldos", "Recibido", "DO-2", "—"]],
    "hall": [[1, "Hallazgo catálogo", "DO-0", "1000.0", "De hecho", "AJ"]],
    "norm": [["Vacaciones", "Código del Trabajo", "15 días", "VAC"]],
    "xlsx": "UEsDBAo=",
}
_DO12_FICTICIO = {
    "hall": [[i + 1, f"Hallazgo {i + 1}", "condición", "criterio", "causa", "efecto",
              1500.0 + i, "Ref. PT", "Ajuste contable" if i == 0 else "Reclasificación",
              "recomendación"] for i in range(14)],
    "aj": [["AJ-1", "5BS.21204.003", "Vacaciones por pagar", 1500.0, None, "H-1"],
           ["RJ-1", "SUE", "Sueldos — administración", 800.0, None, "H-2"]],
    "efe": [["Vacaciones por pagar", 9000.0, -1500.0, 7500.0, "DO-4C"]],
}


def test_construir_prog_llena_las_ventanas_desde_el_motor():
    """Con los JSON del motor, PROG trae el programa (DO-0) y los hallazgos/ajustes (DO-12)."""
    prog = np.construir_prog({"prog": _PROG_FICTICIO, "do12": _DO12_FICTICIO})
    # Programa: pruebas y pasos del motor (prog.json).
    assert len(prog["prog"]) == 2
    assert sum(len(p["pasos"]) for p in prog["prog"]) == 3
    assert prog["rq"] and prog["norm"]
    # Hallazgos: los 14 de DO-12 (do12.hall) con sus ajustes (do12.aj) y efecto (do12.efe).
    assert len(prog["h12"]) == 14
    assert [r[0] for r in prog["aj"]] == ["AJ-1", "RJ-1"]
    assert prog["efe"] and prog["xlsx"] == "UEsDBAo="


def test_construir_prog_vacio_sin_motor():
    """Sin extras (prueba no procesada) → estructura vacía: las ventanas dirán «PENDIENTE»."""
    vacio = np.construir_prog(None)
    assert vacio["prog"] == [] and vacio["h12"] == [] and vacio["aj"] == []
    assert np.construir_prog({})["prog"] == []


def _carpeta_con_vac(tmp_path):
    """Carpeta con una cédula VAC y un kárdex RQ-008 ficticios (valores literales, legibles
    por construir_mdl sin LibreOffice). Datos neutros: nada del piloto."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "VAC Calculadora"
    resumen = [
        "Trabajadores activos al corte (población 100%)",
        "Con kárdex completo", "Sin kárdex (no soportados)",
        "Pasivo exigible según calculadora al corte (a)", "Saldo en libros al corte (b)",
        "Ajuste total propuesto (a) − (b)", "Pasivo correcto al cierre anterior (c)",
        "Saldo en libros al cierre anterior (d)", "Ajuste a resultados acumulados (c) − (d)",
        "Ajuste al gasto del año auditado", "Control",
    ]
    for i, etiqueta in enumerate(resumen):
        ws.cell(9 + i, 1, etiqueta)
        ws.cell(9 + i, 5, 100 + i)
    ws.cell(20, 1, "Estado de la prueba")
    ws.cell(20, 5, "CALCULADO — pasivo y ajuste concluyentes")
    wb.save(str(tmp_path / "VAC_Calculadora_Vacaciones_No_Gozadas.xlsx"))

    kb = openpyxl.Workbook()
    wk = kb.active
    wk.title = "Kárdex RQ-008"
    for i in range(3):
        wk.cell(6 + i, 3, f"170000000{i}")
    kb.save(str(tmp_path / "RQ-008_Kardex_Vacaciones.xlsx"))
    return str(tmp_path)


def test_construir_mdl_vacaciones_desde_la_cedula_del_motor(tmp_path):
    """La ventana de Vacaciones (DO-4V) se alimenta del resumen de la cédula VAC y del kárdex."""
    mdl = np.construir_mdl(_carpeta_con_vac(tmp_path))
    assert "vacx" in mdl and mdl["vacx"]["estado"].startswith("CALCULADO")
    assert mdl["vacx"]["clase"] == "ok"
    assert len(mdl["vacx"]["resumen"]) == 11
    assert mdl["k08"] == {"filas": 3}


def test_construir_mdl_vacio_sin_carpeta():
    assert np.construir_mdl(None) == {}


# --- Nº de trabajadores del motor para el cuestionario DO-1 (punto 1) ---------
#
# THR del panel (nomina_panel.tmpl.html): la aplicabilidad de los ítems del DO-1 por umbral
# depende del Nº de trabajadores. Se replica aquí para comprobar que el número del motor los
# resuelve solos, sin que el auditor lo digite.
THR = {33: lambda n: n >= 25, 36: lambda n: n >= 50, 41: lambda n: n >= 50,
       44: lambda n: 1 <= n <= 10, 45: lambda n: n > 10, 46: lambda n: n >= 10,
       47: lambda n: n >= 10, 48: lambda n: n > 10, 49: lambda n: n > 10}


def test_derivar_nt_desde_la_cedula_vac_del_motor(tmp_path):
    """derivar_nt lee «Trabajadores activos al corte» (E9) de la cédula VAC recalculada."""
    # El fixture pone E9 = 100 en la fila «Trabajadores activos al corte (población 100%)».
    assert np.derivar_nt(_carpeta_con_vac(tmp_path)) == 100


def test_derivar_nt_none_sin_carpeta():
    assert np.derivar_nt(None) is None


def test_render_inyecta_nt_del_motor_y_resuelve_umbrales(tmp_path):
    """Con cédulas procesadas, render inyecta __NOMINA_NT__ con el número del motor (> 0) y ese
    número resuelve solo la aplicabilidad de los ítems por umbral (autoNA/eff del panel)."""
    import re

    carpeta = _carpeta_con_vac(tmp_path)  # E9 = 100 trabajadores activos
    html = np.render({"client": "Empresa de Ejemplo S.A.", "firm": "AuditConsulting",
                      "year": 2026}, 9, carpeta_cedulas=carpeta).decode()
    assert "__NOMINA_NT__" not in html  # placeholder reemplazado
    nt = int(re.search(r"const NT_MOTOR=(\d+);", html).group(1))
    assert nt == 100 and nt > 0
    # Con 100 trabajadores: los umbrales ≥25/≥50/≥10/>10 aplican; el de 1–10 (ítem 44) no.
    assert THR[33](nt) and THR[36](nt) and THR[41](nt)
    assert THR[46](nt) and THR[47](nt) and THR[45](nt) and THR[48](nt) and THR[49](nt)
    assert not THR[44](nt)
    bajo = html.lower()
    for t in TERMINOS_PILOTO:
        assert t not in bajo, t


def test_render_nt_null_sin_procesar():
    """Sin cédulas (prueba no procesada), __NOMINA_NT__ queda en null: el panel se comporta como
    hoy (el auditor digita el número a mano)."""
    import re

    html = np.render({"client": "Empresa de Ejemplo S.A.", "firm": "AuditConsulting"},
                     1, carpeta_cedulas=None).decode()
    assert re.search(r"const NT_MOTOR=null;", html)


def test_panel_trae_deficiencias_ci_do1():
    """DO-1 → carta de control interno: la ventana de Hallazgos trae la pestaña «Deficiencias CI
    (DO-1)» que lista las observaciones del cuestionario (ítems No/Parcial) como deficiencias de
    control, junto a los hallazgos cuantificados del DO-12. Es lógica del panel (no toca el motor)."""
    html = np.render({"client": "Empresa de Ejemplo S.A.", "firm": "AuditConsulting"}, 7).decode()
    assert "Deficiencias CI (DO-1)" in html          # etiqueta de la pestaña
    assert "function pCI(" in html and "function parseObs(" in html
    # El texto de cada deficiencia sale del cuestionario DO-1 (obsText/obsList), no del motor.
    assert "obsList()" in html and "carta de control interno" in html


def test_render_precarga_do1_guardado():
    """render inyecta __NOMINA_DO1__ con el estado guardado del cuestionario (fuente de verdad);
    sin estado queda en null y el panel cae a su borrador local (localStorage)."""
    import json
    import re

    estado = {"nt": 100, "ntManual": True, "ans": {"33": "Sí"}, "obs": {"33": "Tiene reglamento"},
              "step": 2, "done": False}
    html = np.render({"client": "Empresa de Ejemplo S.A.", "firm": "AuditConsulting"},
                     7, do1_estado=estado).decode()
    assert "__NOMINA_DO1__" not in html  # placeholder reemplazado
    saved = json.loads(re.search(r"const DO1_SAVED=(\{.*?\});", html).group(1))
    assert saved == estado
    # Sin estado guardado → null.
    vacio = np.render({"client": "Empresa de Ejemplo S.A.", "firm": "AuditConsulting"}, 7).decode()
    assert re.search(r"const DO1_SAVED=null;", vacio)


def _carpeta_con_rq007(tmp_path, n=12, selecc=4):
    """Carpeta con una cédula RQ-007 ficticia (valores literales, legible sin LibreOffice):
    hoja «Ficha» con los parámetros, «Parámetros» con los totales y «Población» con n filas,
    de las cuales `selecc` quedan marcadas en la muestra (M="Sí"). Datos neutros: nada del piloto."""
    import openpyxl

    wb = openpyxl.Workbook()
    wf = wb.active
    wf.title = "Ficha"
    wf.cell(10, 3, 0.10)   # C10 tamaño de muestra (fracción)
    wf.cell(11, 3, 5)      # C11 partidas clave
    wf.cell(12, 3, 2)      # C12 arranque sistemático

    wq = wb.create_sheet("Parámetros")
    wq.cell(4, 3, 147)     # C4 Población N
    wq.cell(5, 3, 146)     # C5 acumulan también D14
    wq.cell(6, 3, 15)      # C6 tamaño de muestra n
    wq.cell(10, 3, 14.20)  # C10 intervalo

    wp = wb.create_sheet("Población")
    wp.cell(4, 2, "N°"); wp.cell(4, 3, "Cédula"); wp.cell(4, 4, "Nombre")
    wp.cell(4, 5, "D13 acumulado"); wp.cell(4, 6, "D14 acumulado")
    for i in range(n):
        r = 5 + i
        wp.cell(r, 2, i + 1)
        wp.cell(r, 3, f"170000000{i:02d}")
        wp.cell(r, 4, f"Trabajador de Ejemplo {i + 1}")
        wp.cell(r, 5, round(1000.0 + i * 10, 2))        # D13
        wp.cell(r, 6, 0.0 if i % 5 == 0 else 470.0)     # D14 (algunos sin D14)
        wp.cell(r, 10, "Sí" if i < 2 else "No")          # J ¿Clave?
        wp.cell(r, 13, "Sí" if i < selecc else "No")     # M ¿Seleccionado?
    # Fila TOTAL (sin cédula ni importe): no debe contar como población.
    wp.cell(5 + n, 4, "TOTAL")
    wb.save(str(tmp_path / "RQ-007_Muestreo_Solicitudes_Decimos.xlsx"))
    return str(tmp_path)


def test_construir_mdl_muestreo_desde_la_cedula_rq007(tmp_path):
    """La ventana de Muestreo (DO-4 V08) se alimenta de la cédula RQ-007: población, parámetros,
    totales y las filas de la muestra con su marca de selección."""
    mdl = np.construir_mdl(_carpeta_con_rq007(tmp_path, n=12, selecc=4))
    assert "m07" in mdl
    m = mdl["m07"]
    # Población: 12 filas [cédula, nombre, d13, d14] con d13/d14 numéricos (sin la fila TOTAL).
    assert len(m["pob"]) == 12
    assert all(isinstance(row[2], (int, float)) and isinstance(row[3], (int, float)) for row in m["pob"])
    # Parámetros de la Ficha (porcentaje entero, clave, arranque).
    assert m["par"] == {"pct": 10, "key": 5, "st": 2}
    # Totales de Parámetros: 147 / 146 / 15 / intervalo 14,20.
    assert m["tot"] == {"N": 147, "d14": 146, "n": 15, "itv": 14.20}
    # Muestra: las 4 filas marcadas (M="Sí") con su tipo de selección.
    assert len(m["mue"]) == 4
    assert all(row[4] in ("Clave (mayor D13)", "Sistemática") for row in m["mue"])
    assert [row[4] for row in m["mue"][:2]] == ["Clave (mayor D13)", "Clave (mayor D13)"]


def test_render_muestreo_inyecta_pop07_desde_el_motor(tmp_path):
    """render inyecta __NOMINA_POP07__ con la población del motor; sin cédula → lista vacía."""
    import json
    import re

    carpeta = _carpeta_con_rq007(tmp_path, n=8, selecc=3)
    html = np.render({"client": "Empresa de Ejemplo S.A.", "firm": "AuditConsulting",
                      "year": 2026}, 5, carpeta_cedulas=carpeta).decode()
    assert "__NOMINA_POP07__" not in html  # placeholder reemplazado
    pop = json.loads(re.search(r"const POP07=(\[.*?\]);", html).group(1))
    assert len(pop) == 8 and pop[0][0].startswith("170000000")
    bajo = html.lower()
    for t in TERMINOS_PILOTO:
        assert t not in bajo, t
    # Sin cédula procesada: POP07 queda vacío → la ventana muestra «PENDIENTE DE PROCESAR».
    vacio = np.render({"client": "Empresa de Ejemplo S.A.", "firm": "AuditConsulting"},
                      1, carpeta_cedulas=None).decode()
    assert re.search(r"const POP07=\[\];", vacio)


def test_render_con_motor_llena_ventanas_y_sin_datos_del_piloto(tmp_path):
    """HTML completo: PROG y MDL inyectados desde el motor, sin términos del piloto."""
    import json
    import re

    extras = {"prog": _PROG_FICTICIO, "do12": _DO12_FICTICIO}
    carpeta = _carpeta_con_vac(tmp_path)
    html = np.render({"client": "Empresa de Ejemplo S.A.", "firm": "AuditConsulting",
                      "year": 2026}, 7, carpeta_cedulas=carpeta, extras=extras).decode()
    assert "__NOMINA_" not in html
    prog = json.loads(re.search(r"const PROG=(\{.*\});\nlet pTab", html).group(1))
    mdl = json.loads(re.search(r"const MDL=(\{.*?\});\nconst XS", html).group(1))
    assert len(prog["prog"]) == 2 and len(prog["h12"]) == 14
    assert [r[0] for r in prog["aj"]] == ["AJ-1", "RJ-1"]
    assert mdl["vacx"]["estado"].startswith("CALCULADO") and mdl["k08"]["filas"] == 3
    bajo = html.lower()
    for t in TERMINOS_PILOTO:
        assert t not in bajo, t


def test_render_sin_motor_ventanas_vacias(tmp_path):
    """Sin extras ni carpeta: PROG/MDL vacíos → las ventanas muestran «PENDIENTE DE PROCESAR»."""
    import json
    import re

    html = np.render({"client": "Empresa de Ejemplo S.A.", "firm": "AuditConsulting"},
                     1, carpeta_cedulas=None, extras=None).decode()
    prog = json.loads(re.search(r"const PROG=(\{.*\});\nlet pTab", html).group(1))
    mdl = json.loads(re.search(r"const MDL=(\{.*?\});\nconst XS", html).group(1))
    assert prog["prog"] == [] and prog["h12"] == [] and mdl == {}
    assert "PENDIENTE DE PROCESAR" in html


def test_render_procesado_trae_el_visor_con_libros(tmp_path):
    import base64
    import gzip
    import json
    import re

    carpeta = _carpeta_cedulas_ficticias(tmp_path)
    html = np.render({"client": "Empresa de Ejemplo S.A.", "firm": "AuditConsulting"},
                     9, carpeta_cedulas=carpeta).decode()
    m = re.search(r'const VISOR_GZ="([A-Za-z0-9+/=]+)";', html)
    assert m, "el visor no quedó inyectado"
    datos = json.loads(gzip.decompress(base64.b64decode(m.group(1))).decode("utf-8"))
    cods = {lb["c"] for lb in datos["libros"]}
    assert {"DO-2", "DO-3"} <= cods and datos["libros"]


def test_cabecera_logo_segun_firma_y_logo_cliente():
    import json
    import re

    # Firma por defecto (AuditConsulting) → 'audit'; «Partner» → 'partner'.
    for firm, esperado in (("AuditConsulting", "audit"), ("Partner Auditing", "partner")):
        html = np.render({"client": "X S.A.", "firm": firm}, 1).decode()
        enc = json.loads(re.search(r"let ENC=(\{.*?\});", html).group(1))
        assert enc["firma"] == esperado, firm
    # La marca del panel trae los cuatro logos (los mismos de marca.py).
    marca = np.marca_panel({"firm": "AuditConsulting"})
    assert set(marca) == {"audit", "auditOscuro", "partner", "auditia"}
    assert all(str(v).startswith("data:image/") for v in marca.values())
    # Logo del cliente: si la ficha lo trae (data URI), viaja en el encargo.
    logo = "data:image/png;base64,iVBORw0KGgo="
    html = np.render({"client": "X S.A.", "firm": "AuditConsulting", "logoCliente": logo}, 1).decode()
    enc = json.loads(re.search(r"let ENC=(\{.*?\});", html).group(1))
    assert enc.get("clienteLogo") == logo


# --- endpoints bespoke -------------------------------------------------------

def test_panel_nomina_sirve_html_con_el_encargo(client):
    tok, pid = _staff_con_proyecto(client)
    pr = _ficha_y_prueba_nomina(client, tok, pid)
    r = client.get(f"{BASE}/pruebas/{pr['id']}/panel-nomina", headers=_h(tok))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert FICHA["client"] in r.text and FICHA["ruc"] in r.text
    assert f'"pruebaId": {pr["id"]}' in r.text


def test_do1_se_guarda_en_la_prueba_y_se_precarga(client):
    """El estado del DO-1 se persiste DENTRO de la prueba (no en el localStorage) y el panel lo
    precarga en __NOMINA_DO1__ la próxima vez que se abre."""
    import json
    import re

    tok, pid = _staff_con_proyecto(client)
    pr = _ficha_y_prueba_nomina(client, tok, pid)
    estado = {"nt": 25, "ntManual": True, "ans": {"33": "Sí", "36": "No"},
              "obs": {"36": "Falta el comité paritario"}, "step": 1, "done": False}
    r = client.post(f"{BASE}/pruebas/{pr['id']}/nomina-do1", headers=_h(tok), json={"estado": estado})
    assert r.status_code == 200 and r.json()["ok"] is True
    # Al reabrir el panel, el estado viaja en DO1_SAVED (precarga desde la prueba).
    html = client.get(f"{BASE}/pruebas/{pr['id']}/panel-nomina", headers=_h(tok)).text
    saved = json.loads(re.search(r"const DO1_SAVED=(\{.*?\});", html).group(1))
    assert saved == estado


def test_do1_rechaza_estado_invalido(client):
    """estado que no es objeto → 400 (no se corrompe el registro de la prueba)."""
    tok, pid = _staff_con_proyecto(client)
    pr = _ficha_y_prueba_nomina(client, tok, pid)
    r = client.post(f"{BASE}/pruebas/{pr['id']}/nomina-do1", headers=_h(tok),
                    json={"estado": "no-soy-un-objeto"})
    assert r.status_code == 422  # pydantic rechaza el tipo antes de llegar al servicio


def test_cedulas_piden_datos_minimos(client):
    tok, pid = _staff_con_proyecto(client)
    pr = _ficha_y_prueba_nomina(client, tok, pid)
    # Sin archivos cargados: faltan los requerimientos mínimos → 400 con mensaje claro.
    r = client.get(f"{BASE}/pruebas/{pr['id']}/cedula-nomina/{nb.CEDULAS[0]}", headers=_h(tok))
    assert r.status_code == 400 and "RQ-002" in r.json()["detail"]
    r = client.get(f"{BASE}/pruebas/{pr['id']}/cedulas-nomina", headers=_h(tok))
    assert r.status_code == 400 and "RQ-002" in r.json()["detail"]


def test_cedula_desconocida_da_404(client):
    tok, pid = _staff_con_proyecto(client)
    pr = _ficha_y_prueba_nomina(client, tok, pid)
    r = client.get(f"{BASE}/pruebas/{pr['id']}/cedula-nomina/NO_EXISTE.xlsx", headers=_h(tok))
    assert r.status_code == 404


def test_libro_generico_no_aplica_a_la_bespoke(client):
    tok, pid = _staff_con_proyecto(client)
    pr = _ficha_y_prueba_nomina(client, tok, pid)
    r = client.get(f"{BASE}/pruebas/{pr['id']}/libro?formato=html", headers=_h(tok))
    assert r.status_code == 400 and "panel" in r.json()["detail"].lower()


def test_panel_solo_para_la_herramienta_de_nomina(client):
    tok, pid = _staff_con_proyecto(client)
    pr = _ficha_y_prueba_nomina(client, tok, pid, origen="proc:efectivo_equivalentes")
    r = client.get(f"{BASE}/pruebas/{pr['id']}/panel-nomina", headers=_h(tok))
    assert r.status_code == 400
    # Y la de nómina no ofrece el papel formulado de bancos.
    prn = _staff_con_proyecto(client)
    tok2, pid2 = prn
    pr2 = _ficha_y_prueba_nomina(client, tok2, pid2)
    assert client.get(f"{BASE}/pruebas/{pr2['id']}/papel-bancos", headers=_h(tok2)).status_code == 400


# --- regresión: la cadena del requerimiento se arma para la nómina bespoke ----
#
# Antes fallaba: `generate_program` reventaba con KeyError('risk') porque el programa
# de la nómina es mínimo (code/objective/assertion) y `crear_programa` exigía el
# esquema completo del encargo NIIF. Sin programa no había requerimiento → el panel
# no podía crear la prueba («No se pudo conectar con el servidor»). Aquí se recorre la
# misma cadena que `prepararBaseTecnica` del frontend hasta REQUERIMIENTO_APROBADO.

def _leer(client, tok, prid):
    r = client.get(f"{BASE}/pruebas/{prid}", headers=_h(tok))
    assert r.status_code == 200, r.text
    return r.json()


def test_cadena_del_requerimiento_llega_a_aprobado(client):
    tok, pid = _staff_con_proyecto(client)
    pr = _ficha_y_prueba_nomina(client, tok, pid)
    prid = pr["id"]
    for _ in range(10):
        p = _leer(client, tok, prid)
        reg, est, rev = p["registro"], p["estado"], p["revision"]
        if est == "PRUEBA_SELECCIONADA":
            accion, datos = ("generate_program", {}) if reg.get("researchedAt") else ("research", {})
        elif est == "PROGRAMA_PROPUESTO":
            codigos = [x["code"] for x in (reg.get("program") or [])]
            corte = (reg.get("engagement") or {}).get("cutoff") or "corte"
            fuentes = []
            for s in (reg.get("sources") or []):
                f = {**s, "verified": True, "procedures": codigos, "date": s.get("date") or f"Vigente al {corte}"}
                if s.get("category") in ("NIIF", "NIA"):
                    f["section"] = s.get("section") or "Según programa de la ficha"
                fuentes.append(f)
            accion, datos = "approve_program", {"program": reg.get("program"), "sources": fuentes,
                                                "taxScope": reg.get("taxScope") or "", "taxAcknowledged": True}
        elif est == "PROGRAMA_APROBADO":
            accion, datos = "generate_request", {}
        elif est == "REQUERIMIENTO_GENERADO":
            accion, datos = "approve_request", {"requests": reg.get("requests")}
        else:
            break
        r = client.post(f"{BASE}/pruebas/{prid}/acciones", headers=_h(tok),
                        json={"accion": accion, "revision": rev, "datos": datos})
        assert r.status_code == 200, f"{accion}: {r.text[:500]}"

    final = _leer(client, tok, prid)
    assert final["estado"] == "REQUERIMIENTO_APROBADO", final["estado"]
    # Los 8 requerimientos propios de la nómina (RQ-001..RQ-008) con sus procedimientos.
    ids = {rq["id"] for rq in final["registro"]["requests"]}
    assert {"RQ-001", "RQ-002", "RQ-003", "RQ-006"} <= ids
    assert len(final["registro"]["requests"]) == 8
