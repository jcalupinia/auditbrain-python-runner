"""Mayores específicos: categoría por archivo, varios archivos, y que el
Mayor General ya no sea indispensable (procesar solo con específicos)."""

import io

from tests._mayor_fixtures import mayor_xlsx
from tests.test_aud_of_router import _db, _h, _mk_admin_project  # noqa: F401

BASE = "/api/v1/aud/obligaciones-fiscales"

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _crear_borrador(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        f"{BASE}/jobs", headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    return tok, r.json()["id"]


def _mayor_especifico(client, tok, jid, nombre, categoria, filas):
    return client.put(
        f"{BASE}/jobs/{jid}/slots/mayor_especifico",
        headers=_h(tok),
        files=[("archivos", (nombre, io.BytesIO(mayor_xlsx(filas)), XLSX_MIME))],
        data={"categoria": categoria},
    )


FILA_COMPRA = ["1.1.5.1.1", "IVA sobre Compras", "2025-01-05", "COM 1", "", "", "", "", "", 10.0, 0, 10.0]
FILA_RET = ["2.1.7.3.2", "Ret. 70% Servicios", "2025-01-07", "RET 1", "", "", "", "", "", 0, 7.0, -7.0]


def test_cada_mayor_especifico_guarda_su_propia_categoria(client):
    tok, jid = _crear_borrador(client)
    r1 = _mayor_especifico(client, tok, jid, "compras.xlsx", "IVA_COMPRAS", [FILA_COMPRA])
    assert r1.status_code == 200, r1.text
    r2 = _mayor_especifico(client, tok, jid, "retenciones.xlsx", "RET_IVA", [FILA_RET])
    assert r2.status_code == 200, r2.text

    estado = r2.json()["mayor_especifico"]
    assert estado["n_archivos"] == 2
    por_nombre = {a["nombre"]: a["categoria"] for a in estado["archivos"]}
    assert por_nombre["compras.xlsx"] == "IVA_COMPRAS"
    assert por_nombre["retenciones.xlsx"] == "RET_IVA"


def test_categoria_invalida_es_rechazada(client):
    tok, jid = _crear_borrador(client)
    r = _mayor_especifico(client, tok, jid, "x.xlsx", "NO_EXISTE", [FILA_COMPRA])
    assert r.status_code == 400
    assert "categor" in r.text.lower()


def test_quitar_un_mayor_especifico_por_nombre(client):
    tok, jid = _crear_borrador(client)
    _mayor_especifico(client, tok, jid, "compras.xlsx", "IVA_COMPRAS", [FILA_COMPRA])
    _mayor_especifico(client, tok, jid, "retenciones.xlsx", "RET_IVA", [FILA_RET])

    r = client.delete(
        f"{BASE}/jobs/{jid}/slots/mayor_especifico?nombre=compras.xlsx",
        headers=_h(tok),
    )
    assert r.status_code == 200, r.text
    estado = r.json()["mayor_especifico"]
    assert estado["n_archivos"] == 1
    assert [a["nombre"] for a in estado["archivos"]] == ["retenciones.xlsx"]
    assert estado["archivos"][0]["categoria"] == "RET_IVA"


def test_procesar_sin_ningun_mayor_da_400(client):
    tok, jid = _crear_borrador(client)
    r = client.post(f"{BASE}/jobs/{jid}/procesar", headers=_h(tok))
    assert r.status_code == 400
    assert "específico" in r.text.lower() or "especifico" in r.text.lower()


def test_procesar_solo_con_mayor_especifico_usa_la_categoria_declarada(client):
    """El Mayor General ya no es indispensable: con solo un Mayor específico se
    procesa, y sus cuentas quedan con la categoría declarada (origen declarada,
    confianza alta)."""
    tok, jid = _crear_borrador(client)
    _mayor_especifico(client, tok, jid, "compras.xlsx", "IVA_COMPRAS", [FILA_COMPRA])

    r = client.post(f"{BASE}/jobs/{jid}/procesar", headers=_h(tok))
    assert r.status_code == 200, r.text
    estado = client.get(f"{BASE}/jobs/{jid}", headers=_h(tok)).json()
    assert estado["status"] == "revision", estado

    clasif = client.get(f"{BASE}/jobs/{jid}/clasificacion", headers=_h(tok)).json()
    cuentas = {c["codigo_cuenta"]: c for c in clasif["cuentas"]}
    assert "1.1.5.1.1" in cuentas
    assert cuentas["1.1.5.1.1"]["categoria_final"] == "IVA_COMPRAS"
    assert cuentas["1.1.5.1.1"]["origen"] == "declarada"
    assert cuentas["1.1.5.1.1"]["confianza"] == "alta"


def test_general_y_especifico_conviven_el_especifico_manda(client):
    """Con Mayor General + un específico, la cuenta del específico toma la
    categoría declarada aunque las reglas dirían otra cosa."""
    tok, jid = _crear_borrador(client)
    # General: una venta (las reglas la clasificarían como VENTAS).
    fila_venta = ["4.1.1.4", "Venta de insumos", "2025-01-06", "VTA 1", "", "", "", "", "", 0, 100.0, -100.0]
    client.put(
        f"{BASE}/jobs/{jid}/slots/mayor_general",
        headers=_h(tok),
        files=[("archivos", ("general.xlsx", io.BytesIO(mayor_xlsx([fila_venta])), XLSX_MIME))],
    )
    # Específico: la misma cuenta de venta, pero declarada como IVA_VENTAS.
    _mayor_especifico(client, tok, jid, "esp.xlsx", "IVA_VENTAS", [fila_venta])

    r = client.post(f"{BASE}/jobs/{jid}/procesar", headers=_h(tok))
    assert r.status_code == 200, r.text
    clasif = client.get(f"{BASE}/jobs/{jid}/clasificacion", headers=_h(tok)).json()
    cuentas = {c["codigo_cuenta"]: c for c in clasif["cuentas"]}
    assert cuentas["4.1.1.4"]["categoria_final"] == "IVA_VENTAS"
    assert cuentas["4.1.1.4"]["origen"] == "declarada"
