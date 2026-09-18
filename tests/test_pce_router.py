"""Endpoints de la herramienta de pérdidas esperadas (AUD, require_staff)."""
import io
import json
import uuid
from datetime import date

from openpyxl import Workbook

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal, init_db

BASE = "/api/v1/aud/pce-cxc"


def _xlsx(filas):
    wb = Workbook()
    ws = wb.active
    ws.append(["Cliente", "Documento", "Tipo", "Emisión", "Vencimiento", "Saldo"])
    for f in filas:
        ws.append(list(f))
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _archivos():
    c23 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0)])
    c24 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 20000.0)])
    c25 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 10000.0)])
    return [("archivos", ("2023.xlsx", c23)), ("archivos", ("2024.xlsx", c24)),
            ("archivos", ("2025.xlsx", c25))]


def _token(client, role=Role.user):
    init_db()
    tag = uuid.uuid4().hex[:6]
    email, pw = f"pce-{tag}@ex.com", "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=role)
    finally:
        db.close()
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    return r.json()["access_token"]


def test_sin_rol_staff_no_se_puede_calcular(client):
    # El repo solo tiene tres roles: admin, user y client (Role.staff no existe).
    # admin y user SON staff para require_staff; el único rol no-staff es
    # "client" (portal del cliente), y ese lo rechaza get_current_user en
    # defensa en profundidad antes de llegar al chequeo de rol de
    # require_staff ("client-role JWTs must NEVER pass through staff
    # dependencies"), así que la respuesta es 401, no 403. Lo que importa acá
    # es que el cálculo NO se ejecute para un usuario de portal cliente.
    token = _token(client, Role.client)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"]})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (401, 403), r.text


def test_calcula_y_guarda_la_corrida(client):
    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"],
                                                    "entidad": "PRUEBA S.A."})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["corrida_id"]
    assert cuerpo["ecl_total"] >= 0
    g = client.get(f"{BASE}/corridas/{cuerpo['corrida_id']}", headers={"Authorization": f"Bearer {token}"})
    assert g.status_code == 200
    assert g.json()["resultado"]["ecl_total"] == cuerpo["ecl_total"]


def test_exige_los_tres_cortes(client):
    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=_archivos()[:2],
                    data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31"]})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
    assert "tres" in r.json()["detail"].lower()
