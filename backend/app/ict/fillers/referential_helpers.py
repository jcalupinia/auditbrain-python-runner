"""Helpers para generar fórmulas REFERENCIALES en los anexos del ICT.

REGLA del proyecto (CLAUDE.md):
    Los anexos NO deben contener valores hardcoded. Cada celda numérica
    debe ser una FÓRMULA que referencie la celda fuente en las hojas
    DATOS F-101 / DATOS F-103 / DATOS F-104 / DATOS BALANCE.

Estos helpers convierten un par (casillero, lookup) → fórmula `=...`
o None si el casillero no está en el lookup (el caller decide qué hacer).

Uso típico en un filler::

    from backend.app.ict.fillers.referential_helpers import (
        set_casillero_ref, lookups_from_context,
    )

    f101_lookup, f103_lookup, f104_lookup, balance_lookup = \\
        lookups_from_context(anexo_data)

    # Una sola llamada: intenta F-101, fallback a Balance, devuelve True si escribió
    set_casillero_ref(
        ws, "C12", casillero="311",
        anexo_data=anexo_data,
        f101_lookup=f101_lookup,
        balance_lookup=balance_lookup,
        anexo="A2",
    )
"""

from __future__ import annotations

from backend.app.ict.fillers.base import safe_set, safe_set_formula


SHEET_F101 = "DATOS F-101"
SHEET_F103 = "DATOS F-103"
SHEET_F104 = "DATOS F-104"
SHEET_BALANCE = "DATOS BALANCE"


# ---------------------------------------------------------------------------
# Constructores de fórmulas (low-level)
# ---------------------------------------------------------------------------

def f101_ref(casillero: str, lookup: dict) -> str | None:
    """Fórmula ='DATOS F-101'!C<row> o None si el casillero no fue declarado."""
    row = lookup.get(str(casillero))
    if row is None:
        return None
    return f"='{SHEET_F101}'!C{row}"


def f103_monthly_ref(periodo: str, casillero: str, lookup: dict) -> str | None:
    """Fórmula ='DATOS F-103'!<addr> para un mes específico."""
    addr = lookup.get((str(periodo), str(casillero)))
    if not addr:
        return None
    return f"='{SHEET_F103}'!{addr}"


def f103_annual_ref(casillero: str, lookup: dict) -> str | None:
    """Fórmula ='DATOS F-103'!<total_col><row> con la suma anual (12 meses)."""
    addr = lookup.get(("ANUAL", str(casillero)))
    if not addr:
        return None
    return f"='{SHEET_F103}'!{addr}"


def f104_monthly_ref(periodo: str, casillero: str, lookup: dict) -> str | None:
    """Fórmula ='DATOS F-104'!<addr> para un mes específico."""
    addr = lookup.get((str(periodo), str(casillero)))
    if not addr:
        return None
    return f"='{SHEET_F104}'!{addr}"


def f104_annual_ref(casillero: str, lookup: dict) -> str | None:
    """Fórmula ='DATOS F-104'!<total_col><row> con la suma anual (12 meses)."""
    addr = lookup.get(("ANUAL", str(casillero)))
    if not addr:
        return None
    return f"='{SHEET_F104}'!{addr}"


def balance_row_ref(row_in_balance_sheet: int, column: str = "D") -> str:
    """Referencia directa a una fila concreta en DATOS BALANCE."""
    return f"='{SHEET_BALANCE}'!{column}{row_in_balance_sheet}"


def balance_sum_ref(rows_in_balance_sheet: list[int], column: str = "D",
                    take_abs: bool = False) -> str | None:
    """Fórmula que SUMA varias filas de DATOS BALANCE (cuando un casillero
    agrupa varias cuentas contables).

    Ejemplos:
      [5]            → ='DATOS BALANCE'!D5
      [5, 7]         → ='DATOS BALANCE'!D5+'DATOS BALANCE'!D7
      [5,6,7] abs    → =ABS('DATOS BALANCE'!D5+'DATOS BALANCE'!D6+'DATOS BALANCE'!D7)
    """
    if not rows_in_balance_sheet:
        return None
    parts = [f"'{SHEET_BALANCE}'!{column}{r}" for r in rows_in_balance_sheet]
    expr = "+".join(parts)
    if take_abs:
        return f"=ABS({expr})"
    return f"={expr}"


def balance_codigo_ref(rows_in_balance_sheet: list[int], column: str = "B",
                       sep: str = " / ") -> str | None:
    """Fórmula que trae el/los código(s) de cuenta contable (texto, col B de
    DATOS BALANCE) de las filas dadas.

      [5]      → ='DATOS BALANCE'!B5
      [5, 7]   → =TEXTJOIN(" / ",TRUE,'DATOS BALANCE'!B5,'DATOS BALANCE'!B7)
      []       → None
    """
    if not rows_in_balance_sheet:
        return None
    refs = [f"'{SHEET_BALANCE}'!{column}{r}" for r in rows_in_balance_sheet]
    if len(refs) == 1:
        return f"={refs[0]}"
    joined = ",".join(refs)
    return f'=TEXTJOIN("{sep}",TRUE,{joined})'


def libros_sumif_reactivo_formula(casillero_cell: str, *,
                                  take_abs: bool = True) -> str:
    """Fórmula REACTIVA para la columna 'valor en libros' de A4/A5: cuando el
    auditor escribe el casillero en ``casillero_cell`` (ej. '$B17'), suma en
    DATOS BALANCE todas las cuentas con ese casillero. Vacía si la celda lo está.

      $B17 → =IF($B17="","",ABS(SUMIF('DATOS BALANCE'!$A:$A,$B17,'DATOS BALANCE'!$D:$D)))
    """
    inner = (f"SUMIF('{SHEET_BALANCE}'!$A:$A,{casillero_cell},"
             f"'{SHEET_BALANCE}'!$D:$D)")
    if take_abs:
        inner = f"ABS({inner})"
    return f'=IF({casillero_cell}="","",{inner})'


# ---------------------------------------------------------------------------
# Lookups del shared_context
# ---------------------------------------------------------------------------

def lookups_from_context(anexo_data: dict) -> tuple[dict, dict, dict, list]:
    """Extrae los 4 lookups del shared_context. Vacíos si no se subió el
    formulario correspondiente."""
    return (
        anexo_data.get("_f101_lookup", {}) or {},
        anexo_data.get("_f103_lookup", {}) or {},
        anexo_data.get("_f104_lookup", {}) or {},
        anexo_data.get("_balance_lookup", []) or [],
    )


def balance_rows_for_casillero(anexo_data: dict, casillero: str,
                               balance_lookup: list[int]) -> list[int]:
    """Devuelve las filas en DATOS BALANCE de TODAS las cuentas cuyo
    casillero_sri coincide. balance_lookup[i] es la fila de la i-ésima cuenta."""
    cas = str(casillero).strip()
    balance: list[dict] = anexo_data.get("balance_mapeado", []) or []
    rows = []
    for i, item in enumerate(balance):
        item_cas = str(item.get("casillero_sri", "")).strip()
        if item_cas == cas and i < len(balance_lookup):
            rows.append(balance_lookup[i])
    return rows


# ---------------------------------------------------------------------------
# High-level: escribe la referencia adecuada según disponibilidad
# ---------------------------------------------------------------------------

def set_casillero_ref(
    ws,
    cell_addr: str,
    *,
    casillero: str,
    anexo_data: dict,
    f101_lookup: dict | None = None,
    balance_lookup: list | None = None,
    anexo: str | None = None,
    origen_prefix: str = "",
    take_abs_balance: bool = False,
) -> bool:
    """Escribe en ``ws[cell_addr]`` una fórmula referencial del valor del
    casillero. Prioridad de fuentes:
        1) F-101 lookup → fórmula ='DATOS F-101'!C<row>
        2) Balance lookup → fórmula suma 'DATOS BALANCE'!D<row>+...
        3) Si NO hay lookups (invocación directa del filler en tests),
           fallback a valor literal desde anexo_data["f101"] o aggregate
           de anexo_data["balance_mapeado"].

    Devuelve True si escribió algo, False si no se encontró el valor
    en ninguna fuente.
    """
    if f101_lookup is None:
        f101_lookup, _, _, balance_lookup = lookups_from_context(anexo_data)
    if balance_lookup is None:
        _, _, _, balance_lookup = lookups_from_context(anexo_data)

    cas = str(casillero).strip()

    # 1) F-101 referencial
    formula = f101_ref(cas, f101_lookup)
    if formula:
        return safe_set_formula(
            ws, cell_addr, formula,
            anexo=anexo, casillero=cas,
            origen=f"{origen_prefix}F-101 casillero {cas}".strip(),
        )

    # 2) Balance referencial
    rows = balance_rows_for_casillero(anexo_data, cas, balance_lookup)
    formula = balance_sum_ref(rows, take_abs=take_abs_balance)
    if formula:
        n = len(rows)
        cuenta_label = "cuenta" if n == 1 else f"{n} cuentas"
        return safe_set_formula(
            ws, cell_addr, formula,
            anexo=anexo, casillero=cas,
            origen=f"{origen_prefix}Balance Mapeado · {cuenta_label} con cas {cas}".strip(),
        )

    # 3) Fallback a valor literal (cuando no hay lookups — tests directos)
    from backend.app.ict.fillers.helpers import get_casillero_value
    val = get_casillero_value(anexo_data, cas)
    if val is None:
        return False
    return safe_set(
        ws, cell_addr, val,
        anexo=anexo, casillero=cas,
        origen=f"{origen_prefix}valor literal (sin DATOS sheet)".strip(),
    )


def set_balance_item_ref(
    ws,
    cell_addr: str,
    *,
    item_index: int,
    balance_lookup: list[int],
    column: str = "D",
    anexo: str | None = None,
    casillero: str | None = None,
    origen: str | None = None,
) -> bool:
    """Escribe ='DATOS BALANCE'!<col><row> para una cuenta específica
    (por posición en balance_mapeado). Útil cuando el filler escribe
    fila por fila el detalle del balance (ej. A4 Cuadro 1)."""
    if item_index < 0 or item_index >= len(balance_lookup):
        return False
    row = balance_lookup[item_index]
    formula = f"='{SHEET_BALANCE}'!{column}{row}"
    return safe_set_formula(
        ws, cell_addr, formula,
        anexo=anexo, casillero=casillero,
        origen=origen or f"Balance Mapeado fila #{item_index + 1}",
    )


def set_f103_annual_ref(
    ws, cell_addr: str, *, casillero: str, lookup: dict,
    anexo: str | None = None,
) -> bool:
    """Escribe la fórmula al TOTAL ANUAL F-103 del casillero. False si no existe."""
    formula = f103_annual_ref(casillero, lookup)
    if not formula:
        return False
    return safe_set_formula(
        ws, cell_addr, formula,
        anexo=anexo, casillero=casillero,
        origen=f"F-103 anual casillero {casillero}",
    )


def set_f104_annual_ref(
    ws, cell_addr: str, *, casillero: str, lookup: dict,
    anexo: str | None = None,
) -> bool:
    """Escribe la fórmula al TOTAL ANUAL F-104 del casillero. False si no existe."""
    formula = f104_annual_ref(casillero, lookup)
    if not formula:
        return False
    return safe_set_formula(
        ws, cell_addr, formula,
        anexo=anexo, casillero=casillero,
        origen=f"F-104 anual casillero {casillero}",
    )
