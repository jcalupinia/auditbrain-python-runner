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


def ambos_lados(perfil: PerfilCuenta) -> dict[str, dict[str, float]]:
    """Los dos lados brutos por mes, para persistir sin perder información.

    Se guarda ``{"debe": {...}, "haber": {...}}`` (ambos ≥ 0) en vez de un
    solo lado elegido por la categoría: así, cuando el auditor RECLASIFICA una
    cuenta a una categoría de naturaleza contable distinta, el "según libros"
    se vuelve a elegir del lado correcto al armar el libro, sin recomputar nada
    ni releer el mayor. Antes se guardaba un solo lado (el de la categoría
    SUGERIDA) y reclasificar dejaba el signo equivocado.
    """
    return {"debe": dict(perfil.por_mes_debe), "haber": dict(perfil.por_mes_haber)}


# Categorías que se miden por el NETO (haber − débito), no por el lado bruto:
# las ventas, para que las NOTAS DE CRÉDITO (débitos a la cuenta de ingreso)
# resten a las ventas, como en el papel de trabajo del auditor. El resto de
# categorías acreedoras (IVA en ventas, retenciones) usan el lado bruto para
# NO restar los asientos de liquidación/declaración del mes.
_CATEGORIAS_NETAS = frozenset({"VENTAS"})


def lado_para_categoria(
    por_mes_json: dict | None, categoria: str | None
) -> dict[str, float]:
    """Elige, de ``ambos_lados``, el monto "según libros" de la categoría.

    - VENTAS: NETO (haber − débito), para que las notas de crédito resten.
    - Activo/gasto: débito bruto. Pasivo/ingreso/patrimonio: crédito bruto
      (excluye los asientos de liquidación del mes). Sin categoría: débito.

    Compatibilidad hacia atrás: los jobs viejos guardaron ``por_mes_json`` como
    un dict plano ``{mes: valor}`` (un solo lado ya elegido); ese caso se
    devuelve tal cual, porque no hay forma de recuperar el otro lado.
    """
    if not por_mes_json:
        return {}
    if "debe" in por_mes_json or "haber" in por_mes_json:
        debe = por_mes_json.get("debe") or {}
        haber = por_mes_json.get("haber") or {}
        if categoria in _CATEGORIAS_NETAS:
            meses = set(debe) | set(haber)
            return {m: round(haber.get(m, 0.0) - debe.get(m, 0.0), 2) for m in meses}
        cat = CATEGORIAS.get(categoria or "")
        usa_debe = cat is None or cat.naturaleza_esperada in _NATURALEZAS_DEUDORAS
        return dict(debe if usa_debe else haber)
    return dict(por_mes_json)  # forma plana antigua
