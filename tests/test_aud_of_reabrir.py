"""Reabrir un encargo ya generado para corregir lo cargado y re-ejecutar."""

from backend.app.aud.obligaciones_fiscales import file_storage

from tests.test_aud_of_aprobacion import _procesado  # noqa: F401
from tests.test_aud_of_router import _db, _h, _mk_admin_project  # noqa: F401

BASE = "/api/v1/aud/obligaciones-fiscales"


def _done(client):
    """Deja un encargo en 'done' (procesado + aprobado). Con el TestClient la
    BackgroundTask de generación ya corrió al volver de la llamada."""
    tok, jid = _procesado(client)
    r = client.post(f"{BASE}/jobs/{jid}/aprobar", headers=_h(tok))
    assert r.status_code == 200, r.text
    estado = client.get(f"{BASE}/jobs/{jid}", headers=_h(tok)).json()
    assert estado["status"] == "done", estado
    return tok, jid


def test_reabrir_un_job_done_lo_deja_en_revision(client):
    tok, jid = _done(client)
    r = client.post(f"{BASE}/jobs/{jid}/reabrir", headers=_h(tok))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "revision"
    # Y el estado persiste: al volver a consultarlo sigue en revisión.
    estado = client.get(f"{BASE}/jobs/{jid}", headers=_h(tok)).json()
    assert estado["status"] == "revision"


def test_reabierto_vuelve_a_ser_editable_y_re_aprobable(client):
    tok, jid = _done(client)
    client.post(f"{BASE}/jobs/{jid}/reabrir", headers=_h(tok))

    # La clasificación se puede corregir de nuevo (solo permitido en 'revision').
    r = client.put(
        f"{BASE}/jobs/{jid}/clasificacion",
        headers=_h(tok),
        json={"correcciones": [{"codigo_cuenta": "4.1.1.4", "categoria": "IVA_VENTAS"}]},
    )
    assert r.status_code == 200, r.text
    cuentas = {c["codigo_cuenta"]: c for c in r.json()["cuentas"]}
    assert cuentas["4.1.1.4"]["categoria_final"] == "IVA_VENTAS"

    # Y se puede volver a aprobar para regenerar el Excel.
    r = client.post(f"{BASE}/jobs/{jid}/aprobar", headers=_h(tok))
    assert r.status_code == 200, r.text
    estado = client.get(f"{BASE}/jobs/{jid}", headers=_h(tok)).json()
    assert estado["status"] == "done"


def test_reabierto_se_puede_volver_a_procesar(client):
    """Tras reabrir (p. ej. para reemplazar un documento mal cargado) se puede
    volver a Procesar; el guard de procesar acepta 'revision'."""
    tok, jid = _done(client)
    client.post(f"{BASE}/jobs/{jid}/reabrir", headers=_h(tok))
    r = client.post(f"{BASE}/jobs/{jid}/procesar", headers=_h(tok))
    assert r.status_code == 200, r.text
    estado = client.get(f"{BASE}/jobs/{jid}", headers=_h(tok)).json()
    assert estado["status"] == "revision"


def test_descargar_y_luego_reabrir_conserva_los_documentos(client):
    """Escenario del dueño: se descarga el Excel, se detecta un dato mal
    cargado y se reabre para corregir. Descargar NO borra los documentos, así
    que reabrir funciona (no da 410)."""
    tok, jid = _done(client)
    r = client.get(f"{BASE}/jobs/{jid}/download", headers=_h(tok))
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE}/jobs/{jid}/reabrir", headers=_h(tok))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "revision"


def test_no_se_puede_reabrir_un_job_que_no_esta_done(client):
    """Un encargo en 'revision' (o borrador) ya es editable: reabrir da 409."""
    tok, jid = _procesado(client)  # queda en 'revision'
    r = client.post(f"{BASE}/jobs/{jid}/reabrir", headers=_h(tok))
    assert r.status_code == 409, r.text
    assert "reabrir" in r.text.lower()


def test_reabrir_sin_documentos_en_disco_da_410(client):
    """Si los documentos ya se limpiaron (expiración o post-descarga) no hay
    nada que re-procesar: 410 con un aviso claro, no un encargo vacío."""
    tok, jid = _done(client)
    file_storage.delete_job_dir(jid)  # simula el cleanup
    r = client.post(f"{BASE}/jobs/{jid}/reabrir", headers=_h(tok))
    assert r.status_code == 410, r.text
    assert "disponibles" in r.text.lower()
