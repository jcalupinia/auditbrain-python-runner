"""Fase 1: leer el mayor, clasificar y dejar el job en revisión."""

import io

from openpyxl import Workbook

from tests.test_aud_of_router import _db, _h, _mk_admin_project  # noqa: F401

ENCABEZADO = ("Código", "Cuenta", "Fecha", "Asiento", "Documento", "Identificación",
              "Persona", "Persona Cruce Cuenta", "Descripción", "Debe", "Haber", "Saldo")

FILAS = [
    ["1.1.5.1.1", "IVA sobre Compras", "2025-01-05", "COM 1", "", "", "", "", "", 10.0, 0, 10.0],
    ["4.1.1.4", "Venta de insumos", "2025-01-06", "VTA 1", "", "", "", "", "", 0, 100.0, -100.0],
    ["2.1.7.3.2", "Ret. 70% Servicios", "2025-01-07", "RET 1", "", "", "", "", "", 0, 7.0, -7.0],
]


def _mayor_bytes():
    wb = Workbook()
    ws = wb.active
    ws.append(list(ENCABEZADO))
    for f in FILAS:
        ws.append(f)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _borrador_con_mayor(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs", headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    jid = r.json()["id"]
    client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/mayor_general",
        headers=_h(tok),
        files=[("archivos", ("mayor.xlsx", io.BytesIO(_mayor_bytes()),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
    )
    return tok, jid


def test_procesar_deja_el_job_en_revision(client):
    tok, jid = _borrador_con_mayor(client)
    r = client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    assert r.status_code == 200, r.text
    r2 = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    assert r2.json()["status"] == "revision"


def test_la_clasificacion_queda_disponible_para_la_pantalla_de_revision(client):
    tok, jid = _borrador_con_mayor(client)
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/clasificacion", headers=_h(tok))
    assert r.status_code == 200
    cuentas = {c["codigo_cuenta"]: c for c in r.json()["cuentas"]}
    assert cuentas["1.1.5.1.1"]["categoria_final"] == "IVA_COMPRAS"
    assert cuentas["4.1.1.4"]["categoria_final"] == "VENTAS"
    assert cuentas["2.1.7.3.2"]["categoria_final"] == "RET_IVA"
    assert cuentas["2.1.7.3.2"]["tarifa"] == 70.0


def test_la_respuesta_trae_las_categorias_disponibles_para_el_selector(client):
    tok, jid = _borrador_con_mayor(client)
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/clasificacion", headers=_h(tok))
    codigos = {c["codigo"] for c in r.json()["categorias"]}
    assert "IVA_COMPRAS" in codigos and "VENTAS" in codigos


def test_cada_cuenta_explica_por_que_quedo_ahi(client):
    tok, jid = _borrador_con_mayor(client)
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/clasificacion", headers=_h(tok))
    cuenta = next(c for c in r.json()["cuentas"] if c["codigo_cuenta"] == "1.1.5.1.1")
    assert cuenta["justificacion"], "la pantalla necesita el porqué de cada clasificación"


def test_procesar_sin_mayor_general_da_400(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs", headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    jid = r.json()["id"]
    r2 = client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    assert r2.status_code == 400
    assert "mayor" in r2.text.lower()


def test_un_mayor_ilegible_deja_el_job_en_failed_con_el_motivo(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs", headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    jid = r.json()["id"]
    client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/mayor_general",
        headers=_h(tok),
        files=[("archivos", ("roto.xlsx", io.BytesIO(b"no soy un excel"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
    )
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    r2 = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    assert r2.json()["status"] == "failed"
    assert r2.json()["error_message"]
