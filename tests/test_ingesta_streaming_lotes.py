"""Pruebas reproducibles del lector incremental aislado.

Ejecutar: pytest -q tests/test_ingesta_streaming_lotes.py
"""
import csv

import pytest

from backend.app.ingesta.streaming_lotes import iterar_lotes


@pytest.mark.parametrize("cantidad,lote", [(0, 2000), (1, 2000), (34000, 2000), (100001, 5000)])
def test_csv_conserva_filas_y_limita_lotes(tmp_path, cantidad, lote):
    ruta = tmp_path / "mayor.csv"
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        for i in range(cantidad):
            w.writerow([i, "110101", "1.25", "0"])
    total = 0
    maximo = 0
    for bloque in iterar_lotes(ruta, lote=lote):
        total += len(bloque)
        maximo = max(maximo, len(bloque))
    assert total == cantidad
    assert maximo <= lote


def test_xlsx_lectura_incremental(tmp_path):
    from openpyxl import Workbook
    ruta = tmp_path / "mayor.xlsx"
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Mayor")
    for i in range(12001):
        ws.append([i, "110101", 1.25])
    wb.save(ruta)
    lotes = list(iterar_lotes(ruta, lote=5000))
    assert [len(x) for x in lotes] == [5000, 5000, 2001]
    assert lotes[0][0][0] == 0


@pytest.mark.parametrize("lote", [0, -1, 10001])
def test_rechaza_lotes_invalidos(tmp_path, lote):
    ruta = tmp_path / "vacio.csv"
    ruta.write_text("")
    with pytest.raises(ValueError):
        list(iterar_lotes(ruta, lote=lote))
