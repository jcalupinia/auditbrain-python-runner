"""Separa las ventas del mayor en gravadas, exportación, 0%, reembolso, otro
ingreso y «por asignar».

La tarifa se decide ante todo **por la cuenta**: en la mayoría de planes de
cuentas cada cuenta de ventas es de una sola tarifa y lo dice su nombre
(«CORRETAJES CON IVA 0%» → exportación/0%, «… CON IVA 12% Y 15%» → gravada,
«NOTAS DE CRÉDITO …» → resta de su tramo, «INGRESOS POR REEMBOLSO» →
casillero 444, «RENDIMIENTOS / VENTA DE ACTIVOS / RECUPERACIÓN …» → otro
ingreso que NO es operación de IVA en ventas). ``tarifa_de_cuenta`` lee ese
tramo del nombre; el auditor puede corregirlo con ``overrides`` (decisión del
dueño 2026-10-09: «auto por nombre + ajuste del auditor»).

Para una cuenta cuyo nombre NO declara tarifa se cae al reparto **por asiento
contable**, usando la contrapartida de IVA en ventas como testigo, en este
orden:

1. ``iva`` = suma de |neto| de las líneas de categoría ``IVA_VENTAS`` del
   asiento; ``total`` = suma de |neto| de sus líneas de ``VENTAS``.
2. Sin IVA (``iva <= 0,05``) → todo el asiento es 0%.
3. Si alguna tarifa ``t`` cumple ``|iva/t - total| <= 0,05`` → todo gravado.
4. Si no, se busca el subconjunto de líneas cuya suma iguale ``iva/t``. Si es
   único, esas líneas son gravadas y el resto 0%.
5. Lo que no se resuelve queda POR ASIGNAR: no se prorratea ni se adivina, se
   le muestra al auditor para que revise el asiento.

Dos decisiones que NO son libres, porque cambiarlas mueve las cifras:

* **El subconjunto se busca por tamaño ascendente.** El primer tamaño con
  exactamente una combinación gana; si un tamaño tiene dos o más, se abandona
  esa tarifa. Leer la unicidad de forma global (sobre todos los tamaños a la
  vez) es más estricto y sobre el mayor real del cliente resuelve 10 asientos
  en vez de 11 (por asignar 20.043,87 en vez de 19.203,87).
* **El importe que se acumula es el NETO** (haber − débito): las notas de
  crédito (débitos a la cuenta de venta) RESTAN dentro de su tramo, y el
  reparto suma exactamente el total neto que la hoja de mayores publica para
  VENTAS, o el papel de trabajo deja de cuadrar.

Función pura: sin base de datos ni FastAPI, igual que el resto del motor.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict

from backend.app.aud.obligaciones_fiscales.mayor.tipos import Movimiento

# Tramos del desglose. "gravada"/"cero"/"por_asignar" son los que produce el
# reparto por asiento; "exportacion"/"reembolso"/"otro_ingreso" solo salen de
# la clasificación por nombre (o del override del auditor).
BUCKETS = ("gravada", "exportacion", "cero", "reembolso", "otro_ingreso", "por_asignar")
# Tramos a los que el reparto por asiento puede mandar una cuenta sin pista.
BUCKETS_POR_ASIENTO = ("gravada", "cero", "por_asignar")
# Tramos que el auditor puede asignar a una cuenta (override) o que infiere el
# nombre; "por_asignar" nunca se asigna a mano (es el remanente del reparto).
BUCKETS_FIJOS = ("gravada", "exportacion", "cero", "reembolso", "otro_ingreso")
TARIFAS = (0.15, 0.12, 0.14, 0.05)
TOLERANCIA = 5  # centavos


def _norm(texto: str) -> str:
    """Mayúsculas sin acentos, para comparar el nombre por palabras clave."""
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.upper()


# Palabras que marcan un ingreso que NO es operación de IVA en ventas (van al
# bloque "otros ingresos", fuera de los casilleros de ventas).
_OTRO_INGRESO = (
    "RENDIM", "INTERES", "VENTA DE ACTIVO", "ACTIVOS FIJOS", "RECUPERAC",
    "DIFERENCIA", "OTROS CONCEPTOS", "MULTA", "SOBRANTE", "DIVIDENDO",
)
# Palabras que marcan una exportación de servicios (casilleros 417/418), para
# distinguirla de la venta local 0% (413/415).
_EXPORTACION = ("EXPORT", "EXTERIOR", "REASEGURO", "CORRETAJE", "DEL EXTERIOR")
# Tarifa 0% en el nombre.
_CERO = ("0%", "0 %", "TARIFA 0", "CERO", "EXENT")
# Tarifa gravada (≠0%) en el nombre.
_GRAVADA = ("12%", "14%", "15%", "TARIFA DIF")


def es_nota_credito(nombre: str) -> bool:
    """¿El nombre de la cuenta es una nota de crédito / devolución de ventas?"""
    n = _norm(nombre)
    return ("NOTA" in n and "CRED" in n) or "DEVOLUC" in n or "N/C" in n


def tarifa_de_cuenta(nombre: str) -> str | None:
    """Tramo que el nombre de la cuenta declara, o ``None`` si es ambiguo.

    Reglas (en orden): reembolso → otro ingreso → nota de crédito/venta con su
    tarifa → tarifa 0% (exportación si el nombre es de corretaje/exterior, si
    no 0% local) → gravada. Sin ninguna pista devuelve ``None`` y la cuenta se
    reparte por asiento.
    """
    n = _norm(nombre)
    if "REEMBOLSO" in n or "REEMBOLZO" in n:
        return "reembolso"
    if any(k in n for k in _OTRO_INGRESO):
        return "otro_ingreso"
    tiene_cero = any(k in n for k in _CERO)
    tiene_grav = any(k in n for k in _GRAVADA) or ("IVA" in n and not tiene_cero)
    if tiene_cero:
        return "exportacion" if any(k in n for k in _EXPORTACION) else "cero"
    if tiene_grav:
        return "gravada"
    return None

# Tope de la búsqueda combinatoria. El asiento resuelto más grande del mayor
# real tiene 19 líneas de venta y el ambiguo más grande 22; por encima de este
# tope el asiento se marca POR ASIGNAR sin buscar, para que un mayor con
# asientos de cierre de cientos de líneas no cuelgue la generación del libro.
MAX_LINEAS_BUSQUEDA = 24

def _cent(valor: float) -> int:
    return round(valor * 100)


def _buscar(v, prefijo, i, faltan, suma, elegidos, objetivo, hallados) -> None:
    """Combinaciones de tamaño ``faltan`` de ``v[i:]`` que suman ``objetivo``.

    ``v`` viene ordenado de mayor a menor, así que la suma máxima alcanzable
    desde ``i`` son los ``faltan`` primeros y la mínima los ``faltan``
    últimos: con esas dos cotas se poda casi todo el árbol.
    """
    if len(hallados) > 1:
        return
    if faltan == 0:
        if abs(suma - objetivo) <= TOLERANCIA:
            hallados.append(tuple(elegidos))
        return
    n = len(v)
    if n - i < faltan:
        return
    if suma + prefijo[i + faltan] - prefijo[i] < objetivo - TOLERANCIA:
        return
    if suma + prefijo[n] - prefijo[n - faltan] > objetivo + TOLERANCIA:
        return
    elegidos.append(i)
    _buscar(v, prefijo, i + 1, faltan - 1, suma + v[i], elegidos, objetivo, hallados)
    elegidos.pop()
    _buscar(v, prefijo, i + 1, faltan, suma, elegidos, objetivo, hallados)


def subconjunto_unico(valores: list[int], objetivo: int) -> set[int] | None:
    """Índices del único subconjunto propio de ``valores`` que suma ``objetivo``.

    Recorre los tamaños de menor a mayor: el primero con exactamente una
    combinación es la respuesta; el primero con dos o más abandona la
    búsqueda (el asiento es ambiguo y no se adivina).
    """
    n = len(valores)
    orden = sorted(range(n), key=lambda i: -valores[i])
    v = [valores[i] for i in orden]
    prefijo = [0] * (n + 1)
    for i, x in enumerate(v):
        prefijo[i + 1] = prefijo[i] + x

    for tamano in range(1, n):
        hallados: list[tuple[int, ...]] = []
        _buscar(v, prefijo, 0, tamano, 0, [], objetivo, hallados)
        if len(hallados) == 1:
            return {orden[i] for i in hallados[0]}
        if len(hallados) > 1:
            return None
    return None


def separar_ventas_por_tarifa(
    movimientos: list[Movimiento],
    categorias: dict[str, str | None],
    overrides: dict[str, str] | None = None,
) -> dict[str, dict[str, dict[str, float]]]:
    """Desglose de las cuentas de VENTAS por tarifa.

    Devuelve ``{codigo_cuenta: {bucket: {mes: monto}}}`` con una entrada por
    cuenta de categoría ``VENTAS`` y un sub-dict por cada tramo de ``BUCKETS``.
    Para cada cuenta y mes, la suma de todos sus tramos es exactamente el monto
    neto según libros que publica la hoja de mayores.

    Cada cuenta se asigna PRIMERO por su tramo fijo: el ``overrides`` del
    auditor manda; si no, el que infiere el nombre (``tarifa_de_cuenta``). Solo
    las cuentas sin tramo fijo (nombre ambiguo) se reparten por asiento
    (gravada/cero/por_asignar).
    """
    overrides = overrides or {}
    ventas = {c for c, k in categorias.items() if k == "VENTAS"}
    iva_ventas = {c for c, k in categorias.items() if k == "IVA_VENTAS"}
    nombres = {m.codigo: m.cuenta for m in movimientos if m.cuenta}
    # Las ventas se miden por el NETO (haber − débito): así las notas de
    # crédito (débitos a la cuenta de venta) RESTAN dentro de su tramo, igual
    # que en el papel de trabajo del auditor.
    monto = lambda m: round(m.haber - m.debe, 2)  # noqa: E731

    salida: dict[str, dict[str, dict[str, float]]] = {
        codigo: {b: {} for b in BUCKETS} for codigo in ventas
    }

    def anotar(bucket: str, lineas) -> None:
        for m in lineas:
            if not m.mes:
                continue
            destino = salida[m.codigo][bucket]
            destino[m.mes] = round(destino.get(m.mes, 0.0) + monto(m), 2)

    # Tramo fijo por cuenta: override del auditor, o el que dice el nombre.
    tramo_fijo: dict[str, str] = {}
    for codigo in ventas:
        ovr = overrides.get(codigo)
        if ovr in BUCKETS_FIJOS:
            tramo_fijo[codigo] = ovr
        else:
            inferido = tarifa_de_cuenta(nombres.get(codigo, ""))
            if inferido in BUCKETS_FIJOS:
                tramo_fijo[codigo] = inferido

    # Una nota de crédito 0% debe restar del MISMO tramo que la venta 0% que
    # corrige. Si la empresa exporta (hay cuentas en exportación) y no tiene
    # venta 0% local propia, el nombre genérico de la NC ("NOTAS DE CRÉDITO
    # TARIFA 0%") no trae la palabra export: se reubica a exportación para que
    # el neto de exportaciones cuadre con lo declarado. El auditor puede
    # moverla con un override.
    hay_export = any(t == "exportacion" for t in tramo_fijo.values())
    hay_cero_venta = any(
        t == "cero" and not es_nota_credito(nombres.get(c, ""))
        for c, t in tramo_fijo.items()
    )
    if hay_export and not hay_cero_venta:
        for codigo, tramo in list(tramo_fijo.items()):
            if (
                tramo == "cero"
                and codigo not in overrides
                and es_nota_credito(nombres.get(codigo, ""))
            ):
                tramo_fijo[codigo] = "exportacion"

    # 1) Cuentas con tramo fijo: toda la cuenta va a su tramo.
    for m in movimientos:
        if m.codigo in tramo_fijo:
            anotar(tramo_fijo[m.codigo], [m])

    # 2) Cuentas sin tramo fijo: reparto por asiento (solo entre ellas).
    libres = ventas - set(tramo_fijo)
    if not libres:
        return salida

    por_asiento: dict[str, list[Movimiento]] = defaultdict(list)
    for m in movimientos:
        if m.codigo in libres or m.codigo in iva_ventas:
            por_asiento[m.asiento].append(m)

    for movs in por_asiento.values():
        lineas = [m for m in movs if m.codigo in libres]
        if not lineas:
            continue

        iva = _cent(sum(abs(m.neto) for m in movs if m.codigo in iva_ventas))
        if iva <= TOLERANCIA:
            anotar("cero", lineas)
            continue

        valores = [_cent(abs(m.neto)) for m in lineas]
        total = sum(valores)
        if any(abs(round(iva / t) - total) <= TOLERANCIA for t in TARIFAS):
            anotar("gravada", lineas)
            continue

        indices = None
        if len(lineas) <= MAX_LINEAS_BUSQUEDA:
            for tarifa in TARIFAS:
                objetivo = round(iva / tarifa)
                if objetivo > total + TOLERANCIA:
                    continue
                indices = subconjunto_unico(valores, objetivo)
                if indices is not None:
                    break

        if indices is None:
            anotar("por_asignar", lineas)
        else:
            anotar("gravada", [m for i, m in enumerate(lineas) if i in indices])
            anotar("cero", [m for i, m in enumerate(lineas) if i not in indices])

    return salida
