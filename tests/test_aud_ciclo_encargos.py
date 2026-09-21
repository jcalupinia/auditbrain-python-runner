"""Encargos NIIF creados desde la herramienta, sin pasar por Workspaces."""
from tests.test_aud_ciclo_http import BASE, FICHA, _staff_con_proyecto
from tests.test_aud_niif_fichas import _h


def test_crear_y_listar_encargos_desde_la_herramienta(client):
    tok, pid_adv = _staff_con_proyecto(client, modulo="ADV", organizacion_propia=True)
    # El proyecto ADV no es un encargo NIIF.
    assert all(e["id"] != pid_adv for e in client.get(f"{BASE}/encargos", headers=_h(tok)).json())

    # Ficha incompleta: no se crea nada (ni cliente ni proyecto).
    r = client.post(f"{BASE}/encargos", headers=_h(tok), json={"ficha": {**FICHA, "framework": ""}})
    assert r.status_code == 400
    assert client.get(f"{BASE}/encargos", headers=_h(tok)).json() == []

    # Cliente nuevo: se crean cliente, proyecto AUD y ficha juntos.
    r = client.post(f"{BASE}/encargos", headers=_h(tok), json={"cliente": "Comercial Andina S.A.", "ficha": FICHA})
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["nombre"] == "Auditoría 2025" and e["cliente"] == "Comercial Andina S.A." and e["marco"] == "NIIF completas"
    assert client.get(f"{BASE}/proyectos/{e['id']}/ficha", headers=_h(tok)).json()["ficha"]["cutoff"] == "2025-12-31"
    # Ya se pueden crear pruebas en él, sin tocar el Workspace activo.
    assert client.post(f"{BASE}/proyectos/{e['id']}/pruebas", headers=_h(tok), json={"origen": "vnr"}).status_code == 201

    # Mismo cliente por nombre (sin distinguir mayúsculas): no se duplica.
    r = client.post(f"{BASE}/encargos", headers=_h(tok),
                    json={"cliente": "comercial andina s.a.", "nombre": "Revisión limitada 2025", "ficha": FICHA})
    assert r.json()["client_id"] == e["client_id"]
    lista = client.get(f"{BASE}/encargos", headers=_h(tok)).json()
    assert [(x["nombre"], x["pruebas"]) for x in lista] == [("Auditoría 2025", 1), ("Revisión limitada 2025", 0)]

    # Cliente de otra organización: rechazado.
    otro, _ = _staff_con_proyecto(client, organizacion_propia=True)
    r = client.post(f"{BASE}/encargos", headers=_h(otro), json={"client_id": e["client_id"], "ficha": FICHA})
    assert r.status_code == 400 and "Cliente no encontrado" in r.json()["detail"]
    assert all(x["id"] not in {e["id"] for e in lista} for x in client.get(f"{BASE}/encargos", headers=_h(otro)).json())
