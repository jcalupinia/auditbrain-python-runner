"""Mapea el NOMBRE de un concepto de un EEFF resumido a (seccion, clave).

Diccionario EXPLÍCITO y auditado — sin herencia stateful (política CLAUDE.md).
seccion ∈ {'activo','pasivo','patrimonio','resultado','total'}.
"""
from __future__ import annotations
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.upper().split())


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
    n = _norm(nombre)
    # 'TOTAL'/'SUBTOTAL' solo cuadran si el nombre EMPIEZA con esa palabra; así
    # una fila de total/subtotal se reconoce, pero un concepto legítimo que
    # contenga "total" en medio (ej. "Otros resultados totales") NO se descarta.
    if n.startswith("TOTAL") or n.startswith("SUBTOTAL"):
        return ("total", None)
    # 'IMPUESTOS CORRIENTES' aparece en activo y pasivo: se desambigua por
    # 'ACTIVOS'/'PASIVOS' si el nombre lo trae; si no, cae en activo.
    for token, sec, key in _REGLAS:
        if token in n:
            if key == "impRec" and "PASIV" in n:
                return ("pasivo", "impPagar")
            return (sec, key)
    return (None, None)
