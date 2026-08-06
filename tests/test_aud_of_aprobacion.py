"""El auditor corrige, aprueba, y lo aprendido queda para el próximo año."""

from tests.test_aud_of_fase1 import _borrador_con_mayor  # noqa: F401
from tests.test_aud_of_router import _db, _h, _mk_admin_project  # noqa: F401


def _procesado(client):
    tok, jid = _borrador_con_mayor(client)
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    return tok, jid


def test_corregir_una_cuenta_cambia_su_categoria_final(client):
    tok, jid = _procesado(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/clasificacion",
        headers=_h(tok),
        json={"correcciones": [{"codigo_cuenta": "4.1.1.4", "categoria": "IVA_VENTAS"}]},
    )
    assert r.status_code == 200, r.text
    cuentas = {c["codigo_cuenta"]: c for c in r.json()["cuentas"]}
    assert cuentas["4.1.1.4"]["categoria_final"] == "IVA_VENTAS"
    assert cuentas["4.1.1.4"]["categoria_sugerida"] == "VENTAS"
    assert cuentas["4.1.1.4"]["corregida"] is True


def test_no_se_puede_corregir_hacia_una_categoria_inexistente(client):
    tok, jid = _procesado(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/clasificacion",
        headers=_h(tok),
        json={"correcciones": [{"codigo_cuenta": "4.1.1.4", "categoria": "NO_EXISTE"}]},
    )
    assert r.status_code == 400


def test_aprobar_genera_el_excel_y_deja_el_job_en_done(client):
    tok, jid = _procesado(client)
    r = client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/aprobar", headers=_h(tok))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done"
    d = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/download", headers=_h(tok))
    assert d.status_code == 200


def test_aprobar_guarda_lo_aprendido_en_el_historial_del_cliente(client):
    tok, jid = _procesado(client)
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/aprobar", headers=_h(tok))

    from backend.app.aud.obligaciones_fiscales.mayor.models import MayorHomologacion
    from backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        filas = db.query(MayorHomologacion).all()
        por_codigo = {f.codigo_cuenta: f.categoria for f in filas}
        assert por_codigo["1.1.5.1.1"] == "IVA_COMPRAS"
        assert por_codigo["2.1.7.3.2"] == "RET_IVA"
    finally:
        db.close()


def test_el_segundo_job_del_mismo_cliente_ya_llega_clasificado_por_historial(client):
    tok, jid = _procesado(client)
    client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/clasificacion",
        headers=_h(tok),
        json={"correcciones": [{"codigo_cuenta": "4.1.1.4", "categoria": "IVA_VENTAS"}]},
    )
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/aprobar", headers=_h(tok))

    # mismo proyecto (mismo cliente), nuevo job
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    pid = r.json()["project_id"]
    from tests.test_aud_of_fase1 import _mayor_bytes
    import io

    r2 = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs", headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2026"},
    )
    jid2 = r2.json()["id"]
    client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid2}/slots/mayor_general",
        headers=_h(tok),
        files=[("archivos", ("mayor.xlsx", io.BytesIO(_mayor_bytes()),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
    )
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid2}/procesar", headers=_h(tok))
    r3 = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid2}/clasificacion", headers=_h(tok))
    cuentas = {c["codigo_cuenta"]: c for c in r3.json()["cuentas"]}
    assert cuentas["4.1.1.4"]["categoria_final"] == "IVA_VENTAS"
    assert cuentas["4.1.1.4"]["origen"] == "historial"


def test_aprobar_un_job_que_no_esta_en_revision_da_409(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs", headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    jid = r.json()["id"]
    r2 = client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/aprobar", headers=_h(tok))
    assert r2.status_code == 409
