"""Hoja 'Mayores homologados': el resumen que produce el motor.

Es la ÚNICA fuente del "según libros" de todas las cédulas. Cada cédula lee
el subtotal de su categoría por fórmula, usando el mapa de direcciones que
esta función devuelve.
"""

from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook import Workbook

from backend.app.aud.obligaciones_fiscales.mayor.catalogo import CATEGORIAS

SHEET_MAYORES = "Mayores homologados"
MESES = [f"{m:02d}" for m in range(1, 13)]
NOMBRES_MES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
               "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
SIN_CLASIFICAR = "SIN_CLASIFICAR"

FONT_TITULO = Font(name="Calibri", size=11, bold=True)
FONT_DATA = Font(name="Calibri", size=9)
FONT_TOTAL = Font(name="Calibri", size=10, bold=True)
BORDE = Border(*[Side(style="thin")] * 4)
RELLENO_TOTAL = PatternFill("solid", fgColor="DCE6F1")
FORMATO_NUM = "#,##0.00"

COL_CATEGORIA, COL_CODIGO, COL_NOMBRE = 1, 2, 3
COL_PRIMER_MES = 4
COL_TOTAL = COL_PRIMER_MES + 12


def _orden(codigo: str | None) -> int:
    cat = CATEGORIAS.get(codigo or "")
    return cat.orden if cat else 99


def _addr(letra: str, fila: int) -> str:
    """Dirección CALIFICADA con el nombre de esta hoja.

    Las cédulas publican estas direcciones tal cual (`f"={addr}"`), así que
    sin el prefijo Excel las resolvería contra la propia hoja de la cédula:
    ése fue el bug de las referencias circulares de DM5/DM7. El nombre lleva
    espacios, por eso va siempre entre comillas simples.
    """
    return f"'{SHEET_MAYORES}'!{letra}{fila}"


def build_hoja_mayores(wb: Workbook, filas) -> dict[tuple[str, str], str]:
    """Crea la hoja resumen. Devuelve {(categoria, "01".."12"|"TOTAL") → addr}.

    Todas las direcciones devueltas van calificadas con el nombre de la hoja
    (`'Mayores homologados'!D30`). La única excepción es la clave
    `("orden:<categoria>", "cuentas")`, que guarda una LISTA de códigos de
    cuenta, no una dirección.
    """
    if SHEET_MAYORES in wb.sheetnames:
        del wb[SHEET_MAYORES]
    ws = wb.create_sheet(SHEET_MAYORES)

    ws.cell(1, 1, "MAYORES HOMOLOGADOS · resumen por cuenta y mes").font = FONT_TITULO

    encabezado = ["Categoría", "Código", "Cuenta"] + NOMBRES_MES + ["Total"]
    for i, texto in enumerate(encabezado, start=1):
        c = ws.cell(3, i, texto)
        c.font = FONT_TOTAL
        c.border = BORDE
        c.alignment = Alignment(horizontal="center", wrap_text=True)

    por_categoria: dict[str, list] = {}
    for f in filas:
        por_categoria.setdefault(f.categoria_final or SIN_CLASIFICAR, []).append(f)

    lookup: dict[tuple[str, str], str] = {}
    fila = 4
    for categoria in sorted(por_categoria, key=lambda c: (_orden(c), c)):
        cuentas = sorted(por_categoria[categoria], key=lambda f: f.codigo_cuenta)
        primera = fila
        for f in cuentas:
            ws.cell(fila, COL_CATEGORIA, categoria).font = FONT_DATA
            ws.cell(fila, COL_CODIGO, f.codigo_cuenta).font = FONT_DATA
            ws.cell(fila, COL_NOMBRE, f.nombre_cuenta).font = FONT_DATA
            por_mes = f.por_mes_json or {}
            for j, mes in enumerate(MESES):
                c = ws.cell(fila, COL_PRIMER_MES + j, float(por_mes.get(mes, 0.0)))
                c.font = FONT_DATA
                c.number_format = FORMATO_NUM
                c.border = BORDE
                lookup[(f"cuenta:{f.codigo_cuenta}", MESES[j])] = _addr(
                    get_column_letter(COL_PRIMER_MES + j), fila
                )
            ini = get_column_letter(COL_PRIMER_MES)
            fin = get_column_letter(COL_PRIMER_MES + 11)
            t = ws.cell(fila, COL_TOTAL, f"=SUM({ini}{fila}:{fin}{fila})")
            t.font = FONT_DATA
            t.number_format = FORMATO_NUM
            t.border = BORDE
            lookup[(f"cuenta:{f.codigo_cuenta}", "TOTAL")] = _addr(
                get_column_letter(COL_TOTAL), fila
            )
            fila += 1

        lookup[(f"orden:{categoria}", "cuentas")] = [f.codigo_cuenta for f in cuentas]
        ultima = fila - 1
        etiqueta = ws.cell(fila, COL_NOMBRE, f"Subtotal {categoria}")
        etiqueta.font = FONT_TOTAL
        etiqueta.fill = RELLENO_TOTAL
        for j in range(13):
            col = COL_PRIMER_MES + j
            letra = get_column_letter(col)
            c = ws.cell(fila, col, f"=SUM({letra}{primera}:{letra}{ultima})")
            c.font = FONT_TOTAL
            c.fill = RELLENO_TOTAL
            c.number_format = FORMATO_NUM
            c.border = BORDE
            clave = MESES[j] if j < 12 else "TOTAL"
            lookup[(categoria, clave)] = _addr(letra, fila)
        fila += 2  # una fila en blanco entre bloques

    ws.freeze_panes = "D4"
    for col, ancho in ((1, 16), (2, 14), (3, 46)):
        ws.column_dimensions[get_column_letter(col)].width = ancho
    for j in range(13):
        ws.column_dimensions[get_column_letter(COL_PRIMER_MES + j)].width = 14
    return lookup
