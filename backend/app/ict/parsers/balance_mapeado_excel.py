"""Parser for Balance Mapeado Excel (cliente ya mapeó cada cuenta a su casillero SRI).

Estructura esperada:
- Headers en fila 11 (tolerante: escanea hasta fila 20)
- Datos desde fila 13 (o la siguiente a los headers)
- A = Cod.Cuenta.Contable (opcional, algunas filas son subcuentas sin código propio)
- B = Descripción
- D = Códigos SRI (el casillero F-101, OBLIGATORIO para mapeo)
- E = Saldos 31 DIC (numérico, OBLIGATORIO)

Las filas sin D o sin E (numérico) se ignoran (son agrupadores).
"""

from __future__ import annotations

from io import BytesIO

from openpyxl import load_workbook

_EXPECTED_HEADER_KEYWORDS = {
    "codigo": ["cod.cuenta.contable", "cod cuenta contable", "código cuenta", "cuenta"],
    "descripcion": ["descripción cuenta contable", "descripcion cuenta", "descripción"],
    "casillero_sri": ["códigos sri", "codigos sri", "código sri", "sri"],
    "saldo": ["saldos 31 dic", "saldo final", "saldo"],
}


def _norm(s) -> str:
    return str(s or "").strip().lower()


def _find_header(ws, max_scan: int = 20) -> tuple[int, dict[str, int]] | tuple[None, None]:
    """Find the header row + column indices.

    Returns (header_row_idx, {field: col_idx_0_based}) or (None, None).
    Field names: codigo, descripcion, casillero_sri, saldo.
    Codigo column is optional.
    """
    for r in range(1, min(max_scan, ws.max_row) + 1):
        row = [_norm(c.value) for c in ws[r]]
        col_map: dict[str, int] = {}
        for ci, cell in enumerate(row):
            for field, keywords in _EXPECTED_HEADER_KEYWORDS.items():
                if field in col_map:
                    continue
                if any(kw in cell for kw in keywords):
                    col_map[field] = ci
                    break
        # casillero_sri AND saldo are minimum required
        if "casillero_sri" in col_map and "saldo" in col_map:
            return r, col_map
    return None, None


def parse_balance_mapeado(excel_bytes: bytes) -> dict:
    """Parse Balance Mapeado Excel.

    Returns {
        'cuentas': [
            {'casillero_sri': '311', 'codigo': '5BS.11101.002', 'descripcion': 'Caja Chica', 'saldo': 8500.0},
            ...
        ],
        'errores': []
    }
    """
    try:
        wb = load_workbook(BytesIO(excel_bytes), data_only=True, read_only=True)
    except Exception as e:  # noqa: BLE001
        return {"cuentas": [], "errores": [f"Excel inválido: {e}"]}

    ws = wb.active
    header_row, col_map = _find_header(ws)
    if header_row is None:
        return {
            "cuentas": [],
            "errores": [
                "No se detectó fila de encabezado. Esperado: 'Códigos SRI' y 'Saldo' como mínimo. "
                "Verifica que el archivo sea un Balance Mapeado con esas columnas."
            ],
        }

    col_codigo = col_map.get("codigo")
    col_descripcion = col_map.get("descripcion")
    col_casillero = col_map["casillero_sri"]
    col_saldo = col_map["saldo"]

    cuentas: list[dict] = []
    errores: list[str] = []
    last_codigo = ""  # for sub-rows that inherit parent's code

    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        # Skip totally empty rows
        if all(v is None for v in row):
            continue

        casillero_raw = row[col_casillero] if col_casillero < len(row) else None
        saldo_raw = row[col_saldo] if col_saldo < len(row) else None

        # Rows without casillero OR without numeric saldo are skipped (grouping headers)
        if casillero_raw is None or saldo_raw is None:
            # If this row has a codigo, remember it for sub-rows
            if col_codigo is not None and col_codigo < len(row) and row[col_codigo] is not None:
                last_codigo = str(row[col_codigo]).strip()
            continue

        try:
            saldo = float(saldo_raw)
        except (ValueError, TypeError):
            errores.append(f"Saldo inválido para casillero {casillero_raw}: {saldo_raw!r}")
            continue

        casillero = str(casillero_raw).strip()
        # Strip ".0" if Excel stored as float (e.g. 311.0 -> "311")
        if casillero.endswith(".0"):
            casillero = casillero[:-2]

        codigo = ""
        if col_codigo is not None and col_codigo < len(row) and row[col_codigo] is not None:
            codigo = str(row[col_codigo]).strip()
            last_codigo = codigo  # update parent for subsequent sub-rows
        else:
            # Sub-row: inherit last parent codigo
            codigo = last_codigo

        descripcion = ""
        if col_descripcion is not None and col_descripcion < len(row) and row[col_descripcion] is not None:
            descripcion = str(row[col_descripcion]).strip()

        cuentas.append({
            "casillero_sri": casillero,
            "codigo": codigo,
            "descripcion": descripcion,
            "saldo": saldo,
        })

    return {"cuentas": cuentas, "errores": errores}
