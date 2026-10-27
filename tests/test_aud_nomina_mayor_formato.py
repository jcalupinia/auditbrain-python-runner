# -*- coding: utf-8 -*-
"""Lector tolerante al formato del Mayor de nómina (`nomina/mayores.py::_read_tabla`).

Antes el motor exigía los encabezados exactos del encargo de referencia
(`Fecha L/M`, `Nºcuenta`, `Importe`, …) y un `Importe` con signo en una sola columna;
un Mayor de otro cliente (p. ej. `Código`, `Fecha`, `Debe`, `Haber`, `Saldo`) reventaba con
`KeyError: 'Fecha L/M'`. Ahora `_read_tabla` detecta la fila de encabezados, mapea por
sinónimos y deriva `Importe = Debe − Haber`, conservando las columnas originales. Si falta
una columna esencial, da un mensaje claro en español en vez del KeyError."""
import os
import tempfile

import pandas as pd
import pytest

from backend.app.aud.niif.procesadores.nomina import mayores as MY

_EJ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "frontend", "public", "ejemplos", "nomina_beneficios")


def _xlsx(df, **kw):
    ruta = os.path.join(tempfile.mkdtemp(), "mayor.xlsx")
    df.to_excel(ruta, index=False, **kw)
    return ruta


@pytest.mark.parametrize("nombre", [
    "RQ-004_mayor_de_gasto_de_nomina.xlsx",
    "RQ-004_mayor_de_iess_por_pagar.xlsx",
    "RQ-004_mayor_de_beneficios_sociales_por_pagar.xlsx",
])
def test_formato_de_referencia_se_lee_igual(nombre):
    """Regresión: el formato del encargo de referencia se lee idéntico (mismas filas, mismo
    Σimporte) y conserva columnas extra como 'Nombre alfa explicación'."""
    ruta = os.path.join(_EJ, nombre)
    if not os.path.exists(ruta):
        pytest.skip("ejemplo no disponible")
    leido = MY._load(ruta)
    orig = pd.read_excel(ruta)
    assert len(leido) == len(orig)
    assert abs(leido["Importe"].sum() - orig["Importe"].sum()) < 1e-6
    for c in ("Fecha L/M", "Nºcuenta", "Descripción", "Importe", "Explicación -observación-", "REF"):
        assert c in leido.columns
    assert "Nombre alfa explicación" in leido.columns  # columna extra conservada


def test_formato_distinto_codigo_fecha_debe_haber():
    """Un Mayor con otros encabezados (Código/Fecha/Debe/Haber/Saldo) se mapea a las columnas
    canónicas y el Importe sale de Debe − Haber (débito +, crédito −). 'Saldo' NO es el importe."""
    cols = ["Código", "Cuenta", "Fecha", "Centro de Costo", "Documento",
            "Descripción", "Debe", "Haber", "Saldo"]
    filas = [
        ["5PYG.01", "Sueldos", "15/01/2025", "CC1", "D1", "Sueldos enero", 1000, 0, 1000],
        ["5PYG.01", "Sueldos", "10/02/2025", "CC1", "D2", "Ajuste", 0, 200, 800],
        ["5BS.21203.001", "IESS", "20/01/2025", "CC1", "D3", "Aporte patronal", 0, 150, -150],
    ]
    d = MY._load(_xlsx(pd.DataFrame(filas, columns=cols)))
    assert list(d["Importe"]) == [1000, -200, -150]      # Debe − Haber, no el Saldo
    assert list(d["cta"]) == ["5PYG.01", "5PYG.01", "5BS.21203.001"]
    assert list(d["m"]) == [1, 2, 1]
    # sin columnas de clasificación, la descripción hace de respaldo
    assert list(d["Explicación -observación-"]) == ["Sueldos enero", "Ajuste", "Aporte patronal"]


def test_formato_con_importe_unico_y_otros_encabezados():
    """Otros mayores traen un `Importe`/`Valor` con signo en UNA columna (no Debe/Haber) y con
    encabezados distintos (`Fecha contable`, `Cuenta contable`, `Glosa`). Debe leerse igual."""
    cols = ["Fecha contable", "Cuenta contable", "Glosa", "Valor"]
    filas = [
        ["05/01/2025", "5PYG.01", "Sueldos enero", 1000.0],
        ["28/02/2025", "5BS.21204.001", "Provisión décimo", -250.0],
    ]
    d = MY._load(_xlsx(pd.DataFrame(filas, columns=cols)))
    assert list(d["Importe"]) == [1000.0, -250.0]        # columna única, con su signo
    assert list(d["cta"]) == ["5PYG.01", "5BS.21204.001"]
    assert list(d["m"]) == [1, 2]


def test_detecta_encabezado_bajo_una_fila_de_titulo():
    """Si el Mayor trae un título/logo encima, se detecta la fila real de encabezados."""
    df = pd.DataFrame([
        ["MAYOR GENERAL — EMPRESA X", None, None, None],
        ["Código", "Fecha", "Descripción", "Importe"],
        ["5PYG.01", "15/03/2025", "Sueldos", 500],
    ])
    d = MY._load(_xlsx(df, header=False))
    assert list(d["cta"]) == ["5PYG.01"] and list(d["Importe"]) == [500] and list(d["m"]) == [3]


def test_falta_columna_esencial_da_mensaje_claro():
    """Sin columna de fecha/cuenta/importe no revienta con KeyError: da un ValueError claro."""
    d = pd.DataFrame([["x", 1]], columns=["ColumnaA", "ColumnaB"])
    with pytest.raises(ValueError) as e:
        MY._load(_xlsx(d))
    msg = str(e.value)
    assert "No reconozco las columnas del Mayor" in msg
    assert "ColumnaA" in msg  # lista lo que encontró para orientar al usuario
