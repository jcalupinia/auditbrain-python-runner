"""Tests de PATCH /aud/obligaciones-fiscales/jobs/{job_id} — edición de
metadatos del encargo sin tocar archivos ni clasificación."""

import io

from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.db.session import SessionLocal
from tests.test_aud_of_router import _h, _mk_admin_project  # noqa: F401
from tests.test_aud_of_router import _db  # noqa: F401
from tests.test_aud_of_slots import _mk_admin_otra_organizacion  # noqa: F401


def _crear_borrador(client, **extra):
    tok, pid = _mk_admin_project(client)
    data = {"project_id": pid, "cliente_name": "C", "period_label": "2025"}
    data.update(extra)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok), data=data,
    )
    assert r.status_code == 201, r.text
    return tok, r.json()["id"]


def _set_status(job_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        job.status = status
        db.add(job)
        db.commit()
    finally:
        db.close()


def test_patch_actualiza_campos_y_persiste(client):
    tok, jid = _crear_borrador(client)
    r = client.patch(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}",
        headers=_h(tok),
        json={"cliente_name": "Cliente Nuevo", "prepared_by_name": "Ana"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["cliente_name"] == "Cliente Nuevo"
    assert r.json()["prepared_by_name"] == "Ana"

    r2 = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    assert r2.json()["cliente_name"] == "Cliente Nuevo"
    assert r2.json()["prepared_by_name"] == "Ana"


def test_patch_solo_toca_los_campos_enviados(client):
    tok, jid = _crear_borrador(
        client, prepared_by_name="Original Prep", reviewed_by_name="Original Rev",
    )
    r = client.patch(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}",
        headers=_h(tok),
        json={"cliente_name": "Solo cambio esto"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cliente_name"] == "Solo cambio esto"
    # los campos NO enviados en el PATCH deben permanecer intactos
    assert body["prepared_by_name"] == "Original Prep"
    assert body["reviewed_by_name"] == "Original Rev"
    assert body["period_label"] == "2025"


def test_patch_en_estado_done_da_409(client):
    tok, jid = _crear_borrador(client)
    _set_status(jid, "done")
    r = client.patch(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}",
        headers=_h(tok),
        json={"cliente_name": "No debería aplicar"},
    )
    assert r.status_code == 409, r.text


def test_patch_firma_invalida_da_400(client):
    tok, jid = _crear_borrador(client)
    r = client.patch(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}",
        headers=_h(tok),
        json={"firma_auditora": "no_existe"},
    )
    assert r.status_code == 400, r.text


def test_patch_desde_otra_organizacion_da_403(client):
    tok, jid = _crear_borrador(client)
    otro_tok = _mk_admin_otra_organizacion(client)
    r = client.patch(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}",
        headers=_h(otro_tok),
        json={"cliente_name": "Intento ajeno"},
    )
    assert r.status_code == 403, r.text


def test_patch_no_borra_los_archivos_ya_subidos(client):
    """El caso que da sentido a todo esto: subir un archivo a un slot, hacer
    PATCH de metadatos, y comprobar que el archivo SIGUE ahí."""
    tok, jid = _crear_borrador(client)
    client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104",
        headers=_h(tok),
        files=[("archivos", ("d.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"))],
    )
    r_slots_antes = client.get(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots", headers=_h(tok)
    )
    assert r_slots_antes.json()["f104"]["n_archivos"] == 1

    r = client.patch(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}",
        headers=_h(tok),
        json={"cliente_name": "Cliente Actualizado", "reviewed_by_name": "Beatriz"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["cliente_name"] == "Cliente Actualizado"

    r_slots_despues = client.get(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots", headers=_h(tok)
    )
    assert r_slots_despues.status_code == 200
    assert r_slots_despues.json()["f104"]["n_archivos"] == 1
    assert r_slots_despues.json()["f104"]["nombres"] == r_slots_antes.json()["f104"]["nombres"]
