"""Sello inmutable del libro ICT (REP-013).

Aplica al workbook el sello que produce el motor
(`motor-auditoria-analitica`): versión de la app/motor + timestamp + hash de
la salida determinista. Da a cualquier revisor (auditor, SRI, socio) una
huella verificable de QUÉ motor, con QUÉ parámetros y CUÁNDO se generó el
papel de trabajo.

CONTRATO CON EL MOTOR (Agente C · `motor/exportar_excepciones.py`, aún NO
existe). Este módulo asume como ENTRADA el dict que devolverá
`motor.exportar_excepciones.sellar_salida(...)`. Ese sello se calcula sobre
la SALIDA DETERMINISTA del motor (excepciones + parámetros + input_hashes del
ExecutionRun), NO sobre los bytes del .xlsx. Ver nota de circularidad abajo.

NOTA DE CIRCULARIDAD (crítica):
    No se puede escribir dentro del libro el hash de ESE MISMO libro ya
    escrito (cambiaría el hash). Por eso hay dos huellas distintas:
      - `SelloSalida.hash_salida`  → hash de la salida del motor (lo provee
        `sellar_salida`); SÍ se embebe en el libro.
      - hash del .xlsx final       → se calcula con `hash_workbook_bytes`
        DESPUÉS de guardar, y se registra FUERA del libro (nombre de archivo,
        ExecutionRun.output_hashes, bitácora). NUNCA dentro del propio libro.

REGLAS DE CLAUDE.md:
  - Hoja "SELLO" es interna del auditor → ocultarla en el archivo SRI
    (agregar "SELLO" a `service.HIDDEN_SHEETS_FOR_SRI`).
  - El sello NO reemplaza la protección de estructura existente
    (`_protect_workbook_structure`); la complementa.
  - Todo texto pasa por `_safe_text` (un hash o versión no debe romper Excel).
"""

from __future__ import annotations

import hashlib
from typing import TypedDict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

from backend.app.ict.fillers.source_data_sheets import _safe_text

SHEET_NAME = "SELLO"

#: Algoritmo de hash estándar del proyecto (coincide con runHash de NIIF).
ALGORITMO_HASH = "sha256"

_THIN = Side(border_style="thin", color="A0A0A0")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_FONT_TITLE = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
_FONT_SECTION = Font(name="Calibri", size=11, bold=True, color="0A2342")
_FONT_LABEL = Font(name="Calibri", size=9, bold=True)
_FONT_DATA = Font(name="Calibri", size=9)
_FONT_MONO = Font(name="Consolas", size=9)
_FONT_FOOT = Font(name="Calibri", size=8, italic=True, color="6B7280")
_FONT_HEADER = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
_FILL_TITLE = PatternFill("solid", fgColor="0A2342")
_FILL_HEADER = PatternFill("solid", fgColor="2D5F8B")

#: Campos escalares del sello y su etiqueta legible.
_SELLO_LAYOUT: tuple[tuple[str, str], ...] = (
    ("version_app", "Versión de la aplicación (AUDIT-IA)"),
    ("version_motor", "Versión del motor"),
    ("timestamp", "Timestamp de la corrida (UTC)"),
    ("run_id", "ID de corrida (ExecutionRun)"),
    ("algoritmo", "Algoritmo de hash"),
    ("hash_salida", "Hash de la salida determinista"),
)


class SelloSalida(TypedDict, total=False):
    """Salida esperada de `motor.exportar_excepciones.sellar_salida`.

    Es la huella de la SALIDA DETERMINISTA del motor, no del xlsx.
    """

    version_app: str        # versión de AUDIT-IA / app_version del ExecutionRun
    version_motor: str      # engine_version del motor
    timestamp: str          # ISO-8601 UTC de la corrida del motor
    hash_salida: str        # hash de excepciones+parámetros (hex, del motor)
    algoritmo: str          # "sha256"
    run_id: str             # ExecutionRun.run_id
    input_hashes: dict[str, str]   # {nombre_insumo: hash} — F-101, F-103, ...


def apply_seal(
    wb: Workbook,
    sello: SelloSalida,
    *,
    session_data: dict | None = None,
) -> None:
    """Embebe `sello` en `wb`: hoja "SELLO" legible + propiedades del libro.

    Comportamiento esperado (a implementar con TDD en el servidor):
        1. Escribir la hoja "SELLO" (crear/reemplazar) con: versión app,
           versión motor, timestamp, run_id, algoritmo, hash_salida y una
           tabla de input_hashes (un insumo por fila).
        2. Escribir el sello también en las propiedades del documento
           (`wb.properties`: `keywords`/`description`) y en custom properties
           si openpyxl las soporta, para que el sello viaje aunque se copien
           celdas.
        3. Un pie de página con `version · timestamp · hash_salida[:12]…`.
        4. `_safe_text` sobre todo valor de texto.

    NO calcula el hash del propio libro (ver NOTA DE CIRCULARIDAD).
    """
    if SHEET_NAME in wb.sheetnames:
        del wb[SHEET_NAME]
    ws = wb.create_sheet(title=SHEET_NAME)
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 68

    # Cabecera de marca.
    ws.merge_cells("A1:B1")
    c = ws.cell(1, 1, value=_safe_text("AUDIT-IA · Sello inmutable del papel de trabajo"))
    c.font = _FONT_TITLE
    c.fill = _FILL_TITLE
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 24

    sd = session_data or {}
    if sd.get("ruc"):
        ws.merge_cells("A2:B2")
        cc = ws.cell(2, 1, value=_safe_text(f"RUC {sd['ruc']}"))
        cc.font = _FONT_DATA

    row = 4
    for clave, etiqueta in _SELLO_LAYOUT:
        lc = ws.cell(row, 1, value=_safe_text(etiqueta))
        lc.font = _FONT_LABEL
        lc.border = _BORDER
        lc.alignment = Alignment(horizontal="left", vertical="center")
        val = sello.get(clave)
        vc = ws.cell(row, 2, value=_safe_text(val if val is not None else "(no informado)"))
        vc.font = _FONT_MONO if clave == "hash_salida" else _FONT_DATA
        vc.border = _BORDER
        vc.alignment = Alignment(horizontal="left", vertical="center")
        row += 1

    # Tabla de input_hashes (un insumo por fila).
    input_hashes = sello.get("input_hashes") or {}
    row += 1
    ws.cell(row, 1, value=_safe_text("Huellas de insumos (input hashes)")).font = _FONT_SECTION
    row += 1
    for i, titulo in enumerate(("Insumo", "Hash"), start=1):
        hc = ws.cell(row, i, value=_safe_text(titulo))
        hc.font = _FONT_HEADER
        hc.fill = _FILL_HEADER
        hc.alignment = Alignment(horizontal="center", vertical="center")
        hc.border = _BORDER
    row += 1
    if input_hashes:
        for nombre, h in input_hashes.items():
            nc = ws.cell(row, 1, value=_safe_text(nombre))
            nc.font = _FONT_DATA
            nc.border = _BORDER
            hc = ws.cell(row, 2, value=_safe_text(h))
            hc.font = _FONT_MONO
            hc.border = _BORDER
            row += 1
    else:
        ws.cell(row, 1, value=_safe_text("Sin insumos registrados")).font = _FONT_DATA
        row += 1

    # Pie: version · timestamp · hash_salida[:12]…
    row += 1
    hs = str(sello.get("hash_salida", ""))
    pie = " · ".join(
        p for p in (
            str(sello.get("version_app", "")),
            str(sello.get("timestamp", "")),
            (hs[:12] + "…") if hs else "",
        ) if p
    )
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    fc = ws.cell(row, 1, value=_safe_text(pie))
    fc.font = _FONT_FOOT
    fc.alignment = Alignment(horizontal="left", vertical="center")

    # Sello también en las propiedades del documento (viaja con el libro).
    props = wb.properties
    props.keywords = _safe_text(
        f"AUDIT-IA-SELLO;{sello.get('version_app', '')};"
        f"{sello.get('version_motor', '')};{sello.get('run_id', '')};"
        f"{sello.get('algoritmo', ALGORITMO_HASH)};{hs}"
    )
    props.description = _safe_text(
        f"Sello inmutable AUDIT-IA. hash_salida={hs} "
        f"timestamp={sello.get('timestamp', '')} run_id={sello.get('run_id', '')}"
    )


def hash_workbook_bytes(wb_bytes: bytes, *, algoritmo: str = ALGORITMO_HASH) -> str:
    """Hash hex de los bytes del .xlsx ya serializado.

    Se usa DESPUÉS de `wb.save(...)`, sobre los bytes finales, para registrar
    la huella del archivo entregado FUERA del libro (ExecutionRun.output_hashes,
    nombre de archivo, bitácora). Función pura y determinista.

    Esta sí puede implementarse directamente (no depende del motor), pero se
    deja como scaffold para desarrollarla con su test de determinismo:
    mismo input → mismo hash; dos libros idénticos byte a byte → mismo hash.

    """
    return hashlib.new(algoritmo, wb_bytes).hexdigest()


def verify_seal(wb: Workbook, sello_esperado: SelloSalida) -> bool:
    """Comprueba que la hoja/propiedades "SELLO" de `wb` coincidan con
    `sello_esperado`. Para tests de regresión y para re-verificar un libro
    descargado.

    El criterio de coincidencia es el `hash_salida` (huella de la salida del
    motor): se busca en las propiedades del documento (keywords/description),
    donde `apply_seal` lo dejó, y en la hoja SELLO.
    """
    esperado = str(sello_esperado.get("hash_salida", "")).strip()
    if not esperado:
        return False

    # 1) Propiedades del documento.
    props = wb.properties
    for campo in (props.keywords, props.description):
        if campo and esperado in str(campo):
            return True

    # 2) Celdas de la hoja SELLO.
    if SHEET_NAME in wb.sheetnames:
        ws = wb[SHEET_NAME]
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and esperado in str(cell.value):
                    return True
    return False
