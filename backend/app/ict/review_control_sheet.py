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
from typing import Literal, TypedDict

from openpyxl import Workbook

SHEET_NAME = "CONTROL DE REVISIÓN"

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

    Raises:
        NotImplementedError: scaffold; implementación en el servidor.
    """
    raise NotImplementedError(
        "build_review_control_sheet: scaffold P2-F (REP-008). Ver plan "
        "docs/superpowers/plans/2026-09-24-p2f-workpaper.md, Task 4."
    )
