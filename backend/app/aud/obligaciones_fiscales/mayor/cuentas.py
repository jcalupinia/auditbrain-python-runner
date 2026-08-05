"""Movimientos → perfil por cuenta."""

from __future__ import annotations

from collections import Counter, defaultdict

from backend.app.aud.obligaciones_fiscales.mayor.tipos import Movimiento, PerfilCuenta

MAX_DESCRIPCIONES = 20
MAX_CONTRAPARTIDAS = 5


def _prefijo(asiento: str) -> str:
    partes = asiento.split()
    return partes[0].upper() if partes else ""


def _contrapartidas(movimientos: list[Movimiento]) -> dict[str, list[tuple[str, int]]]:
    """Cuentas que aparecen en el mismo número de asiento.

    Con un mayor filtrado a cuentas de impuestos casi no hay asientos
    compartidos: la señal simplemente no aporta, no penaliza.
    """
    por_asiento: dict[str, set[str]] = defaultdict(set)
    for m in movimientos:
        if m.asiento:
            por_asiento[m.asiento].add(m.codigo)

    conteo: dict[str, Counter] = defaultdict(Counter)
    for cuentas in por_asiento.values():
        if len(cuentas) < 2:
            continue
        for codigo in cuentas:
            for otra in cuentas:
                if otra != codigo:
                    conteo[codigo][otra] += 1

    return {
        codigo: c.most_common(MAX_CONTRAPARTIDAS) for codigo, c in conteo.items()
    }


def perfilar(movimientos: list[Movimiento]) -> dict[str, PerfilCuenta]:
    """Agrupa los movimientos por código de cuenta."""
    perfiles: dict[str, PerfilCuenta] = {}
    prefijos: dict[str, Counter] = defaultdict(Counter)

    for m in movimientos:
        p = perfiles.get(m.codigo)
        if p is None:
            p = PerfilCuenta(codigo=m.codigo, nombre=m.cuenta)
            perfiles[m.codigo] = p
        if not p.nombre and m.cuenta:
            p.nombre = m.cuenta
        p.n_movimientos += 1
        p.debe = round(p.debe + m.debe, 2)
        p.haber = round(p.haber + m.haber, 2)
        if m.mes:
            p.por_mes[m.mes] = round(p.por_mes.get(m.mes, 0.0) + m.neto, 2)
        pref = _prefijo(m.asiento)
        if pref:
            prefijos[m.codigo][pref] += 1
        if m.descripcion and len(p.descripciones) < MAX_DESCRIPCIONES:
            p.descripciones.append(m.descripcion)

    for codigo, contador in prefijos.items():
        perfiles[codigo].prefijos_asiento = dict(contador)

    for codigo, pares in _contrapartidas(movimientos).items():
        if codigo in perfiles:
            perfiles[codigo].contrapartidas = pares

    return perfiles
