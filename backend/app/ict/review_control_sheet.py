"""Hoja "CONTROL DE REVISIÓN" del papel de trabajo ICT (REP-008).

Registra la traza de revisión del papel: quién preparó, quién revisó, en qué
fecha y en qué estado quedó cada acción (borrador → en revisión → aprobado).
Es el soporte del sign-off (capa 11 de la arquitectura: revisión, sign-off,
audit trail).

CONTRATO DE ENTRADA. La lista de eventos la lleva la capa de gobierno
(`aud/niif/ciclo`, hash-chain estilo Forge; ver arquitectura). Esta hoja SOLO
presenta esos eventos ya ordenados; no decide estados ni valida transiciones.
El patrón de columnas replica la cédula "14_Control_Revision" de
`backend/app/aud/niif/procesadores/libro.py` para mantener consistencia entre
los papeles de trabajo NIIF y los del ICT.

REGLAS DE CLAUDE.md:
  - Hoja interna del auditor → ocultar en SRI (agregar "CONTROL DE REVISIÓN"
    a `service.HIDDEN_SHEETS_FOR_SRI`).
  - `_safe_text` en todo texto; el Excel no debe pedir reparación.
  - Formato profesional: encabezados negrita, bordes thin, fechas
    `yyyy-mm-dd hh:mm`, anchos explícitos, freeze panes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, TypedDict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from backend.app.ict.fillers.source_data_sheets import _safe_text

SHEET_NAME = "CONTROL DE REVISIÓN"

_THIN = Side(border_style="thin", color="A0A0A0")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_FONT_TITLE = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
_FONT_SUB = Font(name="Calibri", size=9, italic=True, color="404040")
_FONT_HEADER = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
_FONT_DATA = Font(name="Calibri", size=9)
_FILL_TITLE = PatternFill("solid", fgColor="0A2342")
_FILL_HEADER = PatternFill("solid", fgColor="2D5F8B")

#: Resaltado del estado final.
_ESTADO_FILL = {
    "aprobado": PatternFill("solid", fgColor="C6EFCE"),   # verde
    "rechazado": PatternFill("solid", fgColor="F4B6B6"),  # rojo
}
_ESTADO_FILL_DEFAULT = PatternFill("solid", fgColor="FBEFB2")  # ámbar

_ANCHOS = {"fecha": 18, "accion": 16, "estado_anterior": 16,
           "estado_nuevo": 16, "actor": 22, "comentario": 40}

EstadoRevision = Literal["borrador", "en_revision", "aprobado", "rechazado"]

#: Columnas de la hoja (clave del evento, encabezado visible).
COLUMNAS: tuple[tuple[str, str], ...] = (
    ("fecha", "Fecha"),
    ("accion", "Acción"),
    ("estado_anterior", "Estado anterior"),
    ("estado_nuevo", "Estado nuevo"),
    ("actor", "Actor"),
    ("comentario", "Comentario"),
)


class EventoRevision(TypedDict, total=False):
    """Un evento de la bitácora de revisión (espejo de `aud/niif/ciclo`)."""

    fecha: str              # ISO-8601
    accion: str             # "preparó" | "revisó" | "aprobó" | ...
    estado_anterior: EstadoRevision
    estado_nuevo: EstadoRevision
    actor: str              # nombre/rol de quien ejecutó la acción
    comentario: str


@dataclass
class ReviewControlSheetResult:
    """Resultado del volcado para trazabilidad."""

    sheet_name: str = SHEET_NAME
    eventos_escritos: int = 0
    estado_final: str | None = None
    advertencias: list[str] = field(default_factory=list)


def build_review_control_sheet(
    wb: Workbook,
    eventos: list[EventoRevision],
    *,
    session_data: dict | None = None,
) -> ReviewControlSheetResult:
    """Crea/reemplaza la hoja CONTROL DE REVISIÓN en `wb`.

    Comportamiento esperado (a implementar con TDD en el servidor):
        1. Si la hoja existe, borrarla y recrearla.
        2. Título de marca + cabecera del encargo.
        3. Encabezados desde `COLUMNAS`.
        4. Una fila por evento (en el orden recibido); fechas como datetime
           con number_format `yyyy-mm-dd hh:mm`; texto con `_safe_text`.
        5. Si `eventos` está vacío, escribir una fila "Sin eventos de
           revisión registrados" (la hoja SIEMPRE se genera).
        6. Resaltar el estado final (última fila `estado_nuevo`): verde si
           "aprobado", rojo si "rechazado", ámbar en otro caso.
        7. Anchos explícitos; freeze panes; registro en trace log.
        8. Fijar `estado_final` = `estado_nuevo` del último evento.
    """
    if SHEET_NAME in wb.sheetnames:
        del wb[SHEET_NAME]
    ws = wb.create_sheet(title=SHEET_NAME)

    n_cols = len(COLUMNAS)
    # Cabecera de marca.
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    c = ws.cell(1, 1, value=_safe_text("AUDIT-IA · Control de revisión"))
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
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n_cols)
    c2 = ws.cell(2, 1, value=_safe_text(encargo) if encargo else _safe_text("(encargo sin identificar)"))
    c2.font = _FONT_SUB
    c2.alignment = Alignment(horizontal="left", vertical="center", indent=1)

    # Encabezados.
    hdr = 4
    for i, (_clave, titulo) in enumerate(COLUMNAS, start=1):
        hc = ws.cell(hdr, i, value=_safe_text(titulo))
        hc.font = _FONT_HEADER
        hc.fill = _FILL_HEADER
        hc.alignment = Alignment(horizontal="center", vertical="center")
        hc.border = _BORDER
    ws.row_dimensions[hdr].height = 20

    # Anchos.
    for i, (clave, _titulo) in enumerate(COLUMNAS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = _ANCHOS.get(clave, 18)
    ws.freeze_panes = ws.cell(hdr + 1, 1)

    eventos = eventos or []
    if not eventos:
        ws.merge_cells(start_row=hdr + 1, start_column=1, end_row=hdr + 1, end_column=n_cols)
        pc = ws.cell(hdr + 1, 1, value=_safe_text("Sin eventos de revisión registrados"))
        pc.font = _FONT_DATA
        pc.alignment = Alignment(horizontal="left", vertical="center")
        return ReviewControlSheetResult(eventos_escritos=0, estado_final=None)

    row = hdr + 1
    for ev in eventos:
        for i, (clave, _titulo) in enumerate(COLUMNAS, start=1):
            cell = ws.cell(row, i)
            cell.border = _BORDER
            cell.font = _FONT_DATA
            if clave == "fecha":
                dt = _parse_dt(ev.get("fecha"))
                if dt is not None:
                    cell.value = dt
                    cell.number_format = "yyyy-mm-dd hh:mm"
                else:
                    cell.value = _safe_text(ev.get("fecha"))
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.value = _safe_text(ev.get(clave))
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        row += 1

    # Resaltar el estado final (última fila `estado_nuevo`).
    estado_final = str(eventos[-1].get("estado_nuevo") or "").strip() or None
    if estado_final:
        fill = _ESTADO_FILL.get(estado_final, _ESTADO_FILL_DEFAULT)
        estado_col = next(i for i, (c, _t) in enumerate(COLUMNAS, start=1) if c == "estado_nuevo")
        last = row - 1
        ec = ws.cell(last, estado_col)
        ec.fill = fill
        ec.font = Font(name="Calibri", size=9, bold=True)

    return ReviewControlSheetResult(eventos_escritos=len(eventos), estado_final=estado_final)


def _parse_dt(value) -> datetime | None:
    """Parsea una fecha ISO-8601 a datetime; None si no aplica."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None
