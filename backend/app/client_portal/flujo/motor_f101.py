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
