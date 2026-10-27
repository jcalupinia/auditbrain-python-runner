"""Conciliación y no-duplicados de la ingesta masiva (solo SQLite temporal; no toca Hetzner).

Cubre dos escenarios de la validación del preview #392 que el resto del suite no verificaba
explícitamente:
  - No-duplicados dentro de un mismo dataset: la UniqueConstraint(dataset_id, numero_fila) impide
    dos filas con el mismo número dentro del dataset.
  - Conciliación de débitos y créditos: la suma de debe/haber persistida coincide exactamente con
    los movimientos del archivo (sin pérdida ni duplicación).
"""
import csv
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from backend.app.ingesta.ingesta_masiva import (
    crear_tablas, datasets, filas, ingerir_archivo, consultar_filas,
)


def _engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'conciliacion.db'}")
    crear_tablas(engine)
    return engine


def _mayor(tmp_path, movimientos):
    ruta = tmp_path / "mayor.csv"
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cuenta", "fecha", "debe", "haber"])
        for cuenta, debe, haber in movimientos:
            w.writerow([cuenta, "2026-10-26", debe, haber])
    return ruta


def test_unique_constraint_impide_duplicados_en_el_dataset(tmp_path):
    engine = _engine(tmp_path)
    with engine.begin() as conn:
        import datetime as dt
        conn.execute(datasets.insert().values(
            id="d1", cliente_id="c", encargo_id="e", periodo="2026", tipo_documento="mayor",
            archivo="x.csv", sha256_archivo="0" * 64, estado="completado",
            total_filas=1, filas_revision=0, creado_en=dt.datetime.now(dt.timezone.utc),
        ))
        conn.execute(filas.insert().values(dataset_id="d1", numero_fila=1, datos={}, errores=[]))
    # La misma (dataset_id, numero_fila) no puede repetirse dentro del dataset.
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(filas.insert().values(dataset_id="d1", numero_fila=1, datos={}, errores=[]))


def test_concilia_debitos_y_creditos_sin_perdida(tmp_path):
    engine = _engine(tmp_path)
    movimientos = [("110101", "100.00", "0.00"), ("110102", "0.00", "40.50"), ("110103", "25.25", "0.00")]
    ruta = _mayor(tmp_path, movimientos)
    r = ingerir_archivo(
        engine, ruta, cliente_id="clienteA", encargo_id="2026", periodo="2026",
        tipo_documento="mayor", mapeo_confirmado={"cuenta": 0, "fecha": 1, "debe": 2, "haber": 3},
        saltar_filas=1,
    )
    assert r["total_filas"] == 3 and r["filas_revision"] == 0
    leidas = consultar_filas(engine, r["dataset_id"], cliente_id="clienteA", encargo_id="2026", limite=1000)
    assert len(leidas) == 3  # ni pérdida ni duplicación
    suma_debe = sum(Decimal(str(f["datos"]["debe"])) for f in leidas)
    suma_haber = sum(Decimal(str(f["datos"]["haber"])) for f in leidas)
    assert suma_debe == Decimal("125.25")
    assert suma_haber == Decimal("40.50")
