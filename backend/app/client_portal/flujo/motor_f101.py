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
