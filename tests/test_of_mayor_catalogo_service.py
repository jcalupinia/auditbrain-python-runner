"""Semilla y consulta del catálogo de categorías."""

import pytest

from backend.app.aud.obligaciones_fiscales.mayor.catalogo_service import (
    categorias_visibles,
    sembrar_categorias_de_sistema,
)
from backend.app.aud.obligaciones_fiscales.mayor.models import MayorCategoria
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def test_la_semilla_crea_las_siete_categorias_de_sistema():
    db = SessionLocal()
    try:
        sembrar_categorias_de_sistema(db)
        n = db.query(MayorCategoria).filter_by(es_sistema=True).count()
        assert n == 7
    finally:
        db.close()


def test_sembrar_dos_veces_no_duplica():
    db = SessionLocal()
    try:
        sembrar_categorias_de_sistema(db)
        sembrar_categorias_de_sistema(db)
        n = db.query(MayorCategoria).filter_by(es_sistema=True).count()
        assert n == 7
    finally:
        db.close()


def test_una_organizacion_ve_las_de_sistema_mas_las_suyas():
    db = SessionLocal()
    try:
        sembrar_categorias_de_sistema(db)
        db.add(MayorCategoria(organization_id=777, codigo="ICE", nombre="ICE",
                              naturaleza_esperada="pasivo", orden=8))
        db.commit()
        codigos = {c.codigo for c in categorias_visibles(db, organization_id=777)}
        assert "ICE" in codigos
        assert "IVA_COMPRAS" in codigos
        otra = {c.codigo for c in categorias_visibles(db, organization_id=888)}
        assert "ICE" not in otra
    finally:
        db.close()


def test_las_categorias_inactivas_no_se_listan():
    db = SessionLocal()
    try:
        sembrar_categorias_de_sistema(db)
        db.add(MayorCategoria(organization_id=999, codigo="VIEJA", nombre="Vieja",
                              naturaleza_esperada="pasivo", orden=9, activa=False))
        db.commit()
        codigos = {c.codigo for c in categorias_visibles(db, organization_id=999)}
        assert "VIEJA" not in codigos
    finally:
        db.close()
