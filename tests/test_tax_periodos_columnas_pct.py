"""Regresión: columnas de análisis vertical/horizontal NO son períodos.

Bug real (archivos ESF/ERI SIGMANSERVICE): los encabezados intercalan columnas
de ratio como "% 2023 / Total Activos", "% 2024 / Ventas". El detector de
períodos las tomaba como períodos anuales (por el año embebido en el texto),
duplicando las columnas y metiendo ratios (0.96, 0.28…) como si fueran datos.

Un encabezado de período es una FECHA o una ETIQUETA DE AÑO, nunca una columna
de porcentaje/variación que apenas MENCIONA un año.
"""
import datetime as dt

from backend.app.tax.planificacion_utilidades.parsers.balance_interno import (
    _period_label,
    _detect_periods,
)
import pandas as pd


def test_pct_column_no_es_periodo():
    assert _period_label("% 2023 / Total Activos") is None
    assert _period_label("% 2024 / Ventas") is None
    assert _period_label("% 2026 / Ventas") is None


def test_variacion_y_porcentaje_no_son_periodo():
    assert _period_label("Variación") is None
    assert _period_label("Porcentaje") is None
    # Variación que menciona un año tampoco es un período.
    assert _period_label("Variación 2024") is None


def test_fecha_y_anio_limpio_si_son_periodo():
    # Fecha real (datetime) -> período con día/mes.
    assert _period_label(dt.datetime(2026, 5, 31)) == ("31-may-2026", 2026)
    # ISO string.
    assert _period_label("2023-12-31") == ("31-dic-2023", 2023)
    # Año pelado o etiqueta simple de año -> sí es período.
    assert _period_label("2023") == ("2023", 2023)
    assert _period_label("Año 2025") == ("2025", 2025)


def test_detect_periods_ignora_columnas_pct():
    # Fila de encabezado como la real: fecha + su columna de %, intercaladas.
    row = pd.Series([
        "Codigo", "Cuenta",
        dt.datetime(2023, 12, 31), "% 2023 / Total Activos",
        dt.datetime(2024, 12, 31), "% 2024 / Total Activos",
        dt.datetime(2026, 5, 31), "% 2026 / Total Activos",
    ])
    periods = _detect_periods(row)  # cada item: (col_index, label, year)
    # Debe detectar SOLO las 3 fechas (cols 2,4,6), no las 3 columnas de % (3,5,7).
    assert [p[0] for p in periods] == [2, 4, 6]
    assert [p[1] for p in periods] == ["31-dic-2023", "31-dic-2024", "31-may-2026"]
    assert [p[2] for p in periods] == [2023, 2024, 2026]
