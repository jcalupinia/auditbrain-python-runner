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
# El contenido fijo de la plantilla (PROG/POP07/MDL) quedó neutralizado; las ventanas
# Programa/Hallazgos/Vacaciones se alimentarán del motor en la fase B2.
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
