"""Lectura de los archivos de cartera del cliente.

Los archivos llegan con el formato regional del sistema que los generó. Aquí se
normalizan importes y fechas antes de que el motor vea un solo número.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable

_PATRON_DMY = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$")
_PATRON_ISO = re.compile(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})")


def a_numero(valor: Any) -> float:
    """Convierte a número respetando cualquier formato regional.

    - Si aparecen ambos separadores ("." y ","): el último que aparece es el
      decimal, el otro es de miles.
    - Si aparece un solo tipo de separador:
      - más de una vez -> todos son de miles ("8.917.458" -> 8917458);
      - una sola vez y le siguen exactamente tres dígitos -> es de miles
        ("1.500" -> 1500);
      - una sola vez y no le siguen exactamente tres dígitos -> es decimal
        ("1234.56" -> 1234.56).

    Los paréntesis indican negativo.
    """
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return 0.0
    negativo = s.startswith("(") and s.endswith(")") or "-" in s
    s = re.sub(r"[^0-9.,]", "", s)
    if not s:
        return 0.0
    tiene_punto = "." in s
    tiene_coma = "," in s
    entero, decimal = s, ""
    if tiene_punto and tiene_coma:
        i = max(s.rfind(","), s.rfind("."))
        entero, decimal = s[:i], s[i + 1:]
    elif tiene_punto or tiene_coma:
        sep = "." if tiene_punto else ","
        if s.count(sep) == 1:
            i = s.rfind(sep)
            cola = s[i + 1:]
            if len(cola) != 3:
                entero, decimal = s[:i], cola
    entero = re.sub(r"[.,]", "", entero)
    try:
        n = float(f"{entero}.{decimal}" if decimal else entero or "0")
    except ValueError:
        return 0.0
    return -n if negativo and n > 0 else n


def inferir_formato_fecha(valores: Iterable[Any]) -> str:
    """Deduce si las fechas del archivo son día/mes/año o mes/día/año.

    Recorre todos los valores (no se detiene en el primero) porque un Excel
    puede mezclar celdas con formato de fecha nativo y celdas de texto:

    - solo fechas nativas -> "nativo";
    - fechas nativas y además cadenas con patrón de fecha -> "inconsistente"
      (el archivo mezcla formatos);
    - solo cadenas -> "dmy"/"mdy"/"inconsistente" según qué componente supere
      12, o "ambiguo" si ninguno lo delata;
    - nada parseable -> "ambiguo" (no se sabe, no se asume "nativo").
    """
    dmy = mdy = total = 0
    hay_nativas = False
    hay_texto_con_patron = False
    for v in valores:
        if isinstance(v, (date, datetime)):
            hay_nativas = True
            continue
        m = _PATRON_DMY.match(str(v or "").strip())
        if not m:
            continue
        hay_texto_con_patron = True
        total += 1
        if int(m.group(1)) > 12:
            dmy += 1
        if int(m.group(2)) > 12:
            mdy += 1
    if hay_nativas and hay_texto_con_patron:
        return "inconsistente"
    if hay_nativas:
        return "nativo"
    if not total:
        return "ambiguo"
    if dmy and mdy:
        return "inconsistente"
    if dmy:
        return "dmy"
    if mdy:
        return "mdy"
    return "ambiguo"


def a_fecha(valor: Any, formato: str = "dmy") -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if valor is None or valor == "":
        return None
    s = str(valor).strip()
    m = _PATRON_DMY.match(s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        anio = int(m.group(3))
        anio += 2000 if anio < 100 else 0
        dia, mes = (b, a) if formato == "mdy" else (a, b)
        try:
            return date(anio, mes, dia)
        except ValueError:
            return None
    m = _PATRON_ISO.match(s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None
