"""Pruebas reproducibles, solo SQLite temporal: NO acceden a Hetzner."""
import csv
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, func

from backend.app.ingesta.ingesta_masiva import (
    crear_tablas, ingerir_archivo, consultar_filas, filas, datasets,
)


def _setup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'prueba.db'}")
    crear_tablas(engine)
    return engine


def _archivo(tmp_path, n):
    ruta = tmp_path / "mayor.csv"
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cuenta", "fecha", "debe", "haber"])
        for i in range(n):
            w.writerow(["110101", "2026-10-25", "1.25", "0.25"])
    return ruta


def _ingesta(engine, ruta, **kwargs):
    return ingerir_archivo(
        engine, ruta, cliente_id="clienteA", encargo_id="audit2026",
        periodo="2026", tipo_documento="mayor",
        mapeo_confirmado={"cuenta": 0, "fecha": 1, "debe": 2, "haber": 3},
        lote=2000, **kwargs
    )


@pytest.mark.parametrize("n", [0, 1, 34000, 100001])
def test_persistencia_y_conteos(tmp_path, n):
    engine = _setup(tmp_path)
    ruta = _archivo(tmp_path, n)
    res = _ingesta(engine, ruta)
    assert res["total_filas"] == n
    assert res["filas_revision"] == 0
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(filas)) == n
        assert conn.scalar(select(datasets.c.estado)) == "completado"
    if n:
        pagina = consultar_filas(engine, res["dataset_id"],
            cliente_id="clienteA", encargo_id="audit2026", limite=3)
        assert pagina[0]["datos"]["debe"] == "1.25"
        assert len(pagina) == min(3, n)
        with pytest.raises(LookupError):
            consultar_filas(engine, res["dataset_id"],
                cliente_id="otro", encargo_id="audit2026")


def test_vacio_obligatorio_a_revision(tmp_path):
    engine = _setup(tmp_path)
    ruta = _archivo(tmp_path, 0)
    with ruta.open("a", encoding="utf-8") as fh:
        fh.write("110101,2026-10-25,,0.25\n")
    res = _ingesta(engine, ruta)
    assert res["filas_revision"] == 1
    fila = consultar_filas(engine, res["dataset_id"],
        cliente_id="clienteA", encargo_id="audit2026")[0]
    assert fila["datos"]["debe"] is None
    assert fila["errores"]


def test_no_crea_tablas_automaticamente(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'vacia.db'}")
    from sqlalchemy import inspect
    assert "ingesta_masiva_datasets" not in inspect(engine).get_table_names()
