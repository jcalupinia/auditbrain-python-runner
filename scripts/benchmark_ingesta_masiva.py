"""Benchmark reproducible de ingesta por bloques, con base SQLite temporal.

Ejemplo:
  python scripts/benchmark_ingesta_masiva.py --filas 100000 --lote 2000
  python scripts/benchmark_ingesta_masiva.py --filas 500000 --lote 2000

No conecta con produccion ni usa credenciales. Reporta RAM RSS pico del
proceso, integridad de filas, sumas exactas y tiempo transcurrido.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import resource
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select, func

from backend.app.ingesta.ingesta_masiva import (
    crear_tablas, datasets, filas, ingerir_archivo,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--filas", type=int, default=100000)
    parser.add_argument("--lote", type=int, default=2000)
    parser.add_argument("--limite-rss-mb", type=float, default=None)
    args = parser.parse_args()
    if not 0 <= args.filas <= 2_000_000:
        parser.error("--filas debe estar entre 0 y 2000000")
    if not 1 <= args.lote <= 10000:
        parser.error("--lote debe estar entre 1 y 10000")
    with tempfile.TemporaryDirectory(prefix="auditbrain-ingesta-bench-") as d:
        ruta = Path(d) / "mayor.csv"
        with ruta.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["cuenta", "fecha", "debe", "haber"])
            for n in range(args.filas):
                w.writerow(["110101", "2026-10-25", "1.25", "0.25"])
        engine = create_engine(f"sqlite:///{Path(d) / 'ingesta.db'}")
        crear_tablas(engine)
        inicio = time.perf_counter()
        resultado = ingerir_archivo(
            engine, ruta, cliente_id="benchmark", encargo_id="aislado",
            periodo="2026", tipo_documento="mayor",
            mapeo_confirmado={"cuenta": 0, "fecha": 1, "debe": 2, "haber": 3},
            lote=args.lote,
        )
        duracion = round(time.perf_counter() - inicio, 3)
        with engine.connect() as conn:
            conteo = conn.scalar(select(func.count()).select_from(filas))
            estado = conn.scalar(select(datasets.c.estado))
            # Streaming de lectura: no materializar las filas consultadas.
            suma_debe = Decimal("0")
            suma_haber = Decimal("0")
            consulta = conn.execution_options(stream_results=True).execute(
                select(filas.c.datos).where(
                    filas.c.dataset_id == resultado["dataset_id"]
                )
            )
            for (datos,) in consulta:
                suma_debe += Decimal(datos["debe"])
                suma_haber += Decimal(datos["haber"])
        # Linux ru_maxrss es KiB; el benchmark esta orientado a runners Linux.
        rss_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)
        esperado_debe = Decimal(args.filas) * Decimal("1.25")
        esperado_haber = Decimal(args.filas) * Decimal("0.25")
        ok = (conteo == args.filas == resultado["total_filas"]
              and suma_debe == esperado_debe and suma_haber == esperado_haber
              and estado == "completado" and resultado["filas_revision"] == 0)
        memoria_ok = args.limite_rss_mb is None or rss_mb <= args.limite_rss_mb
        print(json.dumps({
            "filas_esperadas": args.filas, "filas_persistidas": conteo,
            "suma_debe": str(suma_debe), "suma_haber": str(suma_haber),
            "duracion_segundos": duracion, "rss_pico_mb": rss_mb,
            "integridad_ok": ok, "memoria_dentro_limite": memoria_ok,
            "tipo_bd": "sqlite-temporal",
        }, ensure_ascii=False, indent=2))
        return 0 if ok and memoria_ok else 1


if __name__ == "__main__":
    sys.exit(main())
