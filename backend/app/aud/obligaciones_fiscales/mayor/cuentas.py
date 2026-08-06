"""Movimientos → perfil por cuenta."""

from __future__ import annotations

from collections import Counter, defaultdict

from backend.app.aud.obligaciones_fiscales.mayor.catalogo import CATEGORIAS
from backend.app.aud.obligaciones_fiscales.mayor.tipos import Movimiento, PerfilCuenta

# Naturalezas que aumentan por el débito. Las demás (pasivo, ingreso,
# patrimonio) aumentan por el crédito.
_NATURALEZAS_DEUDORAS = frozenset({"activo", "gasto"})

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
            p.por_mes_debe[m.mes] = round(p.por_mes_debe.get(m.mes, 0.0) + m.debe, 2)
            p.por_mes_haber[m.mes] = round(p.por_mes_haber.get(m.mes, 0.0) + m.haber, 2)
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


def monto_segun_libros(perfil: PerfilCuenta, categoria: str | None) -> dict[str, float]:
    """El monto "según libros" de cada mes: el lado que AUMENTA la cuenta.

    Las cuentas de activo y gasto aumentan por el débito (p.ej. el IVA en
    compras que se carga con cada factura); las de pasivo, ingreso y
    patrimonio aumentan por el crédito (p.ej. las ventas). Usar el NETO
    (débito menos crédito, ``PerfilCuenta.por_mes``) mezcla el movimiento
    propio del mes con los asientos de liquidación o cierre que se
    registran ese mismo mes contra la cuenta, y el resultado deja de
    corresponder a lo que el cliente declaró al SRI.

    Caso real que detectó este defecto (cliente IMPUESTOS MEDI, cédula
    DM4): la cuenta "IVA sobre Compras" tuvo 659,57 de débito por las
    compras de enero y 659,60 de crédito por la liquidación del mismo
    mes contra el pasivo de IVA. El neto da -0,03; lo que el cliente
    declaró (y lo que el papel de trabajo del auditor muestra en "Según
    libros") es el débito bruto: 659,57.

    Si la categoría no está en el catálogo (cuenta sin clasificar), se
    usa el débito por defecto.
    """
    cat = CATEGORIAS.get(categoria or "")
    usa_debe = cat is None or cat.naturaleza_esperada in _NATURALEZAS_DEUDORAS
    lado = perfil.por_mes_debe if usa_debe else perfil.por_mes_haber
    return dict(lado)
