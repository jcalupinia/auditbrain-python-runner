"""Análisis de estados financieros homologados (NIA 315 / NIA 520).

Toma la salida de ``motor_balances.estados_superintendencia`` (ESF y ERI
estructurados por Código Super Cías, con N columnas de período) y calcula, de
forma determinista:

  - **Vertical**: peso de cada rubro sobre su base (Activo total en el ESF,
    Ingresos de actividades ordinarias en el ERI).
  - **Horizontal**: variación absoluta y porcentual entre el período anterior
    y el corte.
  - **Ratios** de la firma (liquidez, endeudamiento, apalancamiento, márgenes,
    ROA, ROE) sobre los subtotales oficiales.
  - **Expectativa vs. real (NIA 520)**: la expectativa por defecto es el
    período anterior; la diferencia que supera el umbral se marca para explicar.

Python calcula; el papel de trabajo recalcula las mismas cifras con fórmulas de
Excel (ver ``papel_estados.py``). No usa LLM.
"""
from __future__ import annotations

# Códigos Super Cías usados por los ratios (raíces y subtotales oficiales).
COD_ACTIVO = "1"
COD_ACTIVO_CORRIENTE = "101"
COD_PASIVO = "2"
COD_PASIVO_CORRIENTE = "201"
COD_PATRIMONIO = "3"
COD_INGRESOS = "401"          # ingresos de actividades ordinarias (base vertical ERI)
COD_COSTO_VENTAS = "501"      # costo de ventas y producción

# Un numerador/denominador es un código (rollup poblado por la homologación) o
# una diferencia de dos códigos ("-", a, b). Solo se incluyen ratios cuyos
# componentes son rollups confiables del homologado: los subtotales DERIVADOS
# del ERI (402 ganancia bruta, 6xx resultados) no los llena la homologación por
# prefijo, así que márgenes netos, ROA y ROE quedan para la herramienta de
# Planificación NIA, que arma el ERI con sus convenciones de signo.
# (nombre, numerador, denominador, origen, formato).
RATIOS = [
    ("Liquidez corriente", COD_ACTIVO_CORRIENTE, COD_PASIVO_CORRIENTE, "esf", "veces"),
    ("Endeudamiento del activo", COD_PASIVO, COD_ACTIVO, "esf", "razon"),
    ("Apalancamiento", COD_PASIVO, COD_PATRIMONIO, "esf", "veces"),
    ("Margen bruto", ("-", COD_INGRESOS, COD_COSTO_VENTAS), COD_INGRESOS, "eri", "pct"),
]


def _num(x) -> float:
    try:
        return round(float(x or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _por_codigo(estado: dict) -> dict:
    return {l["codigo"]: l for l in estado.get("lineas", [])}


def _valor(por: dict, codigo: str, i: int) -> float:
    vals = por.get(codigo, {}).get("valores", [])
    return _num(vals[i]) if i < len(vals) else 0.0


def _analizar_estado(estado: dict, base_codigo: str) -> dict:
    """Filas no-cero con vertical (sobre `base_codigo`) y horizontal."""
    periodos = estado.get("periodos", [])
    por = _por_codigo(estado)
    base = por.get(base_codigo, {}).get("valores", [0.0] * len(periodos))
    filas = []
    for l in estado.get("lineas", []):
        vals = [_num(v) for v in l.get("valores", [])]
        if not any(vals):
            continue
        fila = {"codigo": l["codigo"], "etiqueta": l["etiqueta"],
                "es_hoja": l.get("es_hoja", False), "valores": vals}
        fila["vertical"] = [
            (v / _num(base[i])) if i < len(base) and _num(base[i]) else 0.0
            for i, v in enumerate(vals)
        ]
        if len(vals) >= 2 and vals[-2]:
            fila["variacion"] = round(vals[-1] - vals[-2], 2)
            fila["variacion_pct"] = (vals[-1] - vals[-2]) / vals[-2]
        elif len(vals) >= 2:
            fila["variacion"] = round(vals[-1] - vals[-2], 2)
            fila["variacion_pct"] = None
        filas.append(fila)
    return {"periodos": periodos, "base_codigo": base_codigo, "lineas": filas}


def _componente(por: dict, spec, i: int) -> float:
    """Un componente de ratio: un código, o una diferencia ("-", a, b)."""
    if isinstance(spec, tuple):
        _, a, b = spec
        return _valor(por, a, i) - _valor(por, b, i)
    return _valor(por, spec, i)


def _ratios(homologado: dict) -> dict:
    esf, eri = homologado.get("esf", {}), homologado.get("eri", {})
    por = {"esf": _por_codigo(esf), "eri": _por_codigo(eri)}
    periodos = esf.get("periodos") or eri.get("periodos") or []
    filas = []
    for nombre, num_spec, den_spec, origen, fmt in RATIOS:
        p = por[origen]
        valores = []
        for i in range(len(periodos)):
            num = _componente(p, num_spec, i)
            den = _componente(p, den_spec, i)
            valores.append((num / den) if den else None)
        if any(v is not None for v in valores):
            filas.append({"nombre": nombre, "origen": origen, "formato": fmt,
                          "valores": valores})
    return {"periodos": periodos, "filas": filas}


def _expectativa(estado: dict, umbral_pct: float) -> dict:
    """NIA 520: expectativa = período anterior; diferencia sobre umbral → explicar."""
    periodos = estado.get("periodos", [])
    if len(periodos) < 2:
        return {"periodos": periodos, "aplicable": False, "lineas": []}
    filas = []
    for l in estado.get("lineas", []):
        vals = [_num(v) for v in l.get("valores", [])]
        if not l.get("es_hoja") or not any(vals):
            continue
        expectativa, real = vals[-2], vals[-1]
        diferencia = round(real - expectativa, 2)
        pct = (diferencia / expectativa) if expectativa else None
        supera = pct is not None and abs(pct) > umbral_pct
        filas.append({"codigo": l["codigo"], "etiqueta": l["etiqueta"],
                      "expectativa": expectativa, "real": real, "diferencia": diferencia,
                      "diferencia_pct": pct, "supera_umbral": supera})
    return {"periodos": periodos, "aplicable": True, "umbral_pct": umbral_pct,
            "lineas": filas}


def analizar(homologado: dict, umbral_pct: float = 0.10) -> dict:
    """Análisis completo a partir de la salida de ``estados_superintendencia``."""
    esf, eri = homologado.get("esf", {}), homologado.get("eri", {})
    return {
        "esf": _analizar_estado(esf, COD_ACTIVO),
        "eri": _analizar_estado(eri, COD_INGRESOS),
        "ratios": _ratios(homologado),
        "expectativa_esf": _expectativa(esf, umbral_pct),
        "expectativa_eri": _expectativa(eri, umbral_pct),
        "umbral_pct": umbral_pct,
    }
