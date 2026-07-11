# backend/app/client_portal/flujo/parser.py
"""Parser de la balanza homologada (hoja tipo "Mapeo") que sube el cliente.

Detecta las columnas por encabezado (cuenta contable, código Super Cías, código
SRI, saldo) para tolerar variaciones de formato entre archivos de clientes.
Acepta números en formato regional (`.` o `,` como decimal)."""
from __future__ import annotations
import io

from openpyxl import load_workbook

# palabras clave para detectar cada columna (normalizadas a minúsculas sin tildes)
_CLAVES = {
    "cuenta": ("cuenta", "cta", "cod.cuenta", "codigo cuenta", "cod cuenta"),
    "super_cias": ("super", "supercias", "super cias"),
    "sri": ("sri",),
    "saldo": ("saldo", "31 dic", "valor"),
}


def _norm(s) -> str:
    s = str(s or "").strip().lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "a"), ("ñ", "n")):
        s = s.replace(a, b)
    return s


def _parse_saldo(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    if not s:
        return None
    # heurística formato regional: el separador decimal es el que aparece al final
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):      # europeo: 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:                                 # us: 2,000.00
            s = s.replace(",", "")
    elif "," in s:
        # coma sola: decimal si 1-2 dígitos tras la última coma, si no miles
        ent, _, dec = s.rpartition(",")
        s = (ent.replace(",", "") + "." + dec) if len(dec) in (1, 2) else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _detectar_columnas(fila_encabezado) -> dict[str, int]:
    """Devuelve {campo: indice_columna} detectando por encabezado."""
    col: dict[str, int] = {}
    for idx, celda in enumerate(fila_encabezado):
        h = _norm(celda)
        if not h:
            continue
        for campo, claves in _CLAVES.items():
            if campo in col:
                continue
            if any(k in h for k in claves):
                col[campo] = idx
                break
    return col


def parse_balanza(contenido: bytes) -> list[dict]:
    """Lee la primera hoja con encabezados reconocibles y devuelve filas
    ``{"cuenta", "super_cias", "sri", "saldo"}``. Ignora filas sin código
    Super Cías o sin saldo numérico."""
    wb = load_workbook(io.BytesIO(contenido), data_only=True, read_only=True)
    for ws in wb.worksheets:
        # busca la fila de encabezados en las primeras 15 filas
        for r_idx, fila in enumerate(ws.iter_rows(min_row=1, max_row=15, values_only=True)):
            col = _detectar_columnas(fila)
            if "super_cias" in col and "saldo" in col:
                return _leer_filas(ws, col, desde=r_idx + 2)
    return []


def _leer_filas(ws, col: dict[str, int], desde: int) -> list[dict]:
    out: list[dict] = []
    imax = max(col.values())
    for fila in ws.iter_rows(min_row=desde, values_only=True):
        if fila is None or len(fila) <= imax:
            continue
        sc = str(fila[col["super_cias"]] or "").strip().replace(".", "")
        if not sc.isdigit():
            continue
        saldo = _parse_saldo(fila[col["saldo"]])
        if saldo is None:
            continue
        out.append({
            "cuenta": str(fila[col["cuenta"]]).strip() if "cuenta" in col and fila[col["cuenta"]] is not None else "",
            "super_cias": sc,
            "sri": str(fila[col["sri"]]).strip() if "sri" in col and fila[col["sri"]] is not None else "",
            "saldo": saldo,
        })
    return out
