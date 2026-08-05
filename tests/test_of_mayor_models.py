"""Persistencia del motor de mayores: catálogo, homologaciones y clasificación."""

import pytest
from sqlalchemy import inspect

from backend.app.aud.obligaciones_fiscales.mayor.models import (
    MayorCategoria,
    MayorClasificacionJob,
    MayorHomologacion,
)
from backend.app.db.session import SessionLocal, engine, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def test_las_tres_tablas_se_crean_con_init_db():
    tablas = set(inspect(engine).get_table_names())
    assert {"mayor_categorias", "mayor_homologaciones", "mayor_clasificacion_job"} <= tablas


def test_una_homologacion_es_unica_por_cliente_y_codigo_de_cuenta():
    db = SessionLocal()
    try:
        db.add(MayorHomologacion(client_id=1, codigo_cuenta="1.1.5.1.1",
                                 nombre_norm="iva sobre compras", categoria="IVA_COMPRAS"))
        db.commit()
        db.add(MayorHomologacion(client_id=1, codigo_cuenta="1.1.5.1.1",
                                 nombre_norm="otro", categoria="VENTAS"))
        with pytest.raises(Exception):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_el_mismo_codigo_puede_existir_para_otro_cliente():
    db = SessionLocal()
    try:
        db.add(MayorHomologacion(client_id=101, codigo_cuenta="4.1.1.1",
                                 nombre_norm="ventas", categoria="VENTAS"))
        db.add(MayorHomologacion(client_id=102, codigo_cuenta="4.1.1.1",
                                 nombre_norm="ventas", categoria="VENTAS"))
        db.commit()
        n = db.query(MayorHomologacion).filter_by(codigo_cuenta="4.1.1.1").count()
        assert n == 2
    finally:
        db.rollback()
        db.close()


def test_la_clasificacion_de_un_job_guarda_las_senales_como_json():
    db = SessionLocal()
    try:
        fila = MayorClasificacionJob(
            job_id=1, codigo_cuenta="2.1.7.3.2", nombre_cuenta="Ret. 70% Servicios",
            categoria_sugerida="RET_IVA", categoria_final="RET_IVA", tarifa=70.0,
            confianza="alta", origen="reglas",
            senales_json=[{"categoria": "RET_IVA", "puntaje": 40, "motivo": "por nombre"}],
        )
        db.add(fila)
        db.commit()
        leida = db.query(MayorClasificacionJob).filter_by(job_id=1).one()
        assert leida.senales_json[0]["puntaje"] == 40
        assert leida.tarifa == 70.0
    finally:
        db.rollback()
        db.close()


def test_una_categoria_de_sistema_no_pertenece_a_ninguna_organizacion():
    """La semilla es global; una organización puede añadir las suyas."""
    cat = MayorCategoria(codigo="IVA_COMPRAS", nombre="IVA en compras",
                         naturaleza_esperada="activo", orden=1, es_sistema=True)
    assert cat.organization_id is None
