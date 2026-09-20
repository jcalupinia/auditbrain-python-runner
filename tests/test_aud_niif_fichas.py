"""Fichas de diseño NIIF: persistencia compartida y circuito de estados."""

import uuid

import pytest

from backend.app.aud.niif import service
from backend.app.aud.niif.models import NiifFicha
from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal, init_db

BASE = "/api/v1/aud/niif"


def _mk_user(role=Role.user):
    init_db()
    tag = uuid.uuid4().hex[:6]
    email = f"niif-{tag}@ex.com"
    pw = "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=role)
    finally:
        db.close()
    return email, pw


def _login(client, email, pw):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _staff(client, role=Role.user):
    email, pw = _mk_user(role)
    return _login(client, email, pw), email


def _ficha_payload(nombre="Valor neto de realización de inventarios"):
    return {
        "nombre": nombre,
        "rubro": "INVENTARIOS",
        "norma": "NIC 2 · Inventarios",
        "parrafo": "§ 9, 28-33",
        "items": [
            {
                "que_se_pide": "Kárdex valorado a la fecha de corte",
                "formatos": ["xlsx", "csv"],
                "obligatorio": True,
                "componentes": 12,
                "grupo_alternativas": "",
            }
        ],
        "salidas": [{"nombre": "Cédula de VNR por ítem", "formatos": ["excel", "html"]}],
    }


def _crear(client, tok, payload=None):
    r = client.post(f"{BASE}/fichas", headers=_h(tok), json=payload or _ficha_payload())
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------------------
# Permisos
# --------------------------------------------------------------------------


def test_sin_auth_no_se_listan_ni_se_crean_fichas(client):
    assert client.get(f"{BASE}/fichas").status_code in (401, 403)
    assert client.post(f"{BASE}/fichas", json=_ficha_payload()).status_code in (401, 403)


def test_un_operador_puede_crear_y_listar(client):
    tok, email = _staff(client, Role.user)
    creada = _crear(client, tok)
    assert creada["estado"] == "en_diseño"
    assert creada["autor_email"] == email
    r = client.get(f"{BASE}/fichas", headers=_h(tok))
    assert r.status_code == 200, r.text
    assert any(f["id"] == creada["id"] for f in r.json())


# --------------------------------------------------------------------------
# Lo que la localStorage no permitía: la ficha la ve otro auditor
# --------------------------------------------------------------------------


def test_la_ficha_que_diseno_uno_la_ve_y_la_prueba_otro(client):
    tok_autor, email_autor = _staff(client)
    creada = _crear(client, tok_autor)

    tok_revisor, email_revisor = _staff(client)
    r = client.get(f"{BASE}/fichas/{creada['id']}", headers=_h(tok_revisor))
    assert r.status_code == 200, r.text
    assert r.json()["autor_email"] == email_autor

    r = client.post(
        f"{BASE}/fichas/{creada['id']}/estado",
        headers=_h(tok_revisor),
        json={"estado": "probada"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["estado"] == "probada"
    assert body["probada_por_email"] == email_revisor
    assert body["probada_por_email"] != email_autor
    assert body["probada_en"] is not None


# --------------------------------------------------------------------------
# Circuito de estados
# --------------------------------------------------------------------------


def test_no_se_puede_saltar_de_en_diseno_a_enviada(client):
    tok, _ = _staff(client)
    creada = _crear(client, tok)
    r = client.post(
        f"{BASE}/fichas/{creada['id']}/estado",
        headers=_h(tok),
        json={"estado": "enviada"},
    )
    assert r.status_code == 409, r.text
    assert "en_diseño" in r.json()["detail"]
    # y la ficha sigue donde estaba
    leida = client.get(f"{BASE}/fichas/{creada['id']}", headers=_h(tok)).json()
    assert leida["estado"] == "en_diseño"
    assert leida["enviada_en"] is None


def test_camino_completo_en_diseno_probada_enviada(client):
    tok, email = _staff(client)
    creada = _crear(client, tok)
    fid = creada["id"]

    r = client.post(f"{BASE}/fichas/{fid}/estado", headers=_h(tok), json={"estado": "probada"})
    assert r.status_code == 200, r.text

    r = client.post(f"{BASE}/fichas/{fid}/estado", headers=_h(tok), json={"estado": "enviada"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["estado"] == "enviada"
    assert body["enviada_por_email"] == email
    assert body["enviada_en"] is not None


def test_enviada_es_terminal(client):
    tok, _ = _staff(client)
    fid = _crear(client, tok)["id"]
    client.post(f"{BASE}/fichas/{fid}/estado", headers=_h(tok), json={"estado": "probada"})
    client.post(f"{BASE}/fichas/{fid}/estado", headers=_h(tok), json={"estado": "enviada"})
    for destino in ("probada", "en_diseño", "enviada"):
        r = client.post(f"{BASE}/fichas/{fid}/estado", headers=_h(tok), json={"estado": destino})
        assert r.status_code == 409, (destino, r.text)


def test_estado_desconocido_es_rechazado(client):
    tok, _ = _staff(client)
    fid = _crear(client, tok)["id"]
    r = client.post(f"{BASE}/fichas/{fid}/estado", headers=_h(tok), json={"estado": "lista"})
    assert r.status_code == 422, r.text


def test_probada_dos_veces_no_reescribe_al_revisor(client):
    tok_a, email_a = _staff(client)
    fid = _crear(client, tok_a)["id"]
    client.post(f"{BASE}/fichas/{fid}/estado", headers=_h(tok_a), json={"estado": "probada"})

    tok_b, _ = _staff(client)
    r = client.post(f"{BASE}/fichas/{fid}/estado", headers=_h(tok_b), json={"estado": "probada"})
    assert r.status_code == 409, r.text
    leida = client.get(f"{BASE}/fichas/{fid}", headers=_h(tok_a)).json()
    assert leida["probada_por_email"] == email_a


# --------------------------------------------------------------------------
# Edición
# --------------------------------------------------------------------------


def test_se_edita_en_diseno_y_deja_de_editarse_al_probarse(client):
    tok, _ = _staff(client)
    fid = _crear(client, tok)["id"]

    cambio = _ficha_payload("VNR de inventarios (v2)")
    r = client.patch(f"{BASE}/fichas/{fid}", headers=_h(tok), json=cambio)
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "VNR de inventarios (v2)"

    client.post(f"{BASE}/fichas/{fid}/estado", headers=_h(tok), json={"estado": "probada"})
    r = client.patch(f"{BASE}/fichas/{fid}", headers=_h(tok), json=_ficha_payload("otro nombre"))
    assert r.status_code == 409, r.text
    assert client.get(f"{BASE}/fichas/{fid}", headers=_h(tok)).json()["nombre"] == (
        "VNR de inventarios (v2)"
    )


def test_ficha_incompleta_es_rechazada(client):
    tok, _ = _staff(client)
    malas = [
        {**_ficha_payload(), "nombre": "   "},
        {**_ficha_payload(), "items": []},
        {**_ficha_payload(), "salidas": []},
    ]
    sin_formato = _ficha_payload()
    sin_formato["items"][0]["formatos"] = []
    malas.append(sin_formato)
    for payload in malas:
        r = client.post(f"{BASE}/fichas", headers=_h(tok), json=payload)
        assert r.status_code == 422, r.text


def test_ficha_inexistente_da_404(client):
    tok, _ = _staff(client)
    assert client.get(f"{BASE}/fichas/999999", headers=_h(tok)).status_code == 404


# --------------------------------------------------------------------------
# Transiciones como función pura (sin HTTP)
# --------------------------------------------------------------------------


def test_transicion_permitida_solo_avanza_un_paso():
    assert service.transicion_permitida("en_diseño", "probada")
    assert service.transicion_permitida("probada", "enviada")
    assert not service.transicion_permitida("en_diseño", "enviada")
    assert not service.transicion_permitida("probada", "en_diseño")
    assert not service.transicion_permitida("enviada", "probada")


def test_aplicar_transicion_invalida_lanza():
    ficha = NiifFicha(estado="en_diseño")

    class _U:
        id = 1
        email = "x@ex.com"

    with pytest.raises(service.TransicionInvalida):
        service.aplicar_transicion(ficha, "enviada", _U())
    assert ficha.estado == "en_diseño"
