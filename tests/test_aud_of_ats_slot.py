"""El slot 'ats' acepta tanto XML como PDF (Talón Resumen del SRI)."""

import io

from backend.app.aud.obligaciones_fiscales.router import ALLOWED_MIMES
from tests.test_aud_of_router import _h, _mk_admin_project  # noqa: F401


def _crear_borrador(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    return tok, r.json()["id"]


def test_allowed_mimes_del_slot_ats_incluye_pdf_y_xml():
    assert "application/pdf" in ALLOWED_MIMES["ats"]
    assert "application/xml" in ALLOWED_MIMES["ats"]
    assert "text/xml" in ALLOWED_MIMES["ats"]


def test_subir_un_pdf_al_slot_ats(client):
    tok, jid = _crear_borrador(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/ats",
        headers=_h(tok),
        files=[("archivos", ("talon.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"))],
    )
    assert r.status_code == 200, r.text
    assert r.json()["ats"]["n_archivos"] == 1


def test_subir_un_xml_al_slot_ats(client):
    tok, jid = _crear_borrador(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/ats",
        headers=_h(tok),
        files=[("archivos", ("anexo.xml", io.BytesIO(b"<xml/>"), "application/xml"))],
    )
    assert r.status_code == 200, r.text
    assert r.json()["ats"]["n_archivos"] == 1
