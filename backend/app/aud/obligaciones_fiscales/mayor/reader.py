"""Lectura de un Mayor General en Excel, agnóstica del ERP de origen.

El formato varía por cliente, así que el encabezado y las columnas se
autodetectan por sinónimos. Si no se logra el mapeo mínimo, el resultado lo
reporta en lugar de fallar: el auditor mapea las columnas a mano.
"""

from __future__ import annotations

import datetime
import unicodedata
from io import BytesIO

from openpyxl import load_workbook

from backend.app.aud.obligaciones_fiscales.cedulas.base import _parse_amount_sri
from backend.app.aud.obligaciones_fiscales.mayor.tipos import (
    COLUMNAS_MINIMAS,
    LecturaMayor,
    Movimiento,
)

# Sinónimos por campo. Se compara por igualdad exacta sobre el encabezado
# normalizado; el "contiene" sólo se usa como respaldo y NUNCA para 'cuenta'
# (porque 'Persona Cruce Cuenta' lo capturaría por error).
SINONIMOS: dict[str, tuple[str, ...]] = {
    "codigo": ("codigo", "cod", "cod cuenta", "codigo cuenta", "cuenta contable",
               "nro cuenta", "numero de cuenta", "cta"),
    "cuenta": ("cuenta", "nombre", "nombre cuenta", "nombre de cuenta",
               "descripcion cuenta", "detalle cuenta"),
    "fecha": ("fecha", "fecha asiento", "fecha movimiento", "f asiento"),
    "asiento": ("asiento", "comprobante", "nro asiento", "numero asiento",
                "no asiento", "diario", "nro comprobante"),
    "documento": ("documento", "doc", "nro documento", "comprobante venta",
                  "factura"),
    "identificacion": ("identificacion", "ruc", "cedula", "ruc cedula", "nit",
                       "identificacion tercero"),
    "persona": ("persona", "razon social", "tercero", "proveedor", "cliente",
                "beneficiario", "nombre tercero"),
    "descripcion": ("descripcion", "glosa", "detalle", "concepto",
                    "observacion", "observaciones"),
    "debe": ("debe", "debito", "cargo", "debitos"),
    "haber": ("haber", "credito", "abono", "creditos"),
    "saldo": ("saldo", "saldo final", "saldo acumulado"),
}

# Campos donde el respaldo por "contiene" sería peligroso.
SOLO_EXACTO = frozenset({"cuenta", "saldo"})

MAX_FILAS_BUSQUEDA_ENCABEZADO = 30


def _norm(valor) -> str:
    """minúsculas, sin tildes, sin puntuación, espacios colapsados."""
    if valor is None:
        return ""
    s = unicodedata.normalize("NFKD", str(valor))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if c.isalnum() else " " for c in s.lower())
    return " ".join(s.split())


def _mapear_encabezado(celdas: list) -> dict[str, int]:
    """Devuelve {campo: índice de columna} para una fila candidata."""
    normalizadas = [_norm(c) for c in celdas]
    mapeo: dict[str, int] = {}
    usadas: set[int] = set()

    for campo, opciones in SINONIMOS.items():
        for i, texto in enumerate(normalizadas):
            if i in usadas or not texto:
                continue
            if texto in opciones:
                mapeo[campo] = i
                usadas.add(i)
                break

    for campo, opciones in SINONIMOS.items():
        if campo in mapeo or campo in SOLO_EXACTO:
            continue
        for i, texto in enumerate(normalizadas):
            if i in usadas or not texto:
                continue
            if any(texto.startswith(o) for o in opciones):
                mapeo[campo] = i
                usadas.add(i)
                break
    return mapeo


def _fecha(valor) -> datetime.date | None:
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    if valor is None:
        return None
    texto = str(valor).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _importe(valor) -> float:
    if isinstance(valor, (int, float)):
        return float(valor)
    parsed = _parse_amount_sri(_texto(valor))
    return parsed if parsed is not None else 0.0


def leer_mayor(contenido: bytes) -> LecturaMayor:
    """Lee un mayor en .xlsx/.xlsm y devuelve sus movimientos normalizados."""
    try:
        wb = load_workbook(BytesIO(contenido), data_only=True, read_only=True)
    except Exception as e:  # noqa: BLE001
        return LecturaMayor(errores=[f"No se pudo abrir el Excel: {e}"])

    mejor = None  # (n_campos, hoja, fila, mapeo)
    for nombre in wb.sheetnames:
        ws = wb[nombre]
        for fila_idx, fila in enumerate(
            ws.iter_rows(max_row=MAX_FILAS_BUSQUEDA_ENCABEZADO, values_only=True),
            start=1,
        ):
            mapeo = _mapear_encabezado(list(fila))
            puntaje = len(mapeo)
            if mejor is None or puntaje > mejor[0]:
                mejor = (puntaje, nombre, fila_idx, mapeo)

    if mejor is None or mejor[0] == 0:
        wb.close()
        return LecturaMayor(
            errores=["No se detectó una fila de encabezado reconocible."],
            columnas_faltantes=list(COLUMNAS_MINIMAS),
        )

    _, hoja, fila_encabezado, mapeo = mejor
    lectura = LecturaMayor(
        columnas_detectadas=mapeo,
        columnas_faltantes=[c for c in COLUMNAS_MINIMAS if c not in mapeo],
        hoja=hoja,
        fila_encabezado=fila_encabezado,
    )
    if not lectura.mapeo_suficiente:
        wb.close()
        return lectura

    ws = wb[hoja]
    col = mapeo

    def celda(fila, campo):
        i = col.get(campo)
        return fila[i] if i is not None and i < len(fila) else None

    for n, fila in enumerate(
        ws.iter_rows(min_row=fila_encabezado + 1, values_only=True),
        start=fila_encabezado + 1,
    ):
        codigo = _texto(celda(fila, "codigo"))
        if not codigo:
            lectura.filas_descartadas += 1
            continue
        if _norm(codigo) in SINONIMOS["codigo"]:
            # Encabezado repetido a mitad del listado (paginación del ERP).
            lectura.filas_descartadas += 1
            continue
        lectura.movimientos.append(
            Movimiento(
                codigo=codigo,
                cuenta=_texto(celda(fila, "cuenta")),
                fecha=_fecha(celda(fila, "fecha")),
                asiento=_texto(celda(fila, "asiento")),
                documento=_texto(celda(fila, "documento")),
                identificacion=_texto(celda(fila, "identificacion")),
                persona=_texto(celda(fila, "persona")),
                descripcion=_texto(celda(fila, "descripcion")),
                debe=_importe(celda(fila, "debe")),
                haber=_importe(celda(fila, "haber")),
                saldo=_importe(celda(fila, "saldo")),
                fila=n,
            )
        )
    wb.close()
    return lectura
