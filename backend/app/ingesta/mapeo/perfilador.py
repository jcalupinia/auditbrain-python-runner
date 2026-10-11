"""Perfilador de tablas (Capa de Mapeo Universal, Fase A3).

Lee una tabla contable venga como venga (Excel, CSV con cualquier delimitador,
export de base de datos tabular) y devuelve su **forma**: qué columnas tiene,
qué tipo infiere cada una y cuál es la fila de encabezado. NO interpreta el
contenido ni mapea nada: solo describe. El mapeo lo propone `proponer.py`.

Detección de encabezado GENERALIZADA (inspirada en
`ict/parsers/balance_excel._find_header_row` pero **sin exigir palabras clave**):
la fila de encabezado es la que maximiza la proporción de celdas de texto corto
no numérico y va seguida de filas con datos. Si ninguna es clara,
``fila_encabezado=None`` y todo queda para revisión del auditor.
"""
from __future__ import annotations

import csv
import io
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.app.ingesta.contract import TipoDato
from backend.app.ingesta.normalizer import inferir_tipo

_NUMERICOS = frozenset({TipoDato.MONEDA, TipoDato.DECIMAL, TipoDato.ENTERO, TipoDato.PORCENTAJE})
_MAX_SCAN = 20          # filas a escanear buscando el encabezado
_MAX_MUESTRA = 5        # valores de muestra por columna
_LARGO_ENCABEZADO = 40  # un encabezado es texto CORTO


def norm_texto(valor: Any) -> str:
    """Normaliza para comparar nombres: minúsculas, sin acentos, sin bordes."""
    s = str(valor if valor is not None else "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


@dataclass(frozen=True)
class PerfilColumna:
    indice: int
    nombre_crudo: str
    tipo_inferido: TipoDato
    muestra: tuple[str, ...]
    n_no_vacios: int
    n_total: int


@dataclass
class PerfilTabla:
    columnas: list[PerfilColumna]
    n_filas: int                 # filas de datos (bajo el encabezado)
    fila_encabezado: Optional[int]  # índice 0-based en `filas`, o None
    hoja: Optional[str]
    filas: list[list[Any]] = field(default_factory=list)  # matriz cruda completa


def _vacio(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _leer_filas(contenido: bytes, filename: str) -> tuple[list[list[Any]], Optional[str]]:
    """Devuelve (filas_crudas, hoja). Excel vía openpyxl; texto/CSV con sniff."""
    nombre = (filename or "").lower()
    es_excel = nombre.endswith((".xlsx", ".xlsm", ".xls")) or contenido[:2] == b"PK"
    if es_excel:
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(contenido), data_only=True, read_only=True)
        ws = wb.active
        filas = [list(fila) for fila in ws.iter_rows(values_only=True)]
        return filas, ws.title
    # Texto / CSV / export tabular (best-effort): sniff del delimitador.
    texto = contenido.decode("utf-8", errors="replace")
    muestra = texto[:4096]
    try:
        dialect = csv.Sniffer().sniff(muestra, delimiters=",;\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = ";" if muestra.count(";") > muestra.count(",") else ","
    filas = [list(f) for f in csv.reader(io.StringIO(texto), delimiter=delim)]
    return filas, None


def _es_textual(v: Any) -> bool:
    if _vacio(v):
        return False
    s = str(v).strip()
    return inferir_tipo(s) is TipoDato.TEXTO and len(s) <= _LARGO_ENCABEZADO


def _tiene_datos_despues(filas: list[list[Any]], r: int) -> bool:
    """¿Hay alguna fila posterior con al menos una celda numérica?"""
    for fila in filas[r + 1:]:
        if any(inferir_tipo(c) in _NUMERICOS for c in fila if not _vacio(c)):
            return True
    return False


def _detectar_encabezado(filas: list[list[Any]]) -> Optional[int]:
    mejor_idx: Optional[int] = None
    mejor_score = 0.0
    tope = min(_MAX_SCAN, len(filas))
    for r in range(tope):
        fila = filas[r]
        no_vacias = [c for c in fila if not _vacio(c)]
        if len(no_vacias) < 2:
            continue
        textuales = sum(1 for c in no_vacias if _es_textual(c))
        ratio = textuales / len(no_vacias)
        if ratio < 0.6:
            continue
        if not _tiene_datos_despues(filas, r):
            continue
        # Favorece el encabezado "ancho" (más columnas etiquetadas) sobre
        # títulos sueltos de una sola celda que ya filtramos arriba.
        score = ratio * len(no_vacias)
        if score > mejor_score:
            mejor_score, mejor_idx = score, r
    return mejor_idx


def _perfilar_columnas(
    filas: list[list[Any]], fila_encabezado: Optional[int]
) -> tuple[list[PerfilColumna], int]:
    if not filas:
        return [], 0
    if fila_encabezado is None:
        # Sin encabezado: columnas anónimas, todo a revisión aguas abajo.
        ancho = max((len(f) for f in filas), default=0)
        encabezados = [f"col_{i}" for i in range(ancho)]
        datos = filas
    else:
        encabezados = [str(c) if not _vacio(c) else f"col_{i}"
                       for i, c in enumerate(filas[fila_encabezado])]
        datos = filas[fila_encabezado + 1:]
    ancho = len(encabezados)
    columnas: list[PerfilColumna] = []
    for i in range(ancho):
        celdas = [fila[i] for fila in datos if i < len(fila)]
        no_vacias = [c for c in celdas if not _vacio(c)]
        tipos = [inferir_tipo(c) for c in no_vacias]
        tipo = _tipo_mayoritario(tipos)
        muestra = tuple(str(c).strip() for c in no_vacias[:_MAX_MUESTRA])
        columnas.append(PerfilColumna(
            indice=i, nombre_crudo=str(encabezados[i]).strip(),
            tipo_inferido=tipo, muestra=muestra,
            n_no_vacios=len(no_vacias), n_total=len(celdas),
        ))
    return columnas, len(datos)


def _tipo_mayoritario(tipos: list[TipoDato]) -> TipoDato:
    if not tipos:
        return TipoDato.DESCONOCIDO
    conteo: dict[TipoDato, int] = {}
    for t in tipos:
        conteo[t] = conteo.get(t, 0) + 1
    # Montos y decimales se agrupan como numérico dominante si predominan.
    return max(conteo, key=lambda t: (conteo[t], t is not TipoDato.TEXTO))


def perfilar(contenido: bytes, filename: str = "tabla") -> PerfilTabla:
    """Lee la tabla y devuelve su :class:`PerfilTabla`. Nunca lanza por datos."""
    try:
        filas, hoja = _leer_filas(contenido, filename)
    except Exception:
        filas, hoja = [], None
    fila_encabezado = _detectar_encabezado(filas)
    columnas, n_datos = _perfilar_columnas(filas, fila_encabezado)
    return PerfilTabla(
        columnas=columnas, n_filas=n_datos,
        fila_encabezado=fila_encabezado, hoja=hoja, filas=filas,
    )
