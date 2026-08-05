"""Extractores de señal.

Cada función recibe un PerfilCuenta y devuelve una lista de Senal
(categoría, puntaje, motivo). El motivo es lo que se imprime en la hoja de
trazabilidad del papel de trabajo: ninguna clasificación es una caja negra.
"""

from __future__ import annotations

import re
import unicodedata

from backend.app.aud.obligaciones_fiscales.mayor.tipos import PerfilCuenta, Senal

PESO_NOMBRE = 40
PESO_NOMBRE_AMBIGUO = 20

# Tarifas de retención de IVA en Ecuador; el resto son de renta.
TARIFAS_RET_IVA = {10.0, 20.0, 30.0, 50.0, 70.0, 100.0}
# El 10% existe en ambos regímenes (arriendos/honorarios de renta), así que
# solo las tarifas altas discriminan por sí solas.
TARIFAS_SOLO_RET_IVA = {20.0, 30.0, 50.0, 70.0, 100.0}

_RE_TARIFA = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def _norm(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def extraer_tarifa(nombre: str) -> float | None:
    """Porcentaje declarado en el nombre de la cuenta, si lo hay."""
    m = _RE_TARIFA.search(nombre or "")
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def senal_nombre(perfil: PerfilCuenta) -> list[Senal]:
    """Patrones de dominio sobre el nombre de la cuenta."""
    n = _norm(perfil.nombre)
    if not n:
        return []

    if "iva" in n and "diferido" in n:
        return [Senal("IVA_DIFERIDO", PESO_NOMBRE, f"nombre contiene 'IVA diferido': {perfil.nombre!r}")]
    if "iva" in n and "retenido" in n:
        return [Senal("IVA_RETENIDO", PESO_NOMBRE, f"nombre contiene 'IVA retenido': {perfil.nombre!r}")]
    if "iva" in n and re.search(r"compra|adquisic|importac", n):
        return [Senal("IVA_COMPRAS", PESO_NOMBRE, f"nombre indica IVA de compras: {perfil.nombre!r}")]
    if "iva" in n and "venta" in n:
        return [Senal("IVA_VENTAS", PESO_NOMBRE, f"nombre indica IVA de ventas: {perfil.nombre!r}")]

    if re.search(r"\bret\b|retenc", n):
        tarifa = extraer_tarifa(perfil.nombre)
        if tarifa in TARIFAS_SOLO_RET_IVA:
            return [Senal("RET_IVA", PESO_NOMBRE, f"nombre con tarifa {tarifa}% de retención de IVA")]
        if tarifa is not None:
            return [Senal("RET_RENTA", PESO_NOMBRE, f"nombre con tarifa {tarifa}% de retención de renta")]
        return [
            Senal("RET_RENTA", PESO_NOMBRE_AMBIGUO, "nombre menciona retención, sin tarifa"),
            Senal("RET_IVA", PESO_NOMBRE_AMBIGUO, "nombre menciona retención, sin tarifa"),
        ]

    if re.search(r"venta|ingreso|servicio|descuento|rebaja", n):
        return [Senal("VENTAS", PESO_NOMBRE, f"nombre indica ventas o ingresos: {perfil.nombre!r}")]

    return []
