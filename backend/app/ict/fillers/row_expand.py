"""Helpers para EXPANDIR bloques tabulares en los anexos del ICT.

Cuando un cliente declara más datos que filas disponibles en un cuadro de
plantilla (ej. A5 Cuadro A: 5 filas pero 15 casilleros no deducibles), hay
que insertar filas en runtime SIN perder ningún dato (REGLA SUPREMA del
proyecto: nunca truncar información del cliente).

`openpyxl.insert_rows` tiene 3 limitaciones conocidas (verificadas en 3.1.5):
  1. NO reajusta las referencias de las fórmulas desplazadas.
  2. NO desplaza los merged cells (quedan en su posición vieja).
  3. NO copia el estilo/alto a las filas nuevas (quedan en blanco).

Este módulo aporta:
  - `shift_formula_rows`: reajusta refs de fila >= umbral en una fórmula.
  - `expand_tabular_block`: inserta N filas en un cuadro y deja la hoja
    consistente (fórmulas reajustadas, merges recreados, estilo copiado).
"""
from __future__ import annotations

import re
from copy import copy

from openpyxl.utils import get_column_letter


# Referencia de celda LOCAL (misma hoja): columna(s) + fila, con $ opcional.
# - lookbehind: no debe venir precedida de letra/dígito/_/$/! (evita capturar
#   parte de un nombre o una ref a OTRA hoja escrita tras '!').
# - lookahead: no debe seguir '(' (evita confundir una función con una ref).
_CELL_REF = re.compile(
    r"(?<![A-Za-z0-9_$!])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![A-Za-z0-9_(])"
)

# Una ref externa completa tras un nombre de hoja: !C500 ó !$C$500:$C$520
_EXTERNAL_REF = re.compile(r"!\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?")


def _shift_segment(seg: str, threshold: int, amount: int) -> str:
    def repl(m: re.Match) -> str:
        col_abs, col, row_abs, row = m.group(1), m.group(2), m.group(3), m.group(4)
        r = int(row)
        if r >= threshold:
            r += amount
        return f"{col_abs}{col}{row_abs}{r}"

    return _CELL_REF.sub(repl, seg)


def shift_formula_rows(formula, threshold: int, amount: int):
    """Suma ``amount`` a cada referencia de fila >= ``threshold`` en una
    fórmula de Excel. Respeta:
      - refs absolutas ($B$30), rangos (G28:G32)
      - literales de texto entre comillas dobles ("0,00%")
      - nombres de hoja entre comillas simples y sus refs externas
        ('DATOS F-101'!C500 NO se desplaza — vive en otra hoja)

    Si ``formula`` no es una cadena que empiece con '=' o ``amount`` es 0,
    se devuelve sin cambios.
    """
    if amount == 0 or not isinstance(formula, str) or not formula.startswith("="):
        return formula

    out: list[str] = []
    i, n = 0, len(formula)
    while i < n:
        ch = formula[i]
        if ch == '"':
            # Literal de texto: copiar intacto hasta el cierre.
            j = formula.find('"', i + 1)
            if j == -1:
                j = n - 1
            out.append(formula[i:j + 1])
            i = j + 1
        elif ch == "'":
            # Nombre de hoja entre comillas: copiar intacto.
            j = formula.find("'", i + 1)
            if j == -1:
                j = n - 1
            out.append(formula[i:j + 1])
            i = j + 1
            # Si sigue '!<ref>', es una ref a OTRA hoja → copiar sin desplazar.
            if i < n and formula[i] == "!":
                m = _EXTERNAL_REF.match(formula[i:])
                if m:
                    out.append(m.group(0))
                    i += m.end()
                else:
                    out.append("!")
                    i += 1
        else:
            # Segmento normal (fórmula local) hasta la próxima comilla.
            j = i
            while j < n and formula[j] not in "\"'":
                j += 1
            out.append(_shift_segment(formula[i:j], threshold, amount))
            i = j
    return "".join(out)


def _copy_cell_style(src_cell, dst_cell) -> None:
    """Copia el estilo (no el valor) de una celda a otra."""
    if src_cell.has_style:
        dst_cell.font = copy(src_cell.font)
        dst_cell.border = copy(src_cell.border)
        dst_cell.fill = copy(src_cell.fill)
        dst_cell.number_format = src_cell.number_format
        dst_cell.protection = copy(src_cell.protection)
        dst_cell.alignment = copy(src_cell.alignment)


def expand_tabular_block(
    ws,
    *,
    insert_at: int,
    amount: int,
    style_row: int,
    inner_merges: list[tuple[int, int]] | None = None,
    last_col: int = 13,
) -> None:
    """Inserta ``amount`` filas en ``insert_at`` y deja la hoja consistente.

    Pasos (compensan las limitaciones de openpyxl.insert_rows):
      1. Recolecta merges con min_row >= insert_at y fórmulas con row >= insert_at.
      2. insert_rows(insert_at, amount).
      3. Borra los merges que quedaron sin desplazar y los recrea con +amount.
      4. Reajusta cada fórmula desplazada (refs de fila >= insert_at → +amount).
      5. Copia el estilo y el alto de ``style_row`` a las filas nuevas.
      6. Recrea los merges internos de cada fila nueva (ej. E:F, G:H, I:J).

    Args:
      insert_at:   fila donde se insertan las nuevas (las que estaban aquí
                   y debajo bajan +amount).
      amount:      número de filas a insertar (>0).
      style_row:   fila plantilla cuyo estilo/alto se copia a las nuevas.
      inner_merges: lista de (col_ini, col_fin) a fusionar dentro de cada
                   fila nueva (ej. [(5,6),(7,8),(9,10)] para E:F,G:H,I:J).
      last_col:    última columna (1-based) a la que copiar estilo.
    """
    if amount <= 0:
        return

    # 1) Recolectar merges (>= insert_at) y fórmulas (>= insert_at) ANTES.
    old_merges = [
        (mc.min_col, mc.min_row, mc.max_col, mc.max_row)
        for mc in ws.merged_cells.ranges
        if mc.min_row >= insert_at
    ]
    old_formulas: dict[tuple[int, int], str] = {}
    for row in ws.iter_rows(min_row=insert_at, max_row=ws.max_row):
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                old_formulas[(cell.row, cell.column)] = cell.value

    # 2) Insertar (mueve contenido+estilo, rompe merges/fórmulas).
    ws.insert_rows(insert_at, amount)

    # 3) Borrar merges desplazados-incorrectamente y recrearlos con +amount.
    for col_ini, row_ini, col_fin, row_fin in old_merges:
        rng = (f"{get_column_letter(col_ini)}{row_ini}:"
               f"{get_column_letter(col_fin)}{row_fin}")
        try:
            ws.unmerge_cells(rng)
        except (KeyError, ValueError):
            pass
        ws.merge_cells(
            start_row=row_ini + amount, start_column=col_ini,
            end_row=row_fin + amount, end_column=col_fin,
        )

    # 4) Reajustar fórmulas desplazadas (ahora en row+amount).
    for (row, col), formula in old_formulas.items():
        ws.cell(row + amount, col).value = shift_formula_rows(
            formula, threshold=insert_at, amount=amount
        )

    # 5) Copiar estilo y alto de style_row a las filas nuevas.
    src_height = ws.row_dimensions[style_row].height
    for new_row in range(insert_at, insert_at + amount):
        if src_height is not None:
            ws.row_dimensions[new_row].height = src_height
        for col in range(1, last_col + 1):
            _copy_cell_style(ws.cell(style_row, col), ws.cell(new_row, col))

    # 6) Recrear merges internos de cada fila nueva.
    for new_row in range(insert_at, insert_at + amount):
        for col_ini, col_fin in (inner_merges or []):
            ws.merge_cells(
                start_row=new_row, start_column=col_ini,
                end_row=new_row, end_column=col_fin,
            )
