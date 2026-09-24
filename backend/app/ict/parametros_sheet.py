"""Hoja "PARÁMETROS" del papel de trabajo ICT (REP-005).

Deja constancia, en el propio libro, de los parámetros del encargo con los
que se corrió el motor: materialidad, materialidad de ejecución, umbrales,
rango del ejercicio, feriados, semilla, confianza. Sin esto, un resultado
"sin excepciones" no es interpretable: NIA 320/450/530 exigen documentar el
umbral aplicado.

CONTRATO DE ENTRADA. Los parámetros los produce y valida el motor
(`motor.parametros.ParametrosEncargo.a_dict()` — bloque U del formulario
AUT-2026-001). Esta capa asume ese dict serializado como ENTRADA y SOLO lo
presenta; no re-valida reglas cruzadas (eso ya lo hizo el motor).

REGLAS DE CLAUDE.md:
  - Importes como Decimal(str), number_format `#,##0.00`, NUNCA float.
  - Hoja interna del auditor → ocultar en SRI (agregar "PARÁMETROS" a
    `service.HIDDEN_SHEETS_FOR_SRI`).
  - `_safe_text` sobre texto; el Excel no debe pedir reparación.
  - Formato profesional: dos columnas (Parámetro / Valor), bordes thin,
    encabezado de bloque en negrita 11, anchos explícitos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TypedDict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

from backend.app.ict.fillers.source_data_sheets import _safe_text

SHEET_NAME = "PARÁMETROS"

NUM_FMT = "#,##0.00"

_THIN = Side(border_style="thin", color="A0A0A0")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_FONT_TITLE = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
_FONT_SUB = Font(name="Calibri", size=9, italic=True, color="404040")
_FONT_HEADER = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
_FONT_LABEL = Font(name="Calibri", size=9, bold=True)
_FONT_DATA = Font(name="Calibri", size=9)
_FONT_MISSING = Font(name="Calibri", size=9, italic=True, color="B00020")
_FILL_TITLE = PatternFill("solid", fgColor="0A2342")
_FILL_HEADER = PatternFill("solid", fgColor="2D5F8B")

#: Parámetros que, de faltar, generan advertencia (los demás son opcionales).
_OBLIGATORIOS = {
    "ejercicio_inicio", "ejercicio_fin", "materialidad",
    "materialidad_ejecucion", "error_tolerable", "confianza", "semilla",
}


class ParametrosEncargoDict(TypedDict, total=False):
    """Espejo del `ParametrosEncargo.a_dict()` del motor (bloque U).

    Los importes llegan como str (Decimal serializado); las fechas como
    ISO-8601; enteros como int. Se declara aquí solo para tipado del
    scaffold — la fuente de verdad es `motor.parametros`.
    """

    ejercicio_inicio: str
    ejercicio_fin: str
    materialidad: str
    materialidad_ejecucion: str
    umbral_insignificante: str
    umbral_aprobacion: str
    feriados: list[str]
    hora_inicio: int
    hora_fin: int
    error_tolerable: str
    confianza: int
    semilla: int
    fecha_registro_es_contable: bool


#: Orden y etiquetas legibles de cada parámetro para la hoja. La clave es la
#: del dict del motor; el valor es (etiqueta visible, tipo de formato).
#: tipo: "monto" | "fecha" | "entero" | "texto" | "lista_fechas" | "booleano".
PARAMETROS_LAYOUT: tuple[tuple[str, str, str], ...] = (
    ("ejercicio_inicio", "Inicio del ejercicio", "fecha"),
    ("ejercicio_fin", "Fin del ejercicio", "fecha"),
    ("materialidad", "Materialidad global", "monto"),
    ("materialidad_ejecucion", "Materialidad de ejecución", "monto"),
    ("umbral_insignificante", "Umbral insignificante", "monto"),
    ("umbral_aprobacion", "Umbral de aprobación", "monto"),
    ("error_tolerable", "Error tolerable", "monto"),
    ("feriados", "Feriados considerados", "lista_fechas"),
    ("hora_inicio", "Hora laborable — inicio", "entero"),
    ("hora_fin", "Hora laborable — fin", "entero"),
    ("confianza", "Nivel de confianza (%)", "entero"),
    ("semilla", "Semilla de muestreo", "entero"),
    ("fecha_registro_es_contable", "Fecha de registro = fecha contable", "booleano"),
)


@dataclass
class ParametrosSheetResult:
    """Resultado del volcado para trazabilidad."""

    sheet_name: str = SHEET_NAME
    parametros_escritos: int = 0
    advertencias: list[str] = field(default_factory=list)


def build_parametros_sheet(
    wb: Workbook,
    parametros: ParametrosEncargoDict,
    *,
    session_data: dict | None = None,
) -> ParametrosSheetResult:
    """Crea/reemplaza la hoja PARÁMETROS en `wb`.

    Comportamiento esperado (a implementar con TDD en el servidor):
        1. Si la hoja existe, borrarla y recrearla.
        2. Título de marca + cabecera del encargo (razon_social/ruc/ejercicio).
        3. Recorrer `PARAMETROS_LAYOUT` en orden; por cada clave presente en
           `parametros`, escribir (etiqueta, valor) formateando según tipo:
           - monto → Decimal(str), number_format `#,##0.00`, derecha.
           - fecha → date.fromisoformat, number_format `yyyy-mm-dd`.
           - lista_fechas → unir con ", " y `_safe_text`.
           - entero/booleano → como int / "Sí"/"No".
        4. Si falta un parámetro obligatorio, escribir "(no informado)" y
           acumular una advertencia (no lanzar: la hoja debe generarse).
        5. Anchos de columna explícitos; bordes thin; registro en trace log.
    """
    if SHEET_NAME in wb.sheetnames:
        del wb[SHEET_NAME]
    ws = wb.create_sheet(title=SHEET_NAME)

    _write_brand_header(ws, session_data)

    # Encabezado de la tabla Parámetro / Valor.
    hdr = 4
    for i, txt in enumerate(("Parámetro", "Valor"), start=1):
        c = ws.cell(hdr, i, value=_safe_text(txt))
        c.font = _FONT_HEADER
        c.fill = _FILL_HEADER
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = _BORDER
    ws.row_dimensions[hdr].height = 20

    row = hdr + 1
    escritos = 0
    advertencias: list[str] = []
    for clave, etiqueta, tipo in PARAMETROS_LAYOUT:
        lc = ws.cell(row, 1, value=_safe_text(etiqueta))
        lc.font = _FONT_LABEL
        lc.border = _BORDER
        lc.alignment = Alignment(horizontal="left", vertical="center")

        vc = ws.cell(row, 2)
        vc.border = _BORDER
        if clave in parametros and parametros[clave] is not None:
            _write_value(vc, parametros[clave], tipo)
            escritos += 1
        else:
            vc.value = _safe_text("(no informado)")
            vc.font = _FONT_MISSING
            vc.alignment = Alignment(horizontal="left", vertical="center")
            if clave in _OBLIGATORIOS:
                advertencias.append(f"Parámetro obligatorio ausente: {clave}")
        row += 1

    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 32
    ws.freeze_panes = ws.cell(hdr + 1, 1)

    return ParametrosSheetResult(parametros_escritos=escritos, advertencias=advertencias)


def _write_brand_header(ws: Worksheet, session_data: dict | None) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=2)
    c = ws.cell(1, 1, value=_safe_text("AUDIT-IA · Parámetros del encargo"))
    c.font = _FONT_TITLE
    c.fill = _FILL_TITLE
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 24
    sd = session_data or {}
    encargo = " · ".join(
        p for p in (
            _safe_text(sd.get("razon_social", "")),
            f"RUC {sd['ruc']}" if sd.get("ruc") else "",
            f"Ejercicio {sd['ejercicio_fiscal']}" if sd.get("ejercicio_fiscal") else "",
        ) if p
    )
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=2)
    c2 = ws.cell(2, 1, value=_safe_text(encargo) if encargo else _safe_text("(encargo sin identificar)"))
    c2.font = _FONT_SUB
    c2.alignment = Alignment(horizontal="left", vertical="center", indent=1)


def _write_value(cell, value, tipo: str) -> None:
    """Escribe el valor formateado según su tipo."""
    if tipo == "monto":
        try:
            cell.value = Decimal(str(value))
            cell.number_format = NUM_FMT
        except (InvalidOperation, ValueError):
            cell.value = _safe_text(value)
        cell.alignment = Alignment(horizontal="right", vertical="center")
        cell.font = _FONT_DATA
    elif tipo == "fecha":
        try:
            cell.value = date.fromisoformat(str(value))
            cell.number_format = "yyyy-mm-dd"
        except (ValueError, TypeError):
            cell.value = _safe_text(value)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.font = _FONT_DATA
    elif tipo == "entero":
        try:
            cell.value = int(value)
        except (TypeError, ValueError):
            cell.value = _safe_text(value)
        cell.alignment = Alignment(horizontal="right", vertical="center")
        cell.font = _FONT_DATA
    elif tipo == "booleano":
        cell.value = _safe_text("Sí" if value else "No")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.font = _FONT_DATA
    elif tipo == "lista_fechas":
        items = value if isinstance(value, (list, tuple)) else [value]
        cell.value = _safe_text(", ".join(str(x) for x in items))
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        cell.font = _FONT_DATA
    else:  # texto
        cell.value = _safe_text(value)
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        cell.font = _FONT_DATA
