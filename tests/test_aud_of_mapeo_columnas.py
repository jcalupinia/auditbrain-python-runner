"""Mapeo manual de columnas de un mayor que el detector no reconoce, y
reemplazo de un mayor que dio error (features ② y ③, 2026-10-13)."""

import io

from tests._mayor_fixtures import mayor_xlsx
from tests.test_aud_of_router import _db, _h, _mk_admin_project  # noqa: F401

BASE = "/api/v1/aud/obligaciones-fiscales"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Encabezado cuyos importes el detector NO reconoce ('Valor1'/'Valor2').
ENC_ILEGIBLE = ("Cuenta Contable", "Nombre", "Fecha", "Comprobante", "Valor1", "Valor2")
FILAS = [["1.1.5.1.1", "IVA sobre Compras", "2025-01-05", "A1", 10.0, 0],
         ["1.1.5.1.1", "IVA sobre Compras", "2025-01-06", "A2", 5.0, 0]]


def _crear_borrador(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        f"{BASE}/jobs", headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    return tok, r.json()["id"]


def _subir_ilegible(client, tok, jid, nombre="raro.xlsx"):
    data = mayor_xlsx(FILAS, encabezado=ENC_ILEGIBLE)
    return client.put(
        f"{BASE}/jobs/{jid}/slots/mayor_especifico", headers=_h(tok),
        files=[("archivos", (nombre, io.BytesIO(data), XLSX_MIME))],
        data={"categoria": "IVA_COMPRAS"},
    )


def test_encabezados_reporta_headers_detectadas_y_faltantes(client):
    tok, jid = _crear_borrador(client)
    assert _subir_ilegible(client, tok, jid).status_code == 200
    r = client.get(
        f"{BASE}/jobs/{jid}/slots/mayor_especifico/encabezados?nombre=raro.xlsx",
        headers=_h(tok),
    )
    assert r.status_code == 200, r.text
    info = r.json()
    assert info["headers"] == list(ENC_ILEGIBLE)
    assert info["columnas_faltantes"] == ["debe", "haber"]
    assert info["columnas_detectadas"]["codigo"] == 0


def test_mapeo_manual_exige_las_columnas_minimas(client):
    tok, jid = _crear_borrador(client)
    _subir_ilegible(client, tok, jid)
    # Solo débito: falta haber.
    r = client.put(
        f"{BASE}/jobs/{jid}/slots/mayor_especifico/mapeo?nombre=raro.xlsx",
        headers=_h(tok), json={"mapeo": {"codigo": 0, "debe": 4}},
    )
    assert r.status_code == 400
    assert "haber" in r.text.lower()


def test_mapeo_manual_rechaza_dos_campos_en_la_misma_columna(client):
    tok, jid = _crear_borrador(client)
    _subir_ilegible(client, tok, jid)
    r = client.put(
        f"{BASE}/jobs/{jid}/slots/mayor_especifico/mapeo?nombre=raro.xlsx",
        headers=_h(tok), json={"mapeo": {"codigo": 0, "debe": 4, "haber": 4}},
    )
    assert r.status_code == 400


def test_flujo_completo_mapear_a_mano_y_procesar(client):
    tok, jid = _crear_borrador(client)
    _subir_ilegible(client, tok, jid)

    # 1) Procesar sin mapeo → el mayor es ilegible → job 'failed'.
    assert client.post(f"{BASE}/jobs/{jid}/procesar", headers=_h(tok)).status_code == 200
    est = client.get(f"{BASE}/jobs/{jid}", headers=_h(tok)).json()
    assert est["status"] == "failed"
    assert "debe" in (est["error_message"] or "").lower()

    # 2) Mapear a mano débito/haber (en 'failed' se admite).
    r = client.put(
        f"{BASE}/jobs/{jid}/slots/mayor_especifico/mapeo?nombre=raro.xlsx",
        headers=_h(tok),
        json={"mapeo": {"codigo": 0, "cuenta": 1, "fecha": 2, "debe": 4, "haber": 5}},
    )
    assert r.status_code == 200, r.text

    # 3) Volver a Procesar → ahora se lee y pasa a 'revision'.
    assert client.post(f"{BASE}/jobs/{jid}/procesar", headers=_h(tok)).status_code == 200
    est = client.get(f"{BASE}/jobs/{jid}", headers=_h(tok)).json()
    assert est["status"] == "revision", est
    clasif = client.get(f"{BASE}/jobs/{jid}/clasificacion", headers=_h(tok)).json()
    assert "1.1.5.1.1" in {c["codigo_cuenta"] for c in clasif["cuentas"]}


def test_reemplazar_un_mayor_que_dio_error(client):
    """③ Reemplazar: borrar el mayor ilegible (en 'failed') y subir uno bueno."""
    tok, jid = _crear_borrador(client)
    _subir_ilegible(client, tok, jid)
    assert client.post(f"{BASE}/jobs/{jid}/procesar", headers=_h(tok)).status_code == 200
    assert client.get(f"{BASE}/jobs/{jid}", headers=_h(tok)).json()["status"] == "failed"

    # Borrar el ilegible (permitido en 'failed').
    rd = client.delete(
        f"{BASE}/jobs/{jid}/slots/mayor_especifico?nombre=raro.xlsx", headers=_h(tok),
    )
    assert rd.status_code == 200, rd.text
    assert rd.json()["mayor_especifico"]["n_archivos"] == 0

    # Subir uno legible con el encabezado estándar y procesar.
    buena = [["1.1.5.1.1", "IVA sobre Compras", "2025-01-05", "A1",
              "", "", "", "", "", 10.0, 0, 10.0]]
    client.put(
        f"{BASE}/jobs/{jid}/slots/mayor_especifico", headers=_h(tok),
        files=[("archivos", ("buena.xlsx", io.BytesIO(mayor_xlsx(buena)), XLSX_MIME))],
        data={"categoria": "IVA_COMPRAS"},
    )
    assert client.post(f"{BASE}/jobs/{jid}/procesar", headers=_h(tok)).status_code == 200
    assert client.get(f"{BASE}/jobs/{jid}", headers=_h(tok)).json()["status"] == "revision"


def test_borrar_el_mayor_limpia_su_mapeo_de_columnas(client):
    tok, jid = _crear_borrador(client)
    _subir_ilegible(client, tok, jid)
    client.put(
        f"{BASE}/jobs/{jid}/slots/mayor_especifico/mapeo?nombre=raro.xlsx",
        headers=_h(tok), json={"mapeo": {"codigo": 0, "debe": 4, "haber": 5}},
    )
    client.delete(
        f"{BASE}/jobs/{jid}/slots/mayor_especifico?nombre=raro.xlsx", headers=_h(tok),
    )
    # Vuelvo a subir el mismo nombre: no debe arrastrar el mapeo viejo.
    _subir_ilegible(client, tok, jid)
    info = client.get(
        f"{BASE}/jobs/{jid}/slots/mayor_especifico/encabezados?nombre=raro.xlsx",
        headers=_h(tok),
    ).json()
    assert info["mapeo_manual"] == {}
