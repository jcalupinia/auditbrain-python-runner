"""Utilidades de parseo de texto de formularios SRI (PDF → texto plano).

Pequeña duplicación deliberada respecto a aud/.../cedulas/base.py: mantenemos el
módulo tax autocontenido para no acoplarlo al módulo de auditoría.
"""

from __future__ import annotations

import re


def find_casillero_value(text: str, casillero: str) -> float | None:
    """Valor decimal asociado a un casillero SRI.

    Robusto ante el ruido de columnas del PDF del SRI, que a veces extrae el
    código pegado a una columna previa ('623.0 141578.45') o con un '0.00'
    intermedio ('623 0.00 141578.45'). Estrategia: localizar la LÍNEA cuyo
    código coincide y devolver el ÚLTIMO número con 2 decimales de esa línea
    (la columna de valor). Si no, se cae a una búsqueda global tolerante.
    """
    esc = re.escape(casillero)
    # 1) Línea que termina en el valor, con el código (y posible ruido) antes.
    line_pat = rf"(?<!\d){esc}(?:\.\d{{1,2}})?(?:\s+0\.00)*\s+(-?[\d.,]*\d\.\d{{2}})\s*$"
    for ln in text.split("\n"):
        m = re.search(line_pat, ln)
        if m:
            val = _to_float(m.group(1))
            if val is not None:
                return val
    # 2) Fallback global tolerante (código seguido de un valor decimal).
    pattern = rf"(?<!\d){esc}(?:\.\d{{1,2}})?\s+(-?[\d.,]+\d)"
    for raw in re.findall(pattern, text):
        val = _to_float(raw)
        if val is not None:
            return val
    return None


def is_formato_declaracion(text: str) -> bool:
    """True si el PDF es el formato vigente 'Declaración de Renta Sociedades'.

    Señales: rótulo de la obligación, total de ingresos en casillero 4 dígitos
    (6999) o el subtotal 'TOTAL PASIVO Y PATRIMONIO' (699), ausentes en el
    formato legacy.
    """
    t = text.upper()
    if "IMPUESTO A LA RENTA SOCIEDADES" in t or "RENTA SOCIEDADES" in t:
        return True
    if "TOTAL PASIVO Y PATRIMONIO" in t:
        return True
    return re.search(r"(?<!\d)6999\s+\d", text) is not None


def _to_float(raw: str) -> float | None:
    """Convierte un número con separadores ES/EN a float.

    '1.234.567,89' -> 1234567.89 ; '1,234,567.89' -> 1234567.89 ;
    '1234.56' -> 1234.56 ; '5000' -> 5000.0
    """
    s = raw.strip()
    if not s or s in {"-", ".", ","}:
        return None
    has_dot = "." in s
    has_comma = "," in s
    if has_dot and has_comma:
        # El último separador que aparece es el decimal.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")  # estilo ES
        else:
            s = s.replace(",", "")                     # estilo EN
    elif has_comma:
        # Coma sola: decimal si hay 1-2 dígitos tras ella, si no, miles.
        dec = s.split(",")[-1]
        s = s.replace(",", ".") if len(dec) <= 2 else s.replace(",", "")
    elif has_dot:
        # Punto solo: miles si hay grupos de 3 (1.234.567), decimal en otro caso.
        parts = s.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def find_label_value(text: str, label: str) -> str | None:
    """Texto a la derecha de una etiqueta (ej. 'RUC  1790...', 'Razón Social X')."""
    m = re.search(rf"{re.escape(label)}\s*[:\-]?\s*(.+)", text, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).strip().split("  ")[0].strip() or None


def find_ruc(text: str) -> str | None:
    """RUC ecuatoriano: 13 dígitos terminados en 001."""
    m = re.search(r"\b(\d{13})\b", text)
    return m.group(1) if m else None


def find_anio(text: str) -> int | None:
    """Año/período fiscal declarado en el formulario."""
    m = re.search(r"(?:Per[ií]odo|Ejercicio|A[ñn]o)\s*(?:Fiscal)?\s*[:\-]?\s*(20\d{2})",
                  text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(20\d{2})\b", text)
    return int(m.group(1)) if m else None
