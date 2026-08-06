"""Extractores de señal.

Cada función recibe un PerfilCuenta y devuelve una lista de Senal
(categoría, puntaje, motivo). El motivo es lo que se imprime en la hoja de
trazabilidad del papel de trabajo: ninguna clasificación es una caja negra.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from backend.app.aud.obligaciones_fiscales.mayor.catalogo import (
    CATEGORIAS,
    categorias_por_naturaleza,
    naturaleza_por_codigo,
)
from backend.app.aud.obligaciones_fiscales.mayor.tipos import PerfilCuenta, Senal

PESO_NOMBRE = 40
PESO_NOMBRE_AMBIGUO = 20

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


PESO_CODIGO = 15
PESO_NATURALEZA = 10
PENALIZACION_NATURALEZA = -30
PESO_MOVIMIENTOS = 10
PESO_CONTRAPARTIDA = 15

UMBRAL_PREFIJO_DOMINANTE = 0.6

# Qué categorías sugiere cada prefijo de asiento del ERP.
PREFIJOS = {
    "VTA": ("VENTAS", "IVA_VENTAS"),
    "COM": ("IVA_COMPRAS",),
    "RET": ("RET_RENTA", "RET_IVA", "IVA_RETENIDO"),
}

# Tendencia del saldo → naturalezas compatibles.
_TENDENCIA_A_NATURALEZAS = {
    "deudor": ("activo", "gasto"),
    "acreedor": ("pasivo", "ingreso"),
}


def senal_codigo(perfil: PerfilCuenta) -> list[Senal]:
    """El primer dígito del código acota las categorías posibles."""
    naturaleza = naturaleza_por_codigo(perfil.codigo)
    if not naturaleza:
        return []
    return [
        Senal(cat, PESO_CODIGO, f"código {perfil.codigo} es de naturaleza {naturaleza}")
        for cat in categorias_por_naturaleza(naturaleza)
    ]


def senal_naturaleza(perfil: PerfilCuenta) -> list[Senal]:
    """La tendencia del saldo confirma o veta categorías.

    Si la cuenta se liquida cada mes (debe == haber) la tendencia es neutra
    y la señal no opina: penalizar ahí sería un falso negativo.
    """
    compatibles = _TENDENCIA_A_NATURALEZAS.get(perfil.tendencia)
    if not compatibles:
        return []
    senales: list[Senal] = []
    for cat in CATEGORIAS.values():
        if cat.naturaleza_esperada in compatibles:
            senales.append(
                Senal(cat.codigo, PESO_NATURALEZA,
                      f"saldo {perfil.tendencia} coincide con naturaleza {cat.naturaleza_esperada}")
            )
        else:
            senales.append(
                Senal(cat.codigo, PENALIZACION_NATURALEZA,
                      f"saldo {perfil.tendencia} contradice naturaleza {cat.naturaleza_esperada}")
            )
    return senales


def senal_movimientos(perfil: PerfilCuenta) -> list[Senal]:
    """El prefijo de asiento dominante indica el tipo de transacción."""
    total = sum(perfil.prefijos_asiento.values())
    if not total:
        return []
    prefijo, veces = max(perfil.prefijos_asiento.items(), key=lambda kv: kv[1])
    if veces / total < UMBRAL_PREFIJO_DOMINANTE:
        return []
    categorias = PREFIJOS.get(prefijo.upper())
    if not categorias:
        return []
    pct = round(100 * veces / total)
    return [
        Senal(cat, PESO_MOVIMIENTOS,
              f"{pct}% de los asientos son '{prefijo}'")
        for cat in categorias
    ]


def senal_contrapartidas(
    perfil: PerfilCuenta, clasificadas: dict[str, str]
) -> list[Senal]:
    """Refuerza la categoría de la contrapartida dominante ya clasificada.

    Solo aplica si comparten naturaleza: el IVA de ventas (pasivo) tiene por
    contrapartida a las ventas (ingreso) y NO debe heredar su categoría.
    """
    if not perfil.contrapartidas:
        return []
    codigo_cp, veces = perfil.contrapartidas[0]
    categoria = clasificadas.get(codigo_cp)
    if not categoria or categoria not in CATEGORIAS:
        return []
    if CATEGORIAS[categoria].naturaleza_esperada != naturaleza_por_codigo(perfil.codigo):
        return []
    return [
        Senal(categoria, PESO_CONTRAPARTIDA,
              f"contrapartida dominante {codigo_cp} ({veces} asientos) es {categoria}")
    ]


# El historial del cliente es evidencia directa: domina cualquier heurística.
PESO_HISTORIAL = 1000
PESO_RAMA = 25


def senal_historial(perfil: PerfilCuenta, historial: dict[str, str]) -> list[Senal]:
    """Homologación previa del MISMO cliente para el MISMO código."""
    categoria = historial.get(perfil.codigo)
    if not categoria:
        return []
    if categoria not in CATEGORIAS:
        # Categoría obsoleta o mal escrita (ej. persistida en base de datos
        # antes de un cambio de catálogo): no se propaga, para no explotar
        # más adelante en el renderer del papel de trabajo.
        return []
    return [
        Senal(categoria, PESO_HISTORIAL,
              f"homologación previa del cliente para la cuenta {perfil.codigo}")
    ]


_RE_SEPARADORES_RAMA = re.compile(r"[.\-/\s]+")


def _rama(codigo: str) -> str | None:
    """Prefijo (rama) de la cuenta sin su último segmento.

    Normaliza los separadores habituales ('.', '-', '/', espacio) antes de
    partir, así que '2-1-7-2-5' y '2/1/7 2 5' se tratan igual que
    '2.1.7.2.5' (→ rama '2.1.7.2').

    Para códigos totalmente numéricos SIN separador (ej. '1150101', típico
    de ERP que no segmenta el plan de cuentas), no hay segmentos que
    partir; se usa como heurística el código sin sus dos últimos
    caracteres ('1150101' → '11501'), asumiendo que el subgrupo/dígito
    verificador se codifica ahí (patrón habitual en planes de cuentas
    ecuatorianos).

    Devuelve None si el código tiene 2 caracteres o menos (no hay rama
    posible).
    """
    codigo = (codigo or "").strip()
    if len(codigo) <= 2:
        return None
    partes = [p for p in _RE_SEPARADORES_RAMA.split(codigo) if p]
    if len(partes) > 1:
        return ".".join(partes[:-1])
    if codigo.isdigit():
        return codigo[:-2]
    return None


def senal_rama(perfil: PerfilCuenta, clasificadas: dict[str, str]) -> list[Senal]:
    """Las cuentas hermanas del mismo prefijo suelen ser de la misma categoría."""
    rama = _rama(perfil.codigo)
    if not rama:
        return []
    votos = Counter(
        categoria
        for codigo, categoria in clasificadas.items()
        if codigo != perfil.codigo and _rama(codigo) == rama
    )
    if not votos:
        return []
    categoria, n = votos.most_common(1)[0]
    return [
        Senal(categoria, PESO_RAMA,
              f"{n} cuenta(s) hermana(s) de la rama {rama} están en {categoria}")
    ]
