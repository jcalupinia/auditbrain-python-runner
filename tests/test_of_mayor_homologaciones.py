"""Historial de homologaciones: lo que el auditor confirmó, por cliente."""

import pytest

from backend.app.aud.obligaciones_fiscales.mayor.homologaciones import (
    guardar_homologaciones,
    historial_de_cliente,
)
from backend.app.aud.obligaciones_fiscales.mayor.models import MayorHomologacion
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def test_un_cliente_sin_historial_devuelve_diccionario_vacio():
    db = SessionLocal()
    try:
        assert historial_de_cliente(db, client_id=4242) == {}
    finally:
        db.close()


def test_guardar_y_recuperar_el_historial_como_diccionario():
    db = SessionLocal()
    try:
        guardar_homologaciones(
            db,
            client_id=4243,
            asignaciones=[
                {"codigo_cuenta": "1.1.5.1.1", "nombre_cuenta": "IVA sobre Compras",
                 "categoria": "IVA_COMPRAS", "tarifa": None},
                {"codigo_cuenta": "2.1.7.3.2", "nombre_cuenta": "Ret. 70% Servicios",
                 "categoria": "RET_IVA", "tarifa": 70.0},
            ],
            user_id=1,
        )
        assert historial_de_cliente(db, client_id=4243) == {
            "1.1.5.1.1": "IVA_COMPRAS",
            "2.1.7.3.2": "RET_IVA",
        }
    finally:
        db.close()


def test_guardar_la_misma_cuenta_otra_vez_actualiza_y_cuenta_el_uso():
    db = SessionLocal()
    try:
        # Limpieza previa: la base de dev es persistente entre corridas de pytest.
        db.query(MayorHomologacion).filter_by(client_id=4244, codigo_cuenta="4.1.1.4").delete()
        db.commit()
        datos = [{"codigo_cuenta": "4.1.1.4", "nombre_cuenta": "Venta insumos",
                  "categoria": "VENTAS", "tarifa": None}]
        guardar_homologaciones(db, client_id=4244, asignaciones=datos, user_id=1)
        guardar_homologaciones(db, client_id=4244, asignaciones=datos, user_id=1)
        fila = db.query(MayorHomologacion).filter_by(
            client_id=4244, codigo_cuenta="4.1.1.4"
        ).one()
        assert fila.veces_usada == 2


        # y si el auditor cambia de opinión, la categoría se actualiza
        guardar_homologaciones(
            db, client_id=4244,
            asignaciones=[{"codigo_cuenta": "4.1.1.4", "nombre_cuenta": "Venta insumos",
                           "categoria": "IVA_VENTAS", "tarifa": None}],
            user_id=1,
        )
        db.expire_all()
        fila = db.query(MayorHomologacion).filter_by(
            client_id=4244, codigo_cuenta="4.1.1.4"
        ).one()
        assert fila.categoria == "IVA_VENTAS"
        assert fila.veces_usada == 3
    finally:
        db.query(MayorHomologacion).filter_by(client_id=4244, codigo_cuenta="4.1.1.4").delete()
        db.commit()
        db.close()


def test_el_historial_de_un_cliente_no_contamina_al_de_otro():
    db = SessionLocal()
    try:
        guardar_homologaciones(
            db, client_id=4245,
            asignaciones=[{"codigo_cuenta": "1.1.5.1.1", "nombre_cuenta": "x",
                           "categoria": "IVA_COMPRAS", "tarifa": None}],
            user_id=1,
        )
        assert historial_de_cliente(db, client_id=4246) == {}
    finally:
        db.close()


def test_una_asignacion_sin_categoria_se_ignora():
    """El auditor puede dejar una cuenta sin resolver."""
    db = SessionLocal()
    try:
        guardar_homologaciones(
            db, client_id=4247,
            asignaciones=[{"codigo_cuenta": "9.9", "nombre_cuenta": "?",
                           "categoria": None, "tarifa": None}],
            user_id=1,
        )
        assert historial_de_cliente(db, client_id=4247) == {}
    finally:
        db.close()
