"""Hoja de VERIFICACIÓN para el ICT 2025.

Genera una hoja al final del workbook con tres tablas:

  1. F-101 vs A1: TODOS los casilleros del F-101 con valor != 0,
     indicando cuáles se trasladaron al anexo A1 y cuáles NO
     (porque no están en el cell_map de A1).

  2. Balance Mapeado vs A1: TODAS las cuentas del balance con saldo != 0,
     indicando si su casillero SRI mapea al A1 o se reservó para
     otros anexos (A2-A9).

  3. Conciliación de totales: F-101 total Activo / Pasivo / Patrimonio
     comparado con la suma del balance por la misma agrupación.

El propósito es darle al auditor evidencia documental de que el
traslado fue íntegro — qué se trasladó, qué se omitió, y por qué.
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from backend.app.ict.cell_maps.a1 import A1_CASILLEROS_ORDERED


SHEET_NAME = "VERIFICACIÓN A1"


def _bold(cell):
    """Aplica negrita preservando el resto del estilo."""
    try:
        cell.font = cell.font.copy(bold=True)
    except Exception:
        pass


def _set_widths(ws, widths: list[int]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def build_verification_sheet(
    workbook: Workbook,
    *,
    f101: dict,
    balance_mapeado: list[dict],
    session_data: dict,
) -> None:
    """Construye la hoja VERIFICACIÓN al final del workbook.

    Args:
        workbook: workbook openpyxl ya cargado con los anexos.
        f101: dict casillero_str → float (extraído por parse_f101).
        balance_mapeado: list of {casillero_sri, codigo, descripcion, saldo}.
        session_data: razon_social, ruc, ejercicio_fiscal, numero_adhesivo.
    """
    # Si ya existe (regeneración), borrar primero
    if SHEET_NAME in workbook.sheetnames:
        del workbook[SHEET_NAME]
    ws = workbook.create_sheet(SHEET_NAME)

    casilleros_a1 = {c for c, _ in A1_CASILLEROS_ORDERED}
    casilleros_a1_names = dict(A1_CASILLEROS_ORDERED)

    # --------------------------------------------------------------------
    # Cabecera con datos del contribuyente
    # --------------------------------------------------------------------
    _bold(ws.cell(1, 1, value="VERIFICACIÓN DE TRASLADO ANEXO A1"))
    ws.cell(2, 1, value="Razón social:")
    ws.cell(2, 2, value=session_data.get("razon_social", ""))
    ws.cell(3, 1, value="RUC:")
    ws.cell(3, 2, value=session_data.get("ruc", ""))
    ws.cell(4, 1, value="Ejercicio fiscal:")
    ws.cell(4, 2, value=session_data.get("ejercicio_fiscal", ""))

    row = 6

    # --------------------------------------------------------------------
    # SECCIÓN 1 — Conciliación F-101 → A1
    # --------------------------------------------------------------------
    _bold(ws.cell(row, 1, value="1. CASILLEROS DEL F-101"))
    row += 1
    ws.cell(row, 1, value="Total casilleros encontrados en F-101:")
    ws.cell(row, 3, value=len(f101))
    row += 1
    casilleros_no_cero = {k: v for k, v in f101.items() if v not in (None, 0, 0.0)}
    ws.cell(row, 1, value="Casilleros con valor distinto de 0:")
    ws.cell(row, 3, value=len(casilleros_no_cero))
    row += 1
    casilleros_en_a1 = {k for k in f101.keys() if k in casilleros_a1}
    ws.cell(row, 1, value="Casilleros que aparecen en el A1:")
    ws.cell(row, 3, value=len(casilleros_en_a1))
    row += 1
    casilleros_omitidos = [k for k in casilleros_no_cero if k not in casilleros_a1]
    ws.cell(row, 1, value="Casilleros con valor !=0 omitidos del A1:")
    ws.cell(row, 3, value=len(casilleros_omitidos))
    if casilleros_omitidos:
        _bold(ws.cell(row, 3))
    row += 2

    # Tabla detalle de omisiones
    if casilleros_omitidos:
        _bold(ws.cell(row, 1, value="Casillero"))
        _bold(ws.cell(row, 2, value="Valor F-101"))
        _bold(ws.cell(row, 3, value="Motivo"))
        row += 1
        for cas in sorted(casilleros_omitidos):
            ws.cell(row, 1, value=cas)
            ws.cell(row, 2, value=f101.get(cas))
            ws.cell(row, 3, value="No está en el cell_map del A1 (puede ir en A2-A9)")
            row += 1
        row += 1

    # --------------------------------------------------------------------
    # SECCIÓN 2 — Conciliación Balance Mapeado → A1
    # --------------------------------------------------------------------
    _bold(ws.cell(row, 1, value="2. CUENTAS DEL BALANCE MAPEADO"))
    row += 1
    ws.cell(row, 1, value="Total cuentas en Balance Mapeado:")
    ws.cell(row, 3, value=len(balance_mapeado))
    row += 1
    cuentas_no_cero = [b for b in balance_mapeado if b.get("saldo") not in (None, 0, 0.0)]
    ws.cell(row, 1, value="Cuentas con saldo distinto de 0:")
    ws.cell(row, 3, value=len(cuentas_no_cero))
    row += 1

    # Agrupar cuentas por casillero
    by_cas: dict[str, list[dict]] = {}
    for b in balance_mapeado:
        cas = str(b.get("casillero_sri", "")).strip()
        if cas:
            by_cas.setdefault(cas, []).append(b)

    cuentas_en_a1 = sum(len(by_cas[c]) for c in by_cas if c in casilleros_a1)
    ws.cell(row, 1, value="Cuentas trasladadas al A1:")
    ws.cell(row, 3, value=cuentas_en_a1)
    row += 1
    cuentas_fuera_a1 = sum(len(by_cas[c]) for c in by_cas if c not in casilleros_a1)
    ws.cell(row, 1, value="Cuentas en otros casilleros (disponibles para A2-A9):")
    ws.cell(row, 3, value=cuentas_fuera_a1)
    row += 1
    cuentas_sin_casillero = sum(1 for b in balance_mapeado if not str(b.get("casillero_sri", "")).strip())
    ws.cell(row, 1, value="Cuentas SIN casillero SRI asignado (revisar mapeo):")
    ws.cell(row, 3, value=cuentas_sin_casillero)
    if cuentas_sin_casillero > 0:
        _bold(ws.cell(row, 3))
    row += 2

    # Tabla detalle de casilleros del balance fuera de A1
    cas_fuera = sorted(set(by_cas.keys()) - casilleros_a1)
    if cas_fuera:
        _bold(ws.cell(row, 1, value="Casilleros del Balance que NO van al A1"))
        row += 1
        _bold(ws.cell(row, 1, value="Casillero"))
        _bold(ws.cell(row, 2, value="# Cuentas"))
        _bold(ws.cell(row, 3, value="Suma de saldos"))
        _bold(ws.cell(row, 4, value="Anexo destino (sugerido)"))
        row += 1
        for cas in cas_fuera:
            items = by_cas[cas]
            total = sum((it.get("saldo") or 0) for it in items)
            destino = _sugerir_anexo(cas)
            ws.cell(row, 1, value=cas)
            ws.cell(row, 2, value=len(items))
            ws.cell(row, 3, value=total)
            ws.cell(row, 4, value=destino)
            row += 1
        row += 1

    # --------------------------------------------------------------------
    # SECCIÓN 3 — Conciliación de totales por bloque
    # --------------------------------------------------------------------
    _bold(ws.cell(row, 1, value="3. CONCILIACIÓN DE TOTALES F-101 vs BALANCE"))
    row += 1
    _bold(ws.cell(row, 1, value="Concepto"))
    _bold(ws.cell(row, 2, value="Casillero F-101"))
    _bold(ws.cell(row, 3, value="Valor F-101"))
    _bold(ws.cell(row, 4, value="Suma Balance"))
    _bold(ws.cell(row, 5, value="Diferencia"))
    row += 1

    # Totales clave a verificar
    TOTALES_REFERENCIA = [
        ("Total Activo", "499", _activos),
        ("Total Pasivo", "599", _pasivos),
        ("Total Patrimonio", "698", _patrimonio),
        ("Total Pasivo + Patrimonio", "699", lambda by: _pasivos(by) + _patrimonio(by)),
        ("Total Ingresos Ordinarios", "1005", _ingresos_ord),
    ]
    for nombre, casillero, calc in TOTALES_REFERENCIA:
        decl = f101.get(casillero)
        bal = calc(by_cas)
        diff = (bal or 0) - (decl or 0)
        ws.cell(row, 1, value=nombre)
        ws.cell(row, 2, value=casillero)
        ws.cell(row, 3, value=decl)
        ws.cell(row, 4, value=bal)
        ws.cell(row, 5, value=diff)
        if abs(diff) > 0.5:
            _bold(ws.cell(row, 5))
        row += 1

    _set_widths(ws, [40, 16, 18, 18, 18])


# ----------------------------------------------------------------------
# Helpers para conciliación
# ----------------------------------------------------------------------

# Rangos de casilleros F-101 por sección. Permite sumar bloques del
# balance independientemente del cell_map del A1.
_ACTIVO_RANGES = [(311, 499)]
_PASIVO_RANGES = [(511, 599)]
_PATRIMONIO_RANGES = [(601, 698)]
_INGRESOS_ORD_RANGES = [(6001, 6018)]


def _sum_balance_range(by_cas: dict[str, list[dict]], ranges: list[tuple[int, int]]) -> float:
    total = 0.0
    for cas, items in by_cas.items():
        try:
            n = int(cas)
        except (ValueError, TypeError):
            continue
        for lo, hi in ranges:
            if lo <= n <= hi:
                for it in items:
                    total += it.get("saldo") or 0
                break
    return total


def _activos(by_cas):       return _sum_balance_range(by_cas, _ACTIVO_RANGES)
def _pasivos(by_cas):       return _sum_balance_range(by_cas, _PASIVO_RANGES)
def _patrimonio(by_cas):    return _sum_balance_range(by_cas, _PATRIMONIO_RANGES)
def _ingresos_ord(by_cas):  return _sum_balance_range(by_cas, _INGRESOS_ORD_RANGES)


def _sugerir_anexo(casillero: str) -> str:
    """Heurística simple para sugerir a qué anexo va un casillero del F-101."""
    try:
        n = int(casillero)
    except (ValueError, TypeError):
        return "—"
    if 6001 <= n <= 6149: return "A2 (Ingresos)"
    if 6150 <= n <= 6152: return "A4 (Conciliación Ingresos)"
    if 7001 <= n <= 7999: return "A3 / A5 (Costos / Gastos)"
    if 800 <= n <= 999:   return "A6 / A7 (Beneficios / Crédito)"
    return "—"
