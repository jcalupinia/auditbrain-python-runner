"""Estudio de la prueba por HTTP: cobertura de una ficha y corrida del motor.

Las reglas en sí están probadas en `test_aud_niif_requerimiento.py` y
`test_aud_niif_motor.py`. Aquí se comprueba lo que añade la capa HTTP: que la
ficha guardada se traduzca bien a ítems, que un error del motor vuelva como
400 con su mensaje, y que nada de esto se pueda usar sin sesión.
"""
from tests.test_aud_niif_fichas import BASE, _crear, _ficha_payload, _h, _staff
from tests.test_aud_niif_motor import FILA, NIIF16

DOC = lambda comp: {"kind": "source", "itemId": "i1", "component": comp}  # noqa: E731


# --- permisos ---

def test_sin_sesion_no_se_mide_cobertura_ni_se_corre_el_motor(client):
    assert client.post(f"{BASE}/fichas/1/cobertura", json={}).status_code in (401, 403)
    assert client.post(f"{BASE}/motor/ejecutar", json={}).status_code in (401, 403)


# --- cobertura ---

def test_un_kardex_de_doce_meses_no_se_cubre_con_un_archivo(client):
    tok, _ = _staff(client)
    ficha = _crear(client, tok)  # el ítem declara componentes: 12

    r = client.post(f"{BASE}/fichas/{ficha['id']}/cobertura", headers=_h(tok),
                    json={"documentos": [DOC("Componente 1")]})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["recibidos"] == 1
    assert cuerpo["esperados"] == 12
    assert len(cuerpo["cobertura"][0]["pending"]) == 11
    assert cuerpo["huecos"], "falta cubrir once meses: debe haber un hueco"


def test_los_doce_componentes_dejan_la_ficha_sin_huecos(client):
    tok, _ = _staff(client)
    ficha = _crear(client, tok)
    docs = [DOC(f"Componente {n}") for n in range(1, 13)]

    r = client.post(f"{BASE}/fichas/{ficha['id']}/cobertura", headers=_h(tok), json={"documentos": docs})
    assert r.status_code == 200, r.text
    assert r.json()["huecos"] == []


def test_un_documento_rechazado_no_tapa_el_hueco_por_http(client):
    tok, _ = _staff(client)
    payload = _ficha_payload("Ficha de un solo documento")
    payload["items"][0]["componentes"] = 1
    ficha = _crear(client, tok, payload)

    r = client.post(f"{BASE}/fichas/{ficha['id']}/cobertura", headers=_h(tok),
                    json={"documentos": [{"kind": "source", "itemId": "i1", "state": "rechazado"}]})
    assert r.json()["huecos"] == ["Kárdex valorado a la fecha de corte"]


def test_cobertura_de_una_ficha_inexistente_es_404(client):
    tok, _ = _staff(client)
    r = client.post(f"{BASE}/fichas/999999/cobertura", headers=_h(tok), json={"documentos": []})
    assert r.status_code == 404


# --- motor ---

def test_el_motor_corre_el_arrendamiento_niif16_por_http(client):
    tok, _ = _staff(client)
    r = client.post(f"{BASE}/motor/ejecutar", headers=_h(tok),
                    json={"definicion": NIIF16, "filas": [FILA]})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert len(cuerpo["schedule"]) == 5
    # El control clave del cuadro: el pasivo se extingue al final del plazo.
    assert abs(float(cuerpo["schedule"][-1]["cierre"])) <= 0.02


def test_una_definicion_rota_vuelve_como_400_con_mensaje(client):
    tok, _ = _staff(client)
    rota = dict(NIIF16, rules=[{"key": "x", "label": "x", "op": "potencia", "a": "pago", "b": "#2", "precision": 2}])
    r = client.post(f"{BASE}/motor/ejecutar", headers=_h(tok), json={"definicion": rota, "filas": [FILA]})
    assert r.status_code == 400, r.text
    # El mensaje es el del motor, sin traducir: el mismo texto que vería el
    # auditor en el sitio. Exigirlo evita un falso verde por cualquier 400.
    assert r.json()["detail"] == "Operador no autorizado"


def test_sin_filas_no_se_corre_el_motor(client):
    tok, _ = _staff(client)
    r = client.post(f"{BASE}/motor/ejecutar", headers=_h(tok), json={"definicion": NIIF16, "filas": []})
    assert r.status_code == 400
    assert "fila" in r.json()["detail"]
