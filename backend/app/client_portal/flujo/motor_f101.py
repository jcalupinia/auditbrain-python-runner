# backend/app/client_portal/flujo/motor_f101.py
"""Motor del Formulario 101 (SRI): agrupación de la balanza por Código SRI
(SUMIF, análogo a ``motor.homologar_balanza`` pero con el código SRI) y
generación del XML de detalle de declaración."""
from __future__ import annotations


def casilleros_f101(balanza: list[dict]) -> dict[str, float]:
    """Agrupa las filas de la balanza por su Código SRI (SUMIF).

    `balanza`: lista de filas ``{"sri": <codigo_sri>, "saldo": <float>}``.
    Las filas sin código SRI se ignoran (no forman parte del F-101).
    Devuelve ``{casillero_sri: valor}`` con cada total redondeado a 2 decimales.
    """
    casilleros: dict[str, float] = {}
    for fila in balanza:
        cod = str(fila.get("sri") or "").strip()
        if not cod:
            continue
        try:
            saldo = float(fila.get("saldo") or 0.0)
        except (TypeError, ValueError):
            saldo = 0.0
        casilleros[cod] = round(casilleros.get(cod, 0.0) + saldo, 2)
    return casilleros


def casilleros_completos(balanza: list[dict], agregados: dict[str, list[str]],
                         extras: dict[str, float] | None = None) -> dict[str, float]:
    """Casilleros HOJA (SUMIF por SRI) + agregados (suma de casilleros hijos con signo).
    `extras` = casilleros calculados fuera (ej. derivados del ER) que se inyectan antes
    de resolver los agregados."""
    val: dict[str, float] = dict(casilleros_f101(balanza))
    if extras:
        val.update({k: round(float(v), 2) for k, v in extras.items()})

    def calc(cas: str, visto: set) -> float:
        if cas in val:
            return val[cas]
        if cas not in agregados or cas in visto:
            return 0.0
        visto.add(cas)
        total = 0.0
        for tok in agregados[cas]:
            signo = -1.0 if tok[0] == "-" else 1.0
            hijo = tok.lstrip("+-").strip()
            total += signo * calc(hijo, visto)
        val[cas] = round(total, 2)
        return val[cas]

    for cas in agregados:
        calc(cas, set())
    return val


# Cuentas contables (Super Cías 30601) que en realidad son OCI actuarial y se
# reclasifican a patrimonio (código 30505). Se identifican por su código de cuenta
# porque comparten el código Super Cías con "resultados acumulados". Fuente: bloque
# de reclasificación N/O del Mapeo del modelo (O16 = E185+E186).
CUENTAS_ORI_ACTUARIAL = ("3020301002", "3020301003")


def _normaliza_cuenta(cod) -> str:
    return str(cod or "").replace(".", "").strip()


def ori_del_periodo(balanza_ant: list[dict], balanza_act: list[dict],
                    cuentas_ori: tuple[str, ...] = CUENTAS_ORI_ACTUARIAL) -> float:
    """Casillero 885 (Otro resultado integral del año) = movimiento OCI del período.

    Es la **variación** entre año actual y anterior de las cuentas actuariales
    reclasificadas a patrimonio (30505). Como esas cuentas comparten el código
    Super Cías 30601 con "resultados acumulados", NO se pueden aislar por total de
    código: se identifican por su **código de cuenta contable** (campo ``cuenta``).
    """
    objetivo = {_normaliza_cuenta(c) for c in cuentas_ori}

    def _suma(bal: list[dict]) -> float:
        total = 0.0
        for fila in bal:
            if _normaliza_cuenta(fila.get("cuenta")) in objetivo:
                try:
                    total += float(fila.get("saldo") or 0.0)
                except (TypeError, ValueError):
                    pass
        return round(total, 2)

    return round(_suma(balanza_act) - _suma(balanza_ant), 2)


def generar_xml_101(casilleros: dict[str, float]) -> str:
    """Genera el XML de detalle de declaración del F-101.

    Solo incluye casilleros con valor distinto de cero, ordenados por
    código de casillero ascendente (numérico). El valor se formatea con
    2 decimales y punto decimal.
    """
    lineas = ["<detalleDeclaracion>"]
    for cod in sorted(casilleros, key=lambda c: int(c)):
        valor = casilleros[cod]
        if valor == 0:
            continue
        lineas.append(f'  <campo codigo="{cod}">{valor:.2f}</campo>')
    lineas.append("</detalleDeclaracion>")
    return "\n".join(lineas)
