"""V4 — un archivo que no se puede abrir responde 400, nunca 500.

POR QUÉ EXISTE. La pantalla ofrecía `accept=".xlsx,.xls,.csv"` y el lector solo
sabe abrir `.xlsx` (`openpyxl.load_workbook`). Los tres formatos que la propia
pantalla ofrecía terminaban en `zipfile.BadZipFile`, que no es `ValueError`, así
que escapaba del handler del router y salía por el 500 genérico: el auditor
subía tres archivos y recibía un error sin una sola instrucción.

LA DECISIÓN. La herramienta lee `.xlsx` y solo `.xlsx`. Aceptar `.xls` de verdad
exigiría una dependencia nueva (`xlrd`), que esta rama no puede añadir, y
aceptar `.csv` cambiaría el perfil de memoria con el que está calibrado el
límite por archivo. Así que la pantalla deja de ofrecer lo que el backend no
lee, y cualquier archivo ilegible -formato antiguo, csv, xlsx dañado o
protegido con contraseña- responde 400 diciendo qué hacer.
"""
from __future__ import annotations

import io
import json
import uuid
from datetime import date

import pytest
from openpyxl import Workbook

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal, init_db

BASE = "/api/v1/aud/pce-cxc"


def _xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Cliente", "Documento", "Tipo", "Emisión", "Vencimiento", "Saldo"])
    ws.append(["ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


#: Un .csv de verdad: lo que un ERP exporta por defecto.
CSV = ("Cliente,Documento,Tipo,Emisión,Vencimiento,Saldo\n"
       "ALFA,F-1,NO-RELACIONADOS,01/09/2023,01/12/2023,100000.00\n").encode("utf-8")

#: La cabecera del formato binario antiguo de Excel (BIFF/OLE2).
XLS = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512

#: Un .xlsx con el nombre correcto y el contenido roto.
XLSX_CORRUPTO = b"PK\x03\x04" + b"basura que no es un zip valido" * 10


def _token(client, role=Role.user):
    init_db()
    tag = uuid.uuid4().hex[:6]
    email, pw = f"pce-ileg-{tag}@ex.com", "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=role)
    finally:
        db.close()
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    return r.json()["access_token"]


@pytest.mark.parametrize("nombre,contenido", [
    ("cartera_2025.csv", CSV),
    ("cartera_2025.xls", XLS),
    ("cartera_2025.xlsx", XLSX_CORRUPTO),
])
def test_un_archivo_que_no_se_puede_abrir_responde_400_accionable(client, nombre, contenido):
    """Los tres casos que la revisión reprodujo contra el endpoint real."""
    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=[
        ("archivos", ("cartera_2023.xlsx", _xlsx())),
        ("archivos", ("cartera_2024.xlsx", _xlsx())),
        ("archivos", (nombre, contenido))],
        data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"]})},
        headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400, f"se esperaba 400, se obtuvo {r.status_code}: {r.text[:300]}"
    detalle = r.json()["detail"]
    # Accionable: nombra el archivo y dice qué hacer con él.
    assert nombre in detalle, detalle
    assert ".xlsx" in detalle, detalle
    assert "guarde" in detalle.lower() or "guárdelo" in detalle.lower(), detalle


def test_el_mensaje_del_csv_dice_que_lo_convierta(client):
    """Cada formato con su instrucción: un .csv no es un libro dañado."""
    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=[
        ("archivos", ("cartera_2023.csv", CSV)),
        ("archivos", ("cartera_2024.xlsx", _xlsx())),
        ("archivos", ("cartera_2025.xlsx", _xlsx()))],
        data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"]})},
        headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400, r.text
    detalle = r.json()["detail"]
    assert "csv" in detalle.lower(), detalle


def test_una_hoja_que_no_existe_tambien_es_400(client):
    """El otro camino por el que el lector levantaba una excepción que no es
    `ValueError`: pedir una hoja que el libro no tiene."""
    from backend.app.aud.pce_cxc.bandas import BANDAS_POR_DEFECTO, desdoblar
    from backend.app.aud.pce_cxc.lectura import leer_cartera

    bandas = desdoblar(BANDAS_POR_DEFECTO, 730)
    with pytest.raises(ValueError, match="hoja"):
        leer_cartera(_xlsx(), "cartera_2025.xlsx", date(2025, 12, 31), bandas,
                     hoja="Hoja que no existe")
