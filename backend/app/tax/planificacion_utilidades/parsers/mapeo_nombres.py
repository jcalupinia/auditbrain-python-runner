"""Mapea el NOMBRE de un concepto de un EEFF resumido a (seccion, clave).

Diccionario EXPLÍCITO y auditado — sin herencia stateful (política CLAUDE.md).
seccion ∈ {'activo','pasivo','patrimonio','resultado','total'}.
"""
from __future__ import annotations
from ._shared import _norm
from .balance_interno import _fix_mojibake


# (subcadena normalizada, seccion, clave). Primera coincidencia gana; el orden
# importa: reglas más específicas antes que las genéricas.
_REGLAS = [
    ("EFECTIVO", "activo", "efectivo"),
    ("INVENTARIO", "activo", "inventario"),
    ("PROPIEDAD", "activo", "ppe"),
    ("IMPUESTOS DIFERIDOS", "activo", "actImpDif"),
    ("IMPUESTOS CORRIENTES", "activo", "impRec"),
    ("COBRAR", "activo", "cxc"),
    ("PAGOS ANTICIPADOS", "activo", "otrasCxc"),
    ("PAGAR RELACIONAD", "pasivo", "cxpRel"),
    ("IMPUESTO DIFERIDO", "pasivo", "pasImpDif"),
    ("PAGAR", "pasivo", "cxp"),
    ("ANTICIPOS DE CLIENTES", "pasivo", "anticipos"),
    ("BENEFICIOS SOCIALES", "pasivo", "benef"),
    ("OBLIGACIONES ACUMULADAS", "pasivo", "benef"),
    ("BENEFICIOS DEFINIDOS", "pasivo", "benefPost"),
    ("CAPITAL", "patrimonio", "capital"),
    ("RESERVA", "patrimonio", "reservas"),
    ("REVALUACION", "patrimonio", "ori"),
    ("ADOPCION NIIF", "patrimonio", "resAcum"),
    ("RESULTADOS ACUMULADOS", "patrimonio", "resAcum"),
    ("RESULTADO DEL EJERCICIO", "patrimonio", "utilEjercicio"),
    ("INGRESOS ORDINARIOS", "resultado", "ventas"),
    ("COSTO", "resultado", "costo"),
    ("ADMINISTRACION", "resultado", "gAdmin"),
    ("FINANCIER", "resultado", "gFin"),
    ("NO ORDINARIAS", "resultado", "otrosIng"),
    ("PARTICIPACION TRABAJADORES", "resultado", "partTrab"),
    ("IMPUESTO A LA RENTA", "resultado", "irCausado"),
]


def mapear_concepto(nombre: str):
    # Reparar mojibake (UTF-8 leído como cp1252) antes de normalizar, para que
    # este camino sea consistente con el codificado (que ya lo aplica).
    n = _norm(_fix_mojibake(str(nombre)))
    # 'TOTAL'/'SUBTOTAL' solo cuadran si el nombre EMPIEZA con esa palabra; así
    # una fila de total/subtotal se reconoce, pero un concepto legítimo que
    # contenga "total" en medio (ej. "Otros resultados totales") NO se descarta.
    if n.startswith("TOTAL") or n.startswith("SUBTOTAL"):
        return ("total", None)
    # Impuestos corrientes: colisionan entre activo (por recuperar) y pasivo
    # (por pagar). Un impuesto es PASIVO si el nombre trae cualquier marcador de
    # obligación (PAGAR / PASIV / OBLIGACION); si no, es ACTIVO (impRec). Se
    # resuelve ANTES del diccionario para no fusionar un pasivo en el activo ni
    # que la regla genérica "PAGAR" lo mande a 'cxp'. Excluye impuestos
    # DIFERIDOS (rubro propio) y el IMPUESTO A LA RENTA del ERI sin marcador de
    # pasivo (que debe seguir siendo 'irCausado').
    if "IMPUEST" in n and "DIFERID" not in n:
        pasivo = any(m in n for m in ("PAGAR", "PASIV", "OBLIGACION"))
        corriente = "CORRIENTE" in n
        if pasivo:
            return ("pasivo", "impPagar")
        if corriente:
            return ("activo", "impRec")
    for token, sec, key in _REGLAS:
        if token in n:
            if key == "impRec" and "PASIV" in n:
                return ("pasivo", "impPagar")
            return (sec, key)
    return (None, None)
