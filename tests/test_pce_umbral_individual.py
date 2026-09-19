"""V9 — el umbral de evaluación individual valida su signo y su magnitud.

POR QUÉ EXISTE. `umbral_individual` entraba como número y nada más: `_pendientes`
solo lo reclama cuando es falsy. Con `1` o `−1` TODOS los clientes salen de la
matriz colectiva y pasan a evaluación individual -sobre los archivos de prueba,
de 2 casos a 7-, y sobre un archivo real eso es una fila de `06-Individual` y un
diccionario en el JSON guardado POR CADA CLIENTE, contra un techo de memoria de
250 MB por petición.

Un umbral negativo no tiene lectura: el umbral separa los saldos relevantes, y
no existe un saldo relevante por ser menor que −1. Y un umbral positivo pero
absurdamente bajo tampoco: convierte la matriz colectiva en un listado, que es
justo lo contrario de lo que el método de la matriz de provisiones hace. Los dos
se rechazan con un 400 que dice qué pasó y qué corregir.
"""
from __future__ import annotations

import io
from datetime import date

import pytest
from openpyxl import Workbook

from backend.app.aud.pce_cxc import service

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


def _filas(n: int, saldo: float = 10000.0):
    return [(f"CLIENTE {i:04d}", f"F-{i}", "NO-RELACIONADOS",
             date(2019, 1, 1), date(2020, 1, 1), saldo) for i in range(n)]


def _cortes(n: int = 3):
    return [{"nombre": f"cartera_{f.year}.xlsx", "contenido": _xlsx(_filas(n)), "fecha": f}
            for f in (date(2023, 12, 31), date(2024, 12, 31), date(2025, 12, 31))]


@pytest.mark.parametrize("umbral", [-1, -100000.0])
def test_un_umbral_negativo_se_rechaza(umbral):
    """Con un umbral negativo TODO cliente lo supera: la matriz colectiva
    desaparece sin que nadie lo haya pedido."""
    with pytest.raises(ValueError, match="umbral_individual"):
        service.analizar(_cortes(), {"umbral_individual": umbral})


def test_un_umbral_que_saca_a_todos_de_la_matriz_se_rechaza():
    """Un umbral de 1 sobre saldos de 10.000 manda a los 600 clientes a
    `06-Individual`: una fila y un diccionario por cliente contra el techo de
    memoria de la petición."""
    with pytest.raises(ValueError, match="evaluación individual"):
        service.analizar(_cortes(600), {"umbral_individual": 1})


def test_el_mensaje_dice_cuantos_casos_salieron_y_cual_es_el_limite():
    """Accionable: el auditor tiene que poder subir el umbral con criterio."""
    try:
        service.analizar(_cortes(600), {"umbral_individual": 1})
    except ValueError as e:
        mensaje = str(e)
    else:
        pytest.fail("no se rechazó el umbral")
    assert str(service.MAX_CASOS_INDIVIDUALES) in mensaje, mensaje
    assert "600" in mensaje, mensaje
    assert "umbral" in mensaje.lower(), mensaje


def test_un_umbral_razonable_sigue_calculando():
    """La guarda no puede estorbar al camino bueno: con 400 clientes de 10.000
    y un umbral de 100.000 no sale ningún caso individual."""
    resultado = service.analizar(_cortes(400), {"umbral_individual": 100000})
    assert resultado["individual"]["casos"] == []


def test_sin_umbral_sigue_siendo_un_pendiente_y_no_un_error():
    """Cero o ausente significa «no lo declaró el socio», que es un pendiente
    del papel desde siempre, no un error de entrada."""
    for umbral in (0, None, ""):
        resultado = service.analizar(_cortes(), {"umbral_individual": umbral})
        variables = [p["variable"] for p in resultado["pendientes"]]
        assert "Umbral de evaluación individual" in variables, (umbral, variables)


def test_el_endpoint_lo_traduce_a_400(client):
    """De punta a punta: el auditor recibe un 400 accionable, no un 500 ni una
    corrida de cientos de casos individuales."""
    import json
    import uuid

    from backend.app.auth import service as auth_service
    from backend.app.auth.models import Role
    from backend.app.db.session import SessionLocal, init_db

    init_db()
    tag = uuid.uuid4().hex[:6]
    email, pw = f"pce-umb-{tag}@ex.com", "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=Role.user)
    finally:
        db.close()
    token = client.post("/api/v1/auth/login",
                        data={"username": email, "password": pw}).json()["access_token"]

    contenido = _xlsx(_filas(3))
    r = client.post(f"{BASE}/analizar", files=[
        ("archivos", ("cartera_2023.xlsx", contenido)),
        ("archivos", ("cartera_2024.xlsx", contenido)),
        ("archivos", ("cartera_2025.xlsx", contenido))],
        data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"],
                                        "umbral_individual": -1})},
        headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400, f"se esperaba 400, se obtuvo {r.status_code}: {r.text[:300]}"
    assert "umbral_individual" in r.json()["detail"]
