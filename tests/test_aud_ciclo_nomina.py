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
