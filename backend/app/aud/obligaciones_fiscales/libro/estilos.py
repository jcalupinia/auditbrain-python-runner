"""Formato compartido por las cédulas del libro DM.

Paleta ejecutiva de la firma (manual de marca): Deep Blue #071B2F, Navy
#0A2342 y Gold #C7A83C. Los encabezados van en banda oscura con texto claro,
los totales en un tono dorado suave y las cifras con bordes finos: el papel se
ve presentable sin que el auditor tenga que darle formato a mano.
"""

from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

FUENTE_MARCAS = "Arial"

# --- Paleta de marca --------------------------------------------------------
COLOR_DEEP_BLUE = "071B2F"   # banda del título de la firma
COLOR_NAVY = "0A2342"        # encabezados de tabla
COLOR_GOLD = "C7A83C"        # acentos
COLOR_GOLD_SUAVE = "F3ECD2"  # fondo de filas TOTAL
COLOR_BLANCO = "FFFFFF"
COLOR_TEXTO = "1A1A1A"

# --- Fuentes ----------------------------------------------------------------
FONT_TITULO_FIRMA = Font(name="Calibri", size=14, bold=True, color=COLOR_BLANCO)
FONT_SUBTITULO_FIRMA = Font(name="Calibri", size=10, bold=False, color=COLOR_GOLD)
FONT_TITULO_CEDULA = Font(name="Calibri", size=11, bold=True, color=COLOR_DEEP_BLUE)
FONT_ETIQUETA = Font(name="Calibri", size=9, color="6B7280")
FONT_DATO = Font(name="Calibri", size=10, bold=True, color=COLOR_TEXTO)
FONT_ENCABEZADO_TABLA = Font(name="Calibri", size=10, bold=True, color=COLOR_BLANCO)
FONT_DATA = Font(name="Calibri", size=9, color=COLOR_TEXTO)
FONT_TOTAL = Font(name="Calibri", size=10, bold=True, color=COLOR_DEEP_BLUE)

# --- Bordes y rellenos ------------------------------------------------------
_AZUL_BORDE = "B8C4D9"
BORDE = Border(*[Side(style="thin", color=_AZUL_BORDE)] * 4)
BORDE_TOTAL = Border(
    top=Side(style="double", color=COLOR_GOLD),
    bottom=Side(style="double", color=COLOR_GOLD),
    left=Side(style="thin", color=_AZUL_BORDE),
    right=Side(style="thin", color=_AZUL_BORDE),
)
RELLENO_TOTAL = PatternFill("solid", fgColor=COLOR_GOLD_SUAVE)
RELLENO_ENCABEZADO = PatternFill("solid", fgColor=COLOR_NAVY)
RELLENO_BANDA_TITULO = PatternFill("solid", fgColor=COLOR_DEEP_BLUE)
FORMATO_NUM = "#,##0.00"

_CENTRO = Alignment(horizontal="center", vertical="center", wrap_text=True)

# Marcas de auditoría. Son fijas de la cédula: NO se calculan contra ninguna
# tolerancia. En el modelo del auditor la misma marca aparecía en Arial y en
# Wingdings; aquí se unifican.
MARCAS = {
    "verificado": ("ü", "Cotejado según libros"),
    "declarado": ("£", "Cotejado según formularios"),
    "diferencia": ("‡", "Diferencia determinada"),
    "sumado": ("Σ", "Sumado, totalizado"),
}


def estilo_encabezado_tabla(celda, *, centro: bool = True) -> None:
    """Aplica la banda de encabezado de tabla (fondo navy, texto blanco) a una
    celda. Centraliza el look de todos los encabezados del libro."""
    celda.font = FONT_ENCABEZADO_TABLA
    celda.fill = RELLENO_ENCABEZADO
    celda.border = BORDE
    if centro:
        celda.alignment = _CENTRO


def escribir_encabezado_cedula(
    ws,
    *,
    titulo: str,
    referencia: str,
    cliente: str,
    periodo: str,
    preparado_por: str | None = None,
    revisado_por: str | None = None,
    fecha_corte=None,
    ancho_banda: int = 15,
) -> None:
    """Encabezado estándar (filas 1 a 10) de una cédula DM, con banda de marca."""
    # Banda de título de la firma: filas 1-2 rellenas en Deep Blue, de la
    # columna 1 hasta ancho_banda, con el título en blanco y la firma en dorado.
    for fila_banda in (1, 2):
        for col in range(1, ancho_banda + 1):
            ws.cell(fila_banda, col).fill = RELLENO_BANDA_TITULO
    ws.cell(1, 1, "OBLIGACIONES FISCALES").font = FONT_TITULO_FIRMA
    ws.cell(1, 1).alignment = Alignment(horizontal="left", vertical="center")
    ws.cell(2, 1, "AuditConsulting Auditores Cía. Ltda.").font = FONT_SUBTITULO_FIRMA
    ws.row_dimensions[1].height = 22

    ws.cell(3, 1, titulo).font = FONT_TITULO_CEDULA

    ws.cell(5, 1, "Nombre del cliente").font = FONT_ETIQUETA
    ws.cell(6, 1, cliente or "").font = FONT_DATO
    ws.cell(5, 4, "Periodo terminado").font = FONT_ETIQUETA
    ws.cell(6, 4, periodo or "").font = FONT_DATO

    ws.cell(7, 1, "Preparado por:").font = FONT_ETIQUETA
    ws.cell(8, 1, preparado_por or "").font = FONT_DATO
    ws.cell(7, 3, "Fecha:").font = FONT_ETIQUETA
    ws.cell(8, 3, fecha_corte or "").font = FONT_DATO
    ws.cell(7, 4, "Referencia").font = FONT_ETIQUETA
    ws.cell(8, 4, referencia).font = FONT_DATO

    ws.cell(9, 1, "Revisado por:").font = FONT_ETIQUETA
    ws.cell(10, 1, revisado_por or "").font = FONT_DATO


def escribir_leyenda_marcas(ws, *, fila: int) -> int:
    """Leyenda de las marcas al pie de la cédula. Devuelve la fila siguiente."""
    for i, (simbolo, texto) in enumerate(MARCAS.values()):
        c = ws.cell(fila + i, 1, simbolo)
        c.font = Font(name=FUENTE_MARCAS, size=10, color=COLOR_GOLD)
        ws.cell(fila + i, 2, texto).font = Font(name=FUENTE_MARCAS, size=9, color="6B7280")
    return fila + len(MARCAS)
