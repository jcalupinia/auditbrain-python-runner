"""Separa las ventas del mayor en gravadas, 0% y por asignar.

El motor de mayores agrega por cuenta y mes, sin distinguir tarifa, así que
DM5 mostraba la MISMA cifra en el bloque «VENTAS ≠ 0%» y en el bloque
«VENTAS 0%». No se puede resolver marcando la cuenta entera: el auditor
confirmó que una misma cuenta de ventas tiene movimientos gravados y 0%.

La separación se hace **por asiento contable**, usando la contrapartida de
IVA en ventas como testigo, en este orden:

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
* **El importe que se acumula es el lado que AUMENTA la cuenta** (el haber,
  para ingresos), igual que ``cuentas.monto_segun_libros``. La aritmética de
  la separación sí usa |neto| —así se midió—, pero el reparto tiene que sumar
  exactamente el total que la hoja de mayores ya publica, o el papel de
  trabajo deja de cuadrar.

Función pura: sin base de datos ni FastAPI, igual que el resto del motor.
"""

from __future__ import annotations

from collections import defaultdict

from backend.app.aud.obligaciones_fiscales.mayor.catalogo import CATEGORIAS
from backend.app.aud.obligaciones_fiscales.mayor.tipos import Movimiento

BUCKETS = ("gravada", "cero", "por_asignar")
TARIFAS = (0.15, 0.12, 0.14, 0.05)
TOLERANCIA = 5  # centavos

# Tope de la búsqueda combinatoria. El asiento resuelto más grande del mayor
# real tiene 19 líneas de venta y el ambiguo más grande 22; por encima de este
# tope el asiento se marca POR ASIGNAR sin buscar, para que un mayor con
# asientos de cierre de cientos de líneas no cuelgue la generación del libro.
MAX_LINEAS_BUSQUEDA = 24

_NATURALEZAS_DEUDORAS = frozenset({"activo", "gasto"})


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


def _lado_que_aumenta(codigo_categoria: str | None):
    cat = CATEGORIAS.get(codigo_categoria or "")
    usa_debe = cat is None or cat.naturaleza_esperada in _NATURALEZAS_DEUDORAS
    return (lambda m: m.debe) if usa_debe else (lambda m: m.haber)


def separar_ventas_por_tarifa(
    movimientos: list[Movimiento], categorias: dict[str, str | None]
) -> dict[str, dict[str, dict[str, float]]]:
    """Desglose de las cuentas de VENTAS por tarifa.

    Devuelve ``{codigo_cuenta: {"gravada"|"cero"|"por_asignar": {mes: monto}}}``
    con una entrada por cuenta de categoría ``VENTAS``. Para cada cuenta y mes,
    ``gravada + cero + por_asignar`` es exactamente el monto según libros que
    publica la hoja de mayores.
    """
    ventas = {c for c, k in categorias.items() if k == "VENTAS"}
    iva_ventas = {c for c, k in categorias.items() if k == "IVA_VENTAS"}
    monto = _lado_que_aumenta("VENTAS")

    por_asiento: dict[str, list[Movimiento]] = defaultdict(list)
    for m in movimientos:
        if m.codigo in ventas or m.codigo in iva_ventas:
            por_asiento[m.asiento].append(m)

    salida: dict[str, dict[str, dict[str, float]]] = {
        codigo: {b: {} for b in BUCKETS} for codigo in ventas
    }

    def anotar(bucket: str, lineas) -> None:
        for m in lineas:
            if not m.mes:
                continue
            destino = salida[m.codigo][bucket]
            destino[m.mes] = round(destino.get(m.mes, 0.0) + monto(m), 2)

    for movs in por_asiento.values():
        lineas = [m for m in movs if m.codigo in ventas]
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
