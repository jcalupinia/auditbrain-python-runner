"""DM3 Revisión de saldos: cuatro bloques por categoría, saldo al corte de la
sumaria (DM2) vs lo declarado en los formularios.

| Bloque                          | Según libros (DM2)   | Declarado                   |
|---------------------------------|----------------------|-----------------------------|
| Crédito tributario (IVA compras)| IVA_COMPRAS          | F-104 casillero 529         |
| IVA en ventas                   | IVA_VENTAS           | F-104 casillero 429         |
| Retenciones activo              | IVA_RETENIDO         | F-104 casillero 609         |
| Retenciones del pasivo          | RET_RENTA + RET_IVA  | F-104 799 + F-103 (399−352) |

El saldo de la sumaria es NETO (débito − crédito): las categorías de pasivo
quedan negativas, así que la diferencia se toma sobre el valor absoluto.
"""

from openpyxl import Workbook

from backend.app.aud.obligaciones_fiscales.libro.cedulas.dm3_saldos import (
    SHEET_DM3,
    build_dm3,
)

PERIODOS = [f"2025-{m:02d}" for m in range(1, 13)]

DIR_F104 = {
    ("2025-12", "529"): "'DATOS F-104'!N100",
    ("2025-12", "429"): "'DATOS F-104'!N101",
    ("2025-12", "609"): "'DATOS F-104'!N102",
    ("2025-12", "799"): "'DATOS F-104'!N103",
}

DIR_F103 = {
    ("2025-12", "399"): "'DATOS F-103'!O399",
    ("2025-12", "352"): "'DATOS F-103'!O352",
}

# Saldo al corte por categoría publicado por la sumaria (DM2).
DIR_DM2 = {
    ("saldo_corte_categoria", "IVA_COMPRAS"): "'DM2 Cédula Sumaria'!F14",
    ("saldo_corte_categoria", "IVA_VENTAS"): "'DM2 Cédula Sumaria'!F20",
    ("saldo_corte_categoria", "IVA_RETENIDO"): "'DM2 Cédula Sumaria'!F26",
    ("saldo_corte_categoria", "RET_RENTA"): "'DM2 Cédula Sumaria'!F32",
    ("saldo_corte_categoria", "RET_IVA"): "'DM2 Cédula Sumaria'!F38",
}


def _cedula(**kw):
    wb = Workbook()
    datos = dict(dir_f104=DIR_F104, dir_f103=DIR_F103, dir_dm2=DIR_DM2,
                 periodos=PERIODOS, cliente="C", periodo="2025")
    datos.update(kw)
    build_dm3(wb, **datos)
    return wb[SHEET_DM3]


def _todas_las_celdas(ws):
    return [ws.cell(r, c).value for r in range(1, ws.max_row + 1) for c in range(1, 6)]


def _fila_declarado(ws, token):
    return next(r for r in range(1, ws.max_row + 1)
                if token in str(ws.cell(r, 2).value or "") and
                str(ws.cell(r, 2).value or "").startswith("Según"))


def test_lleva_el_encabezado_de_cedula_con_su_referencia():
    ws = _cedula()
    valores = [ws.cell(r, c).value for r in range(1, 11) for c in range(1, 6)]
    assert "OBLIGACIONES FISCALES" in valores
    assert "DM3" in valores


def test_los_cuatro_bloques_por_categoria_estan_presentes():
    ws = _cedula()
    valores = [str(v).upper() for v in _todas_las_celdas(ws) if v]
    assert any("CRÉDITO TRIBUTARIO" in v for v in valores)
    assert any("IVA EN VENTAS" in v for v in valores)
    assert any("RETENCIONES ACTIVO" in v for v in valores)
    assert any("RETENCIONES DEL PASIVO" in v for v in valores)


def test_el_credito_tributario_cruza_el_saldo_al_corte_de_iva_compras_vs_529():
    ws = _cedula()
    fila_libros = next(r for r in range(1, ws.max_row + 1)
                       if str(ws.cell(r, 2).value or "").startswith("IVA en compras"))
    assert ws.cell(fila_libros, 3).value == "='DM2 Cédula Sumaria'!F14"
    fila_dec = _fila_declarado(ws, "529")
    assert ws.cell(fila_dec, 3).value == "='DATOS F-104'!N100"


def test_el_iva_en_ventas_cruza_iva_ventas_vs_429():
    ws = _cedula()
    fila_libros = next(r for r in range(1, ws.max_row + 1)
                       if str(ws.cell(r, 2).value or "").startswith("IVA en ventas"))
    assert ws.cell(fila_libros, 3).value == "='DM2 Cédula Sumaria'!F20"
    fila_dec = _fila_declarado(ws, "429")
    assert ws.cell(fila_dec, 3).value == "='DATOS F-104'!N101"


def test_las_retenciones_activo_cruzan_iva_retenido_vs_609():
    ws = _cedula()
    fila_libros = next(r for r in range(1, ws.max_row + 1)
                       if str(ws.cell(r, 2).value or "").startswith("IVA retenido por clientes"))
    assert ws.cell(fila_libros, 3).value == "='DM2 Cédula Sumaria'!F26"
    fila_dec = _fila_declarado(ws, "609")
    assert ws.cell(fila_dec, 3).value == "='DATOS F-104'!N102"


def test_las_retenciones_del_pasivo_suman_ret_renta_mas_ret_iva_vs_799_mas_399_menos_352():
    ws = _cedula()
    fila_libros = next(r for r in range(1, ws.max_row + 1)
                       if str(ws.cell(r, 2).value or "").startswith("Retención fuente"))
    # RET_RENTA + RET_IVA → SUM de los dos saldos al corte de la sumaria.
    assert ws.cell(fila_libros, 3).value == "=SUM('DM2 Cédula Sumaria'!F32,'DM2 Cédula Sumaria'!F38)"
    fila_dec = _fila_declarado(ws, "799")
    # F-104 799 + F-103 (399 − 352).
    assert ws.cell(fila_dec, 3).value == "='DATOS F-104'!N103+'DATOS F-103'!O399-'DATOS F-103'!O352"


def test_corte_interino_compara_contra_el_mes_de_corte_no_diciembre():
    """Con un corte interino (ej. agosto) se compara contra el casillero del
    mes de corte, no contra diciembre (que no existe y daba declarado 0)."""
    periodos = [f"2026-{m:02d}" for m in range(1, 9)]  # enero..agosto
    dir_f104 = {("2026-08", "529"): "'DATOS F-104'!N200"}
    ws = _cedula(periodos=periodos, dir_f104=dir_f104, dir_f103={})
    fila_dec = _fila_declarado(ws, "529")
    assert ws.cell(fila_dec, 3).value == "='DATOS F-104'!N200"
    assert "corte" in str(ws.cell(fila_dec, 2).value).lower()


def test_categoria_sin_saldo_en_la_sumaria_se_escribe_en_cero():
    """Si una categoría no tiene saldo publicado por la sumaria, el bloque no
    revienta: queda en 0."""
    ws = _cedula(dir_dm2={})
    fila_libros = next(r for r in range(1, ws.max_row + 1)
                       if str(ws.cell(r, 2).value or "").startswith("IVA en compras"))
    assert ws.cell(fila_libros, 3).value == 0


def test_casillero_declarado_ausente_queda_en_cero():
    ws = _cedula(dir_f104={}, dir_f103={})
    fila_dec = _fila_declarado(ws, "529")
    assert ws.cell(fila_dec, 3).value == 0


def test_cada_diferencia_usa_el_valor_absoluto_del_saldo_y_redondea():
    ws = _cedula()
    filas = [r for r in range(1, ws.max_row + 1) if ws.cell(r, 2).value == "Diferencia"]
    assert len(filas) == 4
    for fila in filas:
        assert ws.cell(fila, 3).value.startswith("=ROUND(ABS(")


def test_las_cifras_de_dm3_no_llevan_columnas_de_meses():
    """DM3 es una cifra al corte, no una tabla de 12 meses: la columna D
    (que en DM4/DM5/DM7 es un mes) queda vacía."""
    ws = _cedula()
    fila = next(r for r in range(1, ws.max_row + 1)
                if str(ws.cell(r, 2).value or "").startswith("IVA en compras"))
    assert ws.cell(fila, 4).value is None


def test_cruce_global_suma_los_bloques_y_saca_una_diferencia_global():
    """El cruce global suma los saldos al corte (sumaria, en valor absoluto) y
    los contrasta contra el total declarado, con una sola diferencia global."""
    ws = _cedula()
    etiquetas = [str(ws.cell(r, 2).value or "") for r in range(1, ws.max_row + 1)]
    assert any(e.startswith("Total saldos al corte según libros") for e in etiquetas)
    assert "Total según declaraciones" in etiquetas
    fila_glob = next(r for r in range(1, ws.max_row + 1)
                     if ws.cell(r, 2).value == "Diferencia global")
    assert ws.cell(fila_glob, 3).value.startswith("=ROUND(")
    fila_libros_glob = next(r for r in range(1, ws.max_row + 1)
                            if str(ws.cell(r, 2).value or "").startswith("Total saldos al corte"))
    formula = ws.cell(fila_libros_glob, 3).value
    assert formula.startswith("=SUM(")
    assert "ABS(" in formula
