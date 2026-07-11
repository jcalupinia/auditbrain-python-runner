# backend/app/client_portal/flujo/exportadores.py
"""Exportadores de los estados financieros al formato de envío electrónico
(Superintendencia de Compañías / SRI).

Cada estado se baja como un .txt con una línea ``codigo valor`` por rubro, en el
orden oficial de presentación — replicando las macros "Generar TXT" del modelo
Excel del cliente. El valor va con 2 decimales, punto decimal y sin separador de
miles.

Reglas de signo (validadas línea por línea contra el modelo SIGMAN):
- **ESF**: Activo (código 1…) tal cual; Pasivo (2…) y Patrimonio (3…) con signo
  invertido (se presentan como magnitudes positivas).
- **ERI**: cuentas tal cual; los 9 subtotales computados (ganancia bruta,
  utilidades, ORI y resultado integral) se toman de la cascada de resultados.
"""
from __future__ import annotations

from . import catalogos, motor_f101

# Subtotales computados del ERI: código oficial -> clave en cascada_resultados.
_ERI_SUBTOTAL_KEYS = {
    "402": "ganancia_bruta",       # GANANCIA BRUTA
    "600": "utilidad_operativa",   # GANANCIA ANTES DE 15% PARTICIPACIÓN
    "602": "utilidad_antes_ir",    # GANANCIA ANTES DE IMPUESTOS
    "604": "utilidad_operaciones", # GANANCIA DE OPERACIONES CONTINUADAS
    "607": "utilidad_neta",        # GANANCIA NETA
    "707": "utilidad_neta",        # GANANCIA NETA DEL PERIODO
}
_ERI_ORI_CODES = ("800", "80005")  # Otro resultado integral (del año) = ORI
_ERI_RESULTADO_INTEGRAL = "801"    # = utilidad neta + ORI

# Códigos que aparecen en la hoja del estado pero NO en el TXT de envío
# (memos/reclasificaciones ya capturadas en otro rubro; incluirlas duplicaría).
_ESF_TXT_EXCLUIR = frozenset({"30505"})  # Ganancias actuariales (reclass OCI)


def _fmt(valor) -> str:
    """Formatea el valor: 2 decimales, punto decimal, sin miles, sin -0.00."""
    v = round(float(valor), 2)
    if v == 0:
        v = 0.0
    return f"{v:.2f}"


def _linea(codigo: str, valor) -> str:
    return f"{codigo} {_fmt(valor)}"


def txt_esf(totales_esf: dict, estructura=None) -> str:
    """TXT del Estado de Situación Financiera (formato Super Cías).

    `totales_esf`: salida de ``motor.totales_por_codigo`` con la estructura ESF.
    """
    est = estructura if estructura is not None else catalogos.cargar_estructura("esf")
    lineas = []
    vistos: set[str] = set()
    for nodo in est:
        cod = nodo.codigo
        if cod in vistos or cod in _ESF_TXT_EXCLUIR:
            continue
        vistos.add(cod)
        raw = float(totales_esf.get(cod, 0.0))
        valor = raw if cod.startswith("1") else -raw
        lineas.append(_linea(cod, valor))
    return "\n".join(lineas) + "\n"


def txt_eri(totales_eri: dict, cascada: dict, ori: float, estructura=None) -> str:
    """TXT del Estado de Resultados Integral (formato Super Cías).

    `cascada`: salida de ``motor_er.cascada_resultados``. `ori`: casillero 885
    (``motor_f101.ori_del_periodo``)."""
    est = estructura if estructura is not None else catalogos.cargar_estructura("eri")
    ori_val = round(float(ori), 2)
    lineas = []
    for nodo in est:
        cod = nodo.codigo
        if cod in _ERI_SUBTOTAL_KEYS:
            valor = cascada.get(_ERI_SUBTOTAL_KEYS[cod], 0.0)
        elif cod in _ERI_ORI_CODES:
            valor = ori_val
        elif cod == _ERI_RESULTADO_INTEGRAL:
            valor = round(float(cascada.get("utilidad_neta", 0.0)) + ori_val, 2)
        else:
            valor = float(totales_eri.get(cod, 0.0))
        lineas.append(_linea(cod, valor))
    return "\n".join(lineas) + "\n"


def xml_101(balanza_actual: list[dict], balanza_anterior: list[dict] | None = None,
            agregados: dict | None = None) -> str:
    """XML de detalle del Formulario 101 (SRI). Inyecta el casillero 885 (ORI)
    calculado por reclasificación actuarial si se pasa la balanza anterior."""
    agg = agregados if agregados is not None else catalogos.cargar_agregados_f101()
    extras = None
    if balanza_anterior is not None:
        extras = {"885": motor_f101.ori_del_periodo(balanza_anterior, balanza_actual)}
    casilleros = motor_f101.casilleros_completos(balanza_actual, agg, extras=extras)
    return motor_f101.generar_xml_101(casilleros)
