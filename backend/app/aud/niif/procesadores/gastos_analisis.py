"""Gastos: análisis global, vouching, corte, devengo, gastos anticipados, clasificación, partes
relacionadas y partidas extraordinarias o inusuales.

Versión simple que cumple la norma (especificación del socio, MÓDULO 16 · EXP-01..13, lo que sirve a las
pruebas de la matriz). Dos anexos:

- ``cuentas`` (principal): sumaria por cuenta de gasto con su línea del estado de resultados, saldo actual,
  saldo anterior y, si existe, presupuesto. Total de control = saldo actual.
- ``transacciones``: muestra de comprobantes (del ejercicio y posteriores al corte) con fechas de documento,
  registro y período del servicio, y las marcas del auditor (soporte, comprobante válido, bancarización,
  parte relacionada, cuenta sugerida, inusual).

1. Análisis global (NIA 520): variación = actual − anterior (y − presupuesto); excede el umbral si
   |variación| > umbral absoluto y, cuando hay base, |variación %| > umbral %. Variación sobre el umbral sin
   explicación = problema. Cobertura de la muestra por cuenta.
2. Presentación (NIC 1 99, 102–105; PYMES 5.11): gasto por línea del estado de resultados; ninguna partida
   «extraordinaria» (NIC 1 87; PYMES 5.10). Enrutado por marco: si el método es por función, NIIF completas
   exige información por naturaleza (NIC 1 104) y PYMES exige el costo de ventas por separado (5.11 b).
3. Vouching (NIA 500): gasto registrado sin soporte = gasto no soportado.
4. Corte (transacciones sin período de servicio): documento del ejercicio registrado después del corte =
   gasto no registrado; documento posterior registrado en el ejercicio = gasto de otro período.
5. Devengo (transacciones con período de servicio; NIC 1 27–28; PYMES 2.36): gasto del período = importe ×
   días del servicio hasta el corte ÷ días del servicio. Registrado en el ejercicio → la porción posterior
   al corte es gasto anticipado llevado a resultados; registrado después → la porción del período es gasto
   devengado no registrado (pasivo).
6. Clasificación: cuenta sugerida por el auditor ≠ cuenta registrada = reclasificación.
7. Partes relacionadas (NIC 24 18–19; PYMES 33.9–33.10): importe del período por categoría (las categorías
   cambian por marco) frente a lo revelado en notas.
8. Partidas inusuales: las de importe igual o mayor a la materialidad se revelan por separado (NIC 1 97; se usa la materialidad de ejecución como aproximación (NIC 1.97 se refiere a la importancia relativa)).
9. Tributario Ecuador (referencia): sin comprobante de venta válido (LRTI art. 10 num. 1) o sin bancarización sobre el
   umbral (Reglamento LRTI art. 27, reforma 2024, por caso entendido; el art. 103 de la LRTI fija el uso del sistema
   financiero) → no deducible (umbral como parámetro, vigente al corte; VERIFICAR).
10. Ajuste propuesto al gasto = no registrados + devengados no registrados − otro período − anticipados (M09).

Norma leída (M03): NIC 1 párr. 27–28, 87, 97–99, 102–105; NIC 24 párr. 18–19; NIC 8 párr. 41–42 en el
Reglamento (UE) 2023/1803 (EUR-Lex, español); NIIF para las PYMES 2015 párr. 2.23, 2.26, 2.36, 5.9–5.11,
33.9–33.10. Marco Conceptual (definición de gasto) y PYMES 2025: numeración no leída → «VERIFICAR».
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja, m,
    n2, norm, problema, r2, ref, req, suma, validar_campos, validar_definicion_generica,
)

VERSION = "gastos_analisis 1.0"
RUBRO = "COSTOS_GASTOS"

_CUENTAS = [
    campo("id", "Código de cuenta", alias=("cuenta", "codigo", "código", "codigo cuenta", "cta"), ejemplo="5201"),
    campo("nombre", "Nombre de la cuenta", alias=("descripcion", "descripción", "nombre cuenta", "detalle"), ejemplo="Sueldos y beneficios"),
    campo("clasificacion", "Línea del estado de resultados (función o naturaleza)",
          alias=("clasificacion", "clasificación", "linea eri", "rubro", "grupo", "funcion", "función"), ejemplo="Gastos de administración"),
    campo("naturaleza", "Naturaleza del gasto", requerido=False, alias=("naturaleza", "tipo de gasto"), ejemplo="Beneficios a empleados"),
    campo("saldo_actual", "Saldo año actual", "number", alias=("saldo actual", "año actual", "saldo", "actual"), ejemplo="180000"),
    campo("saldo_anterior", "Saldo año anterior", "number", False, ("saldo anterior", "año anterior", "anterior", "comparativo"), "150000"),
    campo("presupuesto", "Presupuesto", "number", False, ("presupuesto", "ppto", "budget"), "175000"),
    campo("explicacion", "Explicación de la variación", requerido=False, alias=("explicacion", "explicación", "comentario", "justificacion"), ejemplo=""),
]
_TRANS = [
    campo("id", "Comprobante", alias=("comprobante", "factura", "documento", "numero", "n factura"), ejemplo="001-001-000101"),
    campo("fecha_documento", "Fecha del documento", "date", alias=("fecha documento", "fecha factura", "fecha emision", "emision"), ejemplo="2025-12-20"),
    campo("fecha_registro", "Fecha de registro", "date", alias=("fecha registro", "fecha contable", "fecha asiento"), ejemplo="2026-01-08"),
    campo("servicio_desde", "Servicio desde", "date", False, ("desde", "periodo desde", "servicio desde", "inicio servicio"), ""),
    campo("servicio_hasta", "Servicio hasta", "date", False, ("hasta", "periodo hasta", "servicio hasta", "fin servicio"), ""),
    campo("importe", "Importe", "number", alias=("valor", "monto", "importe", "subtotal"), ejemplo="4500"),
    campo("cuenta", "Cuenta registrada", alias=("cuenta", "cuenta contable", "codigo cuenta"), ejemplo="5202"),
    campo("proveedor", "Proveedor", alias=("proveedor", "beneficiario", "razon social"), ejemplo="Consultores Delta"),
    campo("soporte", "Tiene soporte (Sí/No)", requerido=False, alias=("soporte", "tiene soporte", "documentado"), ejemplo="Sí"),
    campo("comprobante_valido", "Comprobante válido SRI (Sí/No)", requerido=False, alias=("comprobante valido", "valido sri", "autorizado sri"), ejemplo="Sí"),
    campo("bancarizado", "Pagado por banco (Sí/No)", requerido=False, alias=("bancarizado", "pagado por banco", "medio de pago"), ejemplo="Sí"),
    campo("parte_relacionada", "Parte relacionada (Sí/No)", requerido=False, alias=("parte relacionada", "relacionada", "rp"), ejemplo="No"),
    campo("categoria_rp", "Categoría de parte relacionada", requerido=False, alias=("categoria rp", "categoria parte relacionada", "tipo de relacion"), ejemplo=""),
    campo("cuenta_sugerida", "Cuenta correcta según el auditor", requerido=False, alias=("cuenta sugerida", "cuenta correcta", "reclasificar a"), ejemplo=""),
    campo("inusual", "Partida inusual o no recurrente (Sí/No)", requerido=False, alias=("inusual", "extraordinaria", "no recurrente"), ejemplo="No"),
]
CAMPOS = {"cuentas": _CUENTAS, "transacciones": _TRANS}
TIPOS = {"cuentas": "cuentas", "transacciones": "transacciones"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "cuentas"
CONTROL = "saldo_actual"

METODOS = ("Función", "Naturaleza")
PARAMETROS = {"metodoEri": "Función", "umbralVarPct": 10, "umbralVarAbs": None, "materialidadEjecucion": None,
              "umbralBancarizacion": 500, "gastosSegunEri": None, "rpRevelado": None}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "metodoEri": "Método de desglose del estado de resultados (Función / Naturaleza)",
    "umbralVarPct": "Umbral de variación de la NIA 520 (%)",
    "umbralVarAbs": "Umbral de variación de la NIA 520 (importe; vacío = materialidad de ejecución)",
    "materialidadEjecucion": "Materialidad de ejecución",
    "umbralBancarizacion": "Umbral de bancarización (USD por caso entendido — contrato —, Reglamento LRTI art. 27; vigente al corte; VERIFICAR)",
    "gastosSegunEri": "Total de gastos según el estado de resultados / mayor",
    "rpRevelado": "Transacciones con partes relacionadas reveladas en notas",
}
TOTAL_EJEMPLO = "ajusteGasto"

# Categorías de revelación de partes relacionadas: NIC 24.19 (siete) y PYMES 33.10 (cuatro).
CATEGORIAS_RP = {
    "completas": ["Dominante", "Control conjunto o influencia significativa", "Dependiente", "Asociada", "Negocio conjunto",
                  "Personal clave", "Otra"],
    "pymes": ["Control, control conjunto o influencia significativa sobre la entidad", "Controlada o influida por la entidad", "Personal clave", "Otra"],
}
SIN_CATEGORIA = "Sin categoría válida"

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Analisis_global", "Análisis global por cuenta (NIA 520)"),
    ("04_Presentacion_ERI", "Presentación en el estado de resultados"), ("05_Transacciones", "Transacciones de la muestra"),
    ("06_Vouching", "Verificación del soporte documental"), ("07_Corte", "Corte de gastos"), ("08_Devengo", "Devengo y gastos anticipados"),
    ("09_Reclasificaciones", "Reclasificaciones"), ("10_Partes_relacionadas", "Partes relacionadas"),
    ("11_Inusuales", "Partidas inusuales"), ("12_Tributario", "Referencia tributaria (Ecuador)"),
    ("13_Ajustes", "Ajustes y conciliación"), ("14_Asientos", "Asientos propuestos"), ("15_Problemas", "Problemas encontrados"),
]

_SI = {"si", "s", "x", "yes", "y", "1", "true", "verdadero"}
_NO = {"no", "n", "0", "false", "falso"}
_BOOL = ("soporte", "comprobante_valido", "bancarizado", "parte_relacionada", "inusual")


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def _sino(v):
    """«Sí» / «No» / None (vacío = no informado, M22); ValueError si no se entiende."""
    k = norm(v)
    if not k:
        return None
    if k in _SI:
        return "Sí"
    if k in _NO:
        return "No"
    raise ValueError(v)


def validar_filas(tipo: str, filas: list) -> dict:
    r = validar_campos(CAMPOS[tipo], filas)
    if tipo == "transacciones":
        for f in filas:
            for k in _BOOL:
                try:
                    _sino(f.get(k))
                except ValueError:
                    r["errors"].append({"row": f.get("_row"), "field": k, "message": "Use Sí o No."})
            d, h = fecha(f.get("servicio_desde")), fecha(f.get("servicio_hasta"))
            if (d is None) != (h is None) or (d and h and h < d):
                r["errors"].append({"row": f.get("_row"), "field": "servicio_hasta", "message": "Período del servicio incompleto o con fin anterior al inicio."})
    r["ok"] = not r["errors"]
    return r


# --- cálculo -----------------------------------------------------------------

def _opc(f, k):
    v = str(f.get(k, "") or "").strip()
    return a_num(v) if v else None


def _pnum(p, k):
    v = p.get(k)
    return None if v is None or str(v).strip() == "" else float(a_num(v))


def _txt(f, k):
    return str(f.get(k, "") or "").strip()


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    pymes = es_pymes(p)
    metodo = next((x for x in METODOS if norm(x) == norm(p.get("metodoEri"))), None)
    if metodo is None:
        raise ValueError("Método de desglose del estado de resultados: use Función o Naturaleza.")
    upct, uabs_in, mat = _pnum(p, "umbralVarPct"), _pnum(p, "umbralVarAbs"), _pnum(p, "materialidadEjecucion")
    uban, eri, rp_rev = _pnum(p, "umbralBancarizacion"), _pnum(p, "gastosSegunEri"), _pnum(p, "rpRevelado")
    if upct is None or upct < 0:
        raise ValueError("Indique el umbral de variación en % (cero o positivo).")
    if any(x is not None and x < 0 for x in (uabs_in, mat, uban)):
        raise ValueError("Umbrales y materialidad no pueden ser negativos.")
    uabs = uabs_in if uabs_in is not None else mat
    if uabs is None:
        raise ValueError("Indique el umbral absoluto de variación de la NIA 520 o la materialidad de ejecución.")
    if uban is None:
        raise ValueError("Indique el umbral de bancarización.")

    # Cuentas (análisis global).
    cuentas = []
    for f in datasets.get("cuentas") or []:
        act = a_num(f.get("saldo_actual"))
        if act is None:
            continue
        ant, ppto = _opc(f, "saldo_anterior"), _opc(f, "presupuesto")
        var = None if ant is None else act - ant
        pct = None if ant in (None, 0) else var / ant
        exc = None if var is None else ("No" if abs(var) <= uabs else ("Sí" if ant == 0 or abs(pct) > upct / 100 else "No"))
        vpp = None if ppto is None else act - ppto
        ppct = None if ppto in (None, 0) else vpp / ppto
        excp = None if vpp is None else ("No" if abs(vpp) <= uabs else ("Sí" if ppto == 0 or abs(ppct) > upct / 100 else "No"))
        expl = _txt(f, "explicacion")
        nombre, clas = _txt(f, "nombre"), _txt(f, "clasificacion") or "(sin clasificar)"
        cuentas.append({"cuenta": _txt(f, "id"), "nombre": nombre, "clas": clas, "naturaleza": _txt(f, "naturaleza"), "actual": act,
                        "anterior": ant, "var": var, "pct": pct, "excede": exc, "ppto": ppto, "varPpto": vpp, "pctPpto": ppct,
                        "excedePpto": excp, "explicacion": expl, "sinExplicar": "Sí" if "Sí" in (exc, excp) and not expl else "No",
                        "extra": "Sí" if "extraordinari" in (nombre + " " + clas).lower() else "No", "_row": f.get("_row")})
    if not cuentas:
        raise ValueError("Cargue la sumaria de cuentas de gasto con su saldo del año actual.")
    idx_cta = {c["cuenta"].lower(): c for c in cuentas}

    # Transacciones de la muestra.
    trans = []
    for f in datasets.get("transacciones") or []:
        imp = a_num(f.get("importe"))
        fd, fr = fecha(f.get("fecha_documento")), fecha(f.get("fecha_registro"))
        if imp is None:
            continue
        if fd is None or fr is None:
            raise ValueError(f"Comprobante {f.get('id')}: faltan las fechas de documento o de registro.")
        de, ha = fecha(f.get("servicio_desde")), fecha(f.get("servicio_hasta"))
        if (de is None) != (ha is None) or (de and ha and ha < de):
            raise ValueError(f"Comprobante {f.get('id')}: período del servicio incompleto o con fin anterior al inicio.")
        try:
            b = {k: _sino(f.get(k)) for k in _BOOL}
        except ValueError as e:
            raise ValueError(f"Comprobante {f.get('id')}: «{e}» no es Sí ni No.") from None
        trans.append({"comp": _txt(f, "id"), "fdoc": fd, "freg": fr, "desde": de, "hasta": ha, "importe": imp,
                      "cuenta": _txt(f, "cuenta"), "proveedor": _txt(f, "proveedor"), **b,
                      "categoria": _txt(f, "categoria_rp"), "sugerida": _txt(f, "cuenta_sugerida"),
                      "enPeriodo": "Sí" if fr <= corte_a else "No", "conServicio": "Sí" if de else "No", "_row": f.get("_row")})
    for i, t in enumerate(trans):
        t["i"] = i
    reg = [t for t in trans if t["enPeriodo"] == "Sí"]
    for c in cuentas:
        c["muestra"] = sum(t["importe"] for t in reg if t["cuenta"].lower() == c["cuenta"].lower())
        c["cobertura"] = None if c["actual"] == 0 else c["muestra"] / c["actual"]

    # Corte (sin período de servicio).
    corte_l = [t for t in trans if t["conServicio"] == "No"]
    for t in corte_l:
        t["docEnPeriodo"] = "Sí" if t["fdoc"] <= corte_a else "No"
        t["otroPeriodo"] = t["importe"] if t["docEnPeriodo"] == "No" and t["enPeriodo"] == "Sí" else 0
        t["noRegistrado"] = t["importe"] if t["docEnPeriodo"] == "Sí" and t["enPeriodo"] == "No" else 0
    # Devengo (con período de servicio).
    dev_l = [t for t in trans if t["conServicio"] == "Sí"]
    for t in dev_l:
        t["dias"] = (t["hasta"] - t["desde"]).days + 1
        t["diasPeriodo"] = max(0, (min(t["hasta"], corte_a) - t["desde"]).days + 1)
        t["diasPost"] = t["dias"] - t["diasPeriodo"]
        t["gastoPeriodo"] = t["importe"] * t["diasPeriodo"] / t["dias"]
        t["anticipado"] = t["importe"] * t["diasPost"] / t["dias"] if t["enPeriodo"] == "Sí" else 0
        t["devNoReg"] = t["gastoPeriodo"] if t["enPeriodo"] == "No" else 0
    reclas = [t for t in reg if t["sugerida"] and t["sugerida"].lower() != t["cuenta"].lower()]
    clas_de = lambda cta: idx_cta[cta.lower()]["clas"] if cta.lower() in idx_cta else "(no en la sumaria)"
    for t in reclas:
        t["clasReg"], t["clasSug"] = clas_de(t["cuenta"]), clas_de(t["sugerida"])

    # Partes relacionadas por categoría (enrutado por marco).
    cats = CATEGORIAS_RP["pymes" if pymes else "completas"]
    rp = [t for t in reg if t["parte_relacionada"] == "Sí"]
    rp_tot = sum(t["importe"] for t in rp)
    rp_cat = []
    for c in cats:
        de_c = [t for t in rp if t["categoria"].lower() == c.lower()]
        rp_cat.append({"cat": c, "n": len(de_c), "importe": sum(t["importe"] for t in de_c)})
    validas = {c.lower() for c in cats}
    sin_cat = [t for t in rp if t["categoria"].lower() not in validas]
    rp_cat.append({"cat": SIN_CATEGORIA, "n": len(sin_cat), "importe": rp_tot - sum(x["importe"] for x in rp_cat)})

    inus = [t for t in reg if t["inusual"] == "Sí"]
    for t in inus:
        t["revelarSep"] = None if mat is None else ("Sí" if t["importe"] >= mat else "No")
    for t in reg:
        t["supera"] = "Sí" if t["importe"] > uban else "No"
        t["ndComp"] = t["importe"] if t["comprobante_valido"] == "No" else 0
        t["ndBanco"] = t["importe"] if t["supera"] == "Sí" and t["bancarizado"] == "No" and t["comprobante_valido"] != "No" else 0
        t["noSoportado"] = t["importe"] if t["soporte"] == "No" else 0

    # Presentación por línea del estado de resultados (agrupa sin distinguir mayúsculas, como SUMIF).
    grupos = {}
    for c in cuentas:
        g = grupos.setdefault(c["clas"].lower(), {"clas": c["clas"], "n": 0, "actual": 0.0, "anterior": 0.0})
        g["n"] += 1
        g["actual"] += c["actual"]
        g["anterior"] += c["anterior"] or 0
    total = sum(c["actual"] for c in cuentas)
    eri_l = []
    for g in grupos.values():
        eri_l.append({**g, "var": g["actual"] - g["anterior"], "part": g["actual"] / total if total else None,
                      "extra": "Sí" if "extraordinari" in g["clas"].lower() else "No"})

    no_reg = sum(t["noRegistrado"] for t in corte_l)
    otro = sum(t["otroPeriodo"] for t in corte_l)
    antic = sum(t["anticipado"] for t in dev_l)
    dev_nr = sum(t["devNoReg"] for t in dev_l)
    ajuste = no_reg + dev_nr - otro - antic
    no_sop = sum(t["noSoportado"] for t in reg)
    rec_tot = sum(t["importe"] for t in reclas)
    no_ded = sum(t["ndComp"] + t["ndBanco"] for t in reg)
    inus_tot = sum(t["importe"] for t in inus)
    dif_conc = None if eri is None else total - eri
    rp_nr = max(rp_tot - (rp_rev or 0), 0)   # identificadas en la muestra y no cubiertas por la nota

    # --- problemas ---
    ns = lambda n: f"{n} " + ("cuenta" if n == 1 else "cuentas")
    problemas = []
    for c in cuentas:
        if c["sinExplicar"] == "Sí":
            v = c["var"] if c["excede"] == "Sí" else c["varPpto"]
            problemas.append(problema("VARIACION_SIN_EXPLICAR", f"{c['cuenta']} {c['nombre']}: variación sobre el umbral sin explicación "
                                      f"({m(v)}). Obtenga y corrobore la explicación (NIA 520 párr. 7).", v))
    for c in cuentas:
        if c["extra"] == "Sí":
            problemas.append(problema("PARTIDA_EXTRAORDINARIA", f"{c['cuenta']} {c['nombre']} ({c['clas']}): presentada como «extraordinaria»; "
                                      + ("prohibido por la Sección 5.10." if pymes else "prohibido por la NIC 1 párr. 87.")
                                      + " Presente la partida por su naturaleza o función y, si es material, revélela por separado.", c["actual"]))
    if metodo == "Función":
        if not pymes:
            sin_nat = [c for c in cuentas if not c["naturaleza"]]
            if sin_nat:
                problemas.append(problema("NATURALEZA_NO_REVELADA", f"{ns(len(sin_nat))} sin naturaleza del gasto: "
                                          + ", ".join(c["cuenta"] for c in sin_nat) + ". Con el método por función la NIC 1 párr. 104 exige "
                                          "información por naturaleza (incluidas amortización y retribuciones a los empleados).",
                                          sum(c["actual"] for c in sin_nat)))
        elif not any("costo de venta" in g["clas"].lower() or "coste de venta" in g["clas"].lower() for g in eri_l):
            problemas.append(problema("COSTO_VENTAS_NO_SEPARADO", "Método por función sin línea de costo de ventas: la Sección 5.11 b) exige "
                                      "revelar el costo de ventas por separado de otros gastos."))
    if eri is None:
        problemas.append(problema("SIN_CONCILIACION", "Ingrese el total de gastos según el estado de resultados o el mayor para conciliar la sumaria (NIA 500)."))
    elif abs(dif_conc) > 0.005:
        problemas.append(problema("DIF_CONCILIACION", f"La sumaria ({m(total)}) no concilia con el estado de resultados ({m(eri)}): diferencia {m(dif_conc)}.", dif_conc))
    for c in cuentas:
        if c["actual"] < 0:
            problemas.append(problema("SALDO_ACREEDOR", f"{c['cuenta']} {c['nombre']}: cuenta de gasto con saldo acreedor; revise su naturaleza.", c["actual"]))
    if not trans:
        problemas.append(problema("SIN_MUESTRA", "No se cargó la muestra de transacciones: verificación del soporte, corte y devengo no se ejecutaron (NIA 500, NIA 330)."))
    for t in reg:
        if t["noSoportado"]:
            problemas.append(problema("GASTO_NO_SOPORTADO", f"{t['comp']} {t['proveedor']}: gasto registrado sin soporte (NIA 500).", t["importe"]))
    sd = [t for t in reg if t["soporte"] is None]
    if sd:
        problemas.append(problema("DATO_VOUCHING_FALTANTE", f"{len(sd)} transacción(es) sin resultado de la verificación del soporte: " + ", ".join(t["comp"] for t in sd)
                                  + ". Complete la columna «Tiene soporte».", sum(t["importe"] for t in sd)))
    for t in corte_l:
        if t["otroPeriodo"]:
            problemas.append(problema("CORTE_OTRO_PERIODO", f"{t['comp']} {t['proveedor']}: documento posterior al corte registrado en el ejercicio "
                                      "(gasto de otro período; NIC 1 párr. 27–28).", t["importe"]))
        if t["noRegistrado"]:
            problemas.append(problema("CORTE_NO_REGISTRADO", f"{t['comp']} {t['proveedor']}: documento del ejercicio registrado después del corte "
                                      "(gasto y pasivo no registrados).", t["importe"]))
    for t in dev_l:
        if t["anticipado"] > 0.005:
            problemas.append(problema("GASTO_ANTICIPADO_EN_RESULTADOS", f"{t['comp']} {t['proveedor']}: {t['diasPost']} de {t['dias']} días del servicio son "
                                      f"posteriores al corte; {m(t['anticipado'])} es gasto pagado por anticipado, no gasto del período "
                                      + ("(PYMES 2.36)." if pymes else "(NIC 1 párr. 27–28)."), t["anticipado"]))
        if t["devNoReg"] > 0.005:
            problemas.append(problema("DEVENGADO_NO_REGISTRADO", f"{t['comp']} {t['proveedor']}: servicio del período ({t['diasPeriodo']} de {t['dias']} días) "
                                      f"registrado después del corte; {m(t['devNoReg'])} de gasto por devengar no registrado.", t["devNoReg"]))
    for t in reclas:
        problemas.append(problema("CLASIFICACION_INCORRECTA", f"{t['comp']} {t['proveedor']}: registrado en {t['cuenta']} ({t['clasReg']}); corresponde a "
                                  f"{t['sugerida']} ({t['clasSug']}).", t["importe"]))
    if rp:
        if rp_rev is None:
            problemas.append(problema("SIN_RP_REVELADO", f"Transacciones con partes relacionadas en la muestra por {m(rp_tot)}: ingrese el importe revelado en notas "
                                      + ("(Sección 33.9)." if pymes else "(NIC 24 párr. 18)."), rp_tot))
        elif rp_nr > 0.005:
            problemas.append(problema("RP_NO_REVELADAS", f"Transacciones con partes relacionadas {m(rp_tot)} frente a {m(rp_rev)} reveladas: {m(rp_nr)} sin revelar "
                                      + ("(Sección 33.9–33.10)." if pymes else "(NIC 24 párr. 18–19)."), rp_nr))
        if sin_cat:
            problemas.append(problema("RP_SIN_CATEGORIA", f"{len(sin_cat)} transacción(es) con partes relacionadas sin categoría válida para "
                                      f"{'PYMES (33.10)' if pymes else 'NIIF completas (NIC 24 párr. 19)'}: " + ", ".join(t["comp"] for t in sin_cat)
                                      + ". Use: " + "; ".join(cats) + ".", rp_cat[-1]["importe"]))
    for t in inus:
        det = ("iguala o supera la materialidad: revele su naturaleza e importe por separado (NIC 1 párr. 97" + ("; PYMES 5.9" if pymes else "") + "; se usa la materialidad de ejecución como aproximación (NIC 1.97 se refiere a la importancia relativa))"
               if t["revelarSep"] == "Sí" else "evalúe su naturaleza y si requiere revelación separada"
               + (" (materialidad no informada)" if mat is None else ""))
        problemas.append(problema("PARTIDA_INUSUAL", f"{t['comp']} {t['proveedor']}: partida inusual; {det}.", t["importe"]))
    for t in reg:
        if t["ndComp"]:
            problemas.append(problema("SIN_COMPROBANTE_VALIDO", f"{t['comp']} {t['proveedor']}: sin comprobante de venta válido; no deducible "
                                      "(LRTI art. 10 num. 1; VERIFICAR norma vigente).", t["importe"]))
        if t["ndBanco"]:
            problemas.append(problema("SIN_BANCARIZACION", f"{t['comp']} {t['proveedor']}: pago mayor a {m(uban)} sin bancarización; no deducible "
                                      "(Reglamento LRTI art. 27, por caso entendido; umbral vigente al corte, VERIFICAR).", t["importe"]))
    fuera = sorted({t["cuenta"] for t in trans if t["cuenta"].lower() not in idx_cta})
    if fuera:
        problemas.append(problema("CUENTA_FUERA_DE_SUMARIA", "Cuentas de la muestra que no están en la sumaria: " + ", ".join(fuera) + "."))

    iso = lambda d: d.isoformat() if d else None
    rows = [{"id": c["cuenta"], "nombre": c["nombre"], "clasificacion": c["clas"], "saldoActual": r2(c["actual"]),
             "saldoAnterior": "" if c["anterior"] is None else r2(c["anterior"]), "variacion": "" if c["var"] is None else r2(c["var"]),
             "variacionPct": "" if c["pct"] is None else f"{c['pct']:.6f}", "excedeUmbral": c["excede"] or "", "_row": c["_row"]} for c in cuentas]
    totales = {"gastoTotal": total, "gastoAnterior": sum(c["anterior"] or 0 for c in cuentas), "noRegistradoCorte": no_reg,
               "devengadoNoRegistrado": dev_nr, "otroPeriodo": otro, "anticipado": antic, "ajusteGasto": ajuste, "noSoportado": no_sop,
               "reclasificaciones": rec_tot, "partesRelacionadas": rp_tot, "rpNoReveladas": rp_nr, "inusuales": inus_tot, "noDeducible": no_ded}
    etiquetas = {"gastoTotal": "Gastos según la sumaria (año actual)", "gastoAnterior": "Gastos año anterior",
                 "noRegistradoCorte": "Gastos del ejercicio no registrados (corte)", "devengadoNoRegistrado": "Gastos devengados no registrados",
                 "otroPeriodo": "Gastos de otro período registrados (corte)", "anticipado": "Gastos anticipados llevados a resultados",
                 "ajusteGasto": "Ajuste propuesto al gasto (neto)", "noSoportado": "Gastos no soportados",
                 "reclasificaciones": "Reclasificaciones entre cuentas", "partesRelacionadas": "Transacciones con partes relacionadas",
                 "rpNoReveladas": "Partes relacionadas no reveladas", "inusuales": "Partidas inusuales",
                 "noDeducible": "No deducible (referencia tributaria)"}
    if dif_conc is not None:
        totales["difConciliacion"] = dif_conc
        etiquetas["difConciliacion"] = "Diferencia sumaria vs estado de resultados"
    detalle = {"cortes": {"actual": corte_a.isoformat()}, "parametros": p, "pymes": pymes, "edicion": edicion_pymes(p) if pymes else "",
               "metodo": metodo, "upct": upct, "uabsIn": uabs_in, "mat": mat, "uabs": uabs, "uban": uban, "eri": eri, "rpRev": rp_rev,
               "cuentas": cuentas, "eri_l": eri_l, "rpCat": rp_cat, "categorias": cats,
               "trans": [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in t.items()} for t in trans]}
    return {"engine": VERSION, "rows": rows, "totals": {k: r2(v) for k, v in totales.items()}, "labels": etiquetas,
            "primary": "ajusteGasto", "exceptions": problemas, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

P = ref("02_Parametros")
CTA, TRX, VOU, COR, DEV, REC, RPS, INU, TRI, AJ = (ref(n) for n in (
    "03_Analisis_global", "05_Transacciones", "06_Vouching", "07_Corte", "08_Devengo", "09_Reclasificaciones",
    "10_Partes_relacionadas", "11_Inusuales", "12_Tributario", "13_Ajustes"))
_PAR = ["corte", "marco", "metodoEri", "requisito", "umbralVarPct", "umbralVarAbs", "materialidadEjecucion", "umbralAbs",
        "umbralBancarizacion", "gastosSegunEri", "rpRevelado"]
PAR = {k: FILA0 + i for i, k in enumerate(_PAR)}
_AJ = ["noReg", "devNoReg", "otro", "antic", "ajuste", "noSop", "reclas", "rp", "rpRev", "rpNr", "sumaria", "eri", "difConc", "noDed", "inus"]
AJF = {k: FILA0 + i for i, k in enumerate(_AJ)}


def _pb(k):
    return f"{P}$B${PAR[k]}"


def _rng(hoja_ref: str, col: str, n: int) -> str:
    return f"{hoja_ref}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    cs, tr, el = d["cuentas"], d["trans"], d["eri_l"]
    t = {k: float(v) for k, v in res["totals"].items()}
    nc, nt = len(cs), len(tr)
    corte = _pb("corte")
    ua, up = _pb("umbralAbs"), _pb("umbralVarPct")
    rt = lambda x: FILA0 + x["i"]            # fila de la transacción en 05_Transacciones
    tot_ref = lambda hoja_ref, col, n: f"{hoja_ref}{col}{FILA0 + n}" if n else "0"
    marco = (MARCO_PYMES + f" {d['edicion']}") if d["pymes"] else MARCO_COMPLETAS
    if d["metodo"] == "Función":
        requisito = ("Revelar el costo de ventas por separado (PYMES 5.11 b)" if d["pymes"]
                     else "Revelar información por naturaleza: amortización y retribuciones a los empleados (NIC 1 párr. 104)")
    else:
        requisito = "Desglose por naturaleza (" + ("PYMES 5.11 a)" if d["pymes"] else "NIC 1 párr. 102") + ")"

    parametros = [
        ["Corte del ejercicio", d["cortes"]["actual"], "Ficha del encargo"],
        ["Marco contable", marco, "Ficha del encargo: enruta el requisito de desglose y las categorías de partes relacionadas"],
        ["Método de desglose del estado de resultados", d["metodo"], "NIC 1 párr. 99 / PYMES 5.11"],
        ["Requisito de desglose que aplica", requisito, "Enrutado por marco y método"],
        ["Umbral de variación (%)", d["upct"], "NIA 520 párr. 5 d) y 7 — juicio del auditor"],
        ["Umbral de variación (importe)", d["uabsIn"], "NIA 520 — vacío: se usa la materialidad de ejecución"],
        ["Materialidad de ejecución", d["mat"], "NIA 320; revelación separada de partidas materiales: se usa la materialidad de ejecución como aproximación (NIC 1.97 se refiere a la importancia relativa)"],
        ["Umbral absoluto aplicado", fx(f'IF(B{PAR["umbralVarAbs"]}<>"",B{PAR["umbralVarAbs"]},B{PAR["materialidadEjecucion"]})', d["uabs"]),
         "Umbral de variación o, si falta, materialidad de ejecución"],
        ["Umbral de bancarización (USD)", d["uban"], "Por caso entendido (contrato), Reglamento LRTI art. 27 — vigente al corte; VERIFICAR"],
        ["Gastos según el estado de resultados / mayor", d["eri"], "Estado de resultados o balance de comprobación"],
        ["Partes relacionadas reveladas en notas", d["rpRev"], "Nota de partes relacionadas (NIC 24 párr. 18 / PYMES 33.9)"],
    ]

    # 03 · Análisis global.
    analisis = []
    for i, c in enumerate(cs):
        r = FILA0 + i
        exc = lambda v, b, pc: f'IF({v}="","",IF(ABS({v})<={ua},"No",IF({b}=0,"Sí",IF(ABS({pc})>{up}/100,"Sí","No"))))'
        analisis.append([
            c["cuenta"], c["nombre"], c["clas"], c["naturaleza"], n2(c["actual"]), c["anterior"],
            fx(f'IF(F{r}="","",E{r}-F{r})', c["var"]), fx(f'IF(F{r}="","",IF(F{r}=0,"",G{r}/F{r}))', c["pct"]),
            fx(exc(f"G{r}", f"F{r}", f"H{r}"), c["excede"]), c["ppto"],
            fx(f'IF(J{r}="","",E{r}-J{r})', c["varPpto"]), fx(f'IF(J{r}="","",IF(J{r}=0,"",K{r}/J{r}))', c["pctPpto"]),
            fx(exc(f"K{r}", f"J{r}", f"L{r}"), c["excedePpto"]), c["explicacion"],
            fx(f'IF(AND(OR(I{r}="Sí",M{r}="Sí"),N{r}=""),"Sí","No")', c["sinExplicar"]),
            fx(f'SUMIFS({_rng(TRX, "F", nt)},{_rng(TRX, "G", nt)},A{r},{_rng(TRX, "P", nt)},"Sí")' if nt else "0", n2(c["muestra"])),
            fx(f'IF(E{r}=0,"",P{r}/E{r})', c["cobertura"]),
            fx(f'IF(OR(ISNUMBER(SEARCH("extraordinari",B{r})),ISNUMBER(SEARCH("extraordinari",C{r}))),"Sí","No")', c["extra"]),
        ])
    fin_c = FILA0 + nc - 1
    tot_an = ["TOTAL", "", "", "", suma("E", fin_c, t["gastoTotal"]), suma("F", fin_c, t["gastoAnterior"]),
              suma("G", fin_c, sum(c["var"] or 0 for c in cs)), None, "", suma("J", fin_c, sum(c["ppto"] or 0 for c in cs)),
              suma("K", fin_c, sum(c["varPpto"] or 0 for c in cs)), None, "", "", "", suma("P", fin_c, sum(c["muestra"] for c in cs)),
              fx(f'IF(E{fin_c + 1}=0,"",P{fin_c + 1}/E{fin_c + 1})', sum(c["muestra"] for c in cs) / t["gastoTotal"] if t["gastoTotal"] else None), ""]

    # 04 · Presentación por línea del estado de resultados.
    pres = []
    for i, g in enumerate(el):
        r = FILA0 + i
        pres.append([g["clas"], fx(f"COUNTIF({_rng(CTA, 'C', nc)},A{r})", g["n"]),
                     fx(f"SUMIF({_rng(CTA, 'C', nc)},A{r},{_rng(CTA, 'E', nc)})", g["actual"]),
                     fx(f"SUMIF({_rng(CTA, 'C', nc)},A{r},{_rng(CTA, 'F', nc)})", g["anterior"]),
                     fx(f"C{r}-D{r}", g["var"]), fx(f"IF(SUM({_rng(CTA, 'E', nc)})=0,\"\",C{r}/SUM({_rng(CTA, 'E', nc)}))", g["part"]),
                     fx(f'IF(ISNUMBER(SEARCH("extraordinari",A{r})),"Sí","No")', g["extra"])])
    fin_e = FILA0 + len(el) - 1
    tot_pres = ["TOTAL", suma("B", fin_e, nc), suma("C", fin_e, t["gastoTotal"]), suma("D", fin_e, t["gastoAnterior"]),
                suma("E", fin_e, t["gastoTotal"] - t["gastoAnterior"]), None, ""]

    # 05 · Transacciones (datos de la muestra).
    trans = []
    for x in tr:
        r = rt(x)
        trans.append([x["comp"], x["fdoc"], x["freg"], x["desde"], x["hasta"], n2(x["importe"]), x["cuenta"], x["proveedor"],
                      x["soporte"], x["comprobante_valido"], x["bancarizado"], x["parte_relacionada"], x["categoria"] or None,
                      x["sugerida"] or None, x["inusual"],
                      fx(f'IF(C{r}<={corte},"Sí","No")', x["enPeriodo"]), fx(f'IF(AND(D{r}<>"",E{r}<>""),"Sí","No")', x["conServicio"])])
    fin_t = FILA0 + nt - 1
    tot_tr = ["TOTAL", "", "", "", "", suma("F", fin_t, sum(x["importe"] for x in tr))] + [""] * 11 if tr else None

    reg = [x for x in tr if x["enPeriodo"] == "Sí"]
    imp = lambda x: fx(f"{TRX}F{rt(x)}", n2(x["importe"]))

    # 06 · Vouching (registradas en el ejercicio).
    vou = []
    for j, x in enumerate(reg):
        r = FILA0 + j
        vou.append([x["comp"], x["fdoc"], x["cuenta"], x["proveedor"], imp(x), x["soporte"],
                    fx(f'IF(F{r}="No",E{r},0)', n2(x["noSoportado"])),
                    fx(f'IF(F{r}="Sí","Soportado",IF(F{r}="No","No soportado","Sin resultado informado"))',
                       {"Sí": "Soportado", "No": "No soportado"}.get(x["soporte"], "Sin resultado informado"))])
    fin_v = FILA0 + len(reg) - 1
    tot_vou = ["TOTAL", "", "", "", suma("E", fin_v, sum(x["importe"] for x in reg)), "", suma("G", fin_v, t["noSoportado"]), ""] if reg else None

    # 07 · Corte (sin período de servicio).
    cl = [x for x in tr if x["conServicio"] == "No"]
    cor = []
    for j, x in enumerate(cl):
        r = FILA0 + j
        cor.append([x["comp"], x["proveedor"], x["cuenta"], x["fdoc"], x["freg"], imp(x),
                    fx(f'IF(D{r}<={corte},"Sí","No")', x["docEnPeriodo"]), fx(f'IF(E{r}<={corte},"Sí","No")', x["enPeriodo"]),
                    fx(f'IF(AND(G{r}="No",H{r}="Sí"),F{r},0)', n2(x["otroPeriodo"])),
                    fx(f'IF(AND(G{r}="Sí",H{r}="No"),F{r},0)', n2(x["noRegistrado"]))])
    fin_co = FILA0 + len(cl) - 1
    tot_cor = ["TOTAL", "", "", "", "", suma("F", fin_co, sum(x["importe"] for x in cl)), "", "",
               suma("I", fin_co, t["otroPeriodo"]), suma("J", fin_co, t["noRegistradoCorte"])] if cl else None

    # 08 · Devengo (con período de servicio).
    dl = [x for x in tr if x["conServicio"] == "Sí"]
    dev = []
    for j, x in enumerate(dl):
        r = FILA0 + j
        dev.append([x["comp"], x["proveedor"], x["cuenta"], x["freg"], x["desde"], x["hasta"], imp(x),
                    fx(f"F{r}-E{r}+1", x["dias"]), fx(f"MAX(0,MIN(F{r},{corte})-E{r}+1)", x["diasPeriodo"]), fx(f"H{r}-I{r}", x["diasPost"]),
                    fx(f"G{r}*I{r}/H{r}", x["gastoPeriodo"]), fx(f'IF(D{r}<={corte},"Sí","No")', x["enPeriodo"]),
                    fx(f'IF(L{r}="Sí",G{r}*J{r}/H{r},0)', x["anticipado"]), fx(f'IF(L{r}="No",K{r},0)', x["devNoReg"])])
    fin_d = FILA0 + len(dl) - 1
    tot_dev = ["TOTAL", "", "", "", "", "", suma("G", fin_d, sum(x["importe"] for x in dl)), None, None, None,
               suma("K", fin_d, sum(x["gastoPeriodo"] for x in dl)), "", suma("M", fin_d, t["anticipado"]),
               suma("N", fin_d, t["devengadoNoRegistrado"])] if dl else None

    # 09 · Reclasificaciones.
    rl = [x for x in reg if x["sugerida"] and x["sugerida"].lower() != x["cuenta"].lower()]
    look = lambda c: f'IFERROR(INDEX({_rng(CTA, "C", nc)},MATCH({c},{_rng(CTA, "A", nc)},0)),"(no en la sumaria)")'
    rec = []
    for j, x in enumerate(rl):
        r = FILA0 + j
        rec.append([x["comp"], x["proveedor"], x["cuenta"], x["sugerida"], imp(x), fx(look(f"C{r}"), x["clasReg"]), fx(look(f"D{r}"), x["clasSug"]),
                    fx(f'IF(F{r}<>G{r},"Sí","No")', "Sí" if x["clasReg"].lower() != x["clasSug"].lower() else "No")])
    fin_r = FILA0 + len(rl) - 1
    tot_rec = ["TOTAL", "", "", "", suma("E", fin_r, t["reclasificaciones"]), "", "", ""] if rl else None

    # 10 · Partes relacionadas por categoría (del período).
    rps = []
    crit = f'{_rng(TRX, "L", nt)},"Sí",{_rng(TRX, "P", nt)},"Sí"'
    nrp = len(d["rpCat"])
    for j, x in enumerate(d["rpCat"]):
        r = FILA0 + j
        if x["cat"] == SIN_CATEGORIA:
            prev = f"SUM(C{FILA0}:C{r - 1})" if j else "0"
            fn = f"COUNTIFS({crit})-SUM(B{FILA0}:B{r - 1})" if j else f"COUNTIFS({crit})"
            rps.append([x["cat"], fx(fn if nt else "0", x["n"]), fx(f"SUMIFS({_rng(TRX, 'F', nt)},{crit})-{prev}" if nt else "0", n2(x["importe"])),
                        "Categoría vacía o no prevista para el marco"])
        else:
            rps.append([x["cat"], fx(f"COUNTIFS({crit},{_rng(TRX, 'M', nt)},A{r})" if nt else "0", x["n"]),
                        fx(f"SUMIFS({_rng(TRX, 'F', nt)},{crit},{_rng(TRX, 'M', nt)},A{r})" if nt else "0", n2(x["importe"])),
                        "PYMES 33.10" if d["pymes"] else "NIC 24 párr. 19"])
    fin_rp = FILA0 + nrp - 1
    tot_rp = ["TOTAL", suma("B", fin_rp, sum(x["n"] for x in d["rpCat"])), suma("C", fin_rp, t["partesRelacionadas"]), ""]

    # 11 · Partidas inusuales.
    il = [x for x in reg if x["inusual"] == "Sí"]
    inu = []
    for j, x in enumerate(il):
        r = FILA0 + j
        mt = _pb("materialidadEjecucion")
        inu.append([x["comp"], x["fdoc"], x["cuenta"], x["proveedor"], imp(x),
                    fx(f'IF({mt}="","",IF(E{r}>={mt},"Sí","No"))', x["revelarSep"])])
    fin_i = FILA0 + len(il) - 1
    tot_inu = ["TOTAL", "", "", "", suma("E", fin_i, t["inusuales"]), ""] if il else None

    # 12 · Referencia tributaria.
    tri = []
    for j, x in enumerate(reg):
        r = FILA0 + j
        tri.append([x["comp"], x["proveedor"], imp(x), x["comprobante_valido"], x["bancarizado"],
                    fx(f'IF(C{r}>{_pb("umbralBancarizacion")},"Sí","No")', x["supera"]),
                    fx(f'IF(D{r}="No",C{r},0)', n2(x["ndComp"])), fx(f'IF(AND(F{r}="Sí",E{r}="No",D{r}<>"No"),C{r},0)', n2(x["ndBanco"])),
                    fx(f"G{r}+H{r}", n2(x["ndComp"] + x["ndBanco"]))])
    tot_tri = ["TOTAL", "", suma("C", fin_v, sum(x["importe"] for x in reg)), "", "", "", suma("G", fin_v, sum(x["ndComp"] for x in reg)),
               suma("H", fin_v, sum(x["ndBanco"] for x in reg)), suma("I", fin_v, t["noDeducible"])] if reg else None

    # 13 · Ajustes y conciliación.
    eri_v = d["eri"]
    ajustes = [
        ["Gastos del ejercicio no registrados (corte)", fx(tot_ref(COR, "J", len(cl)), t["noRegistradoCorte"]), "07_Corte"],
        ["Gastos devengados no registrados", fx(tot_ref(DEV, "N", len(dl)), t["devengadoNoRegistrado"]), "08_Devengo"],
        ["Gastos de otro período registrados (corte)", fx(tot_ref(COR, "I", len(cl)), t["otroPeriodo"]), "07_Corte"],
        ["Gastos anticipados llevados a resultados", fx(tot_ref(DEV, "M", len(dl)), t["anticipado"]), "08_Devengo"],
        ["Ajuste propuesto al gasto (neto)", fx(f"B{AJF['noReg']}+B{AJF['devNoReg']}-B{AJF['otro']}-B{AJF['antic']}", t["ajusteGasto"]),
         "Positivo: falta gasto; negativo: exceso de gasto"],
        ["Gastos no soportados", fx(tot_ref(VOU, "G", len(reg)), t["noSoportado"]), "06_Vouching — posible incorrección (NIA 450)"],
        ["Reclasificaciones entre cuentas", fx(tot_ref(REC, "E", len(rl)), t["reclasificaciones"]), "09_Reclasificaciones"],
        ["Transacciones con partes relacionadas", fx(f"{RPS}C{fin_rp + 1}", t["partesRelacionadas"]), "10_Partes_relacionadas"],
        ["Partes relacionadas reveladas en notas", fx(_pb("rpRevelado"), d["rpRev"] or 0), "Parámetros"],
        ["Partes relacionadas no reveladas", fx(f"MAX(B{AJF['rp']}-B{AJF['rpRev']},0)", t["rpNoReveladas"]), "NIC 24 párr. 18 / PYMES 33.9"],
        ["Gastos según la sumaria", fx(f"SUM({_rng(CTA, 'E', nc)})", t["gastoTotal"]), "03_Analisis_global"],
        ["Gastos según el estado de resultados / mayor", fx(f'IF({_pb("gastosSegunEri")}="","",{_pb("gastosSegunEri")})', eri_v), "Parámetros"],
        ["Diferencia sumaria vs estado de resultados", fx(f'IF(B{AJF["eri"]}="","",B{AJF["sumaria"]}-B{AJF["eri"]})', t.get("difConciliacion")), "Conciliación (NIA 500)"],
        ["No deducible (referencia tributaria)", fx(tot_ref(TRI, "I", len(reg)), t["noDeducible"]), "12_Tributario"],
        ["Partidas inusuales", fx(tot_ref(INU, "E", len(il)), t["inusuales"]), "11_Inusuales"],
    ]

    # 14 · Asientos.
    asientos = []

    def asiento(titulo, lineas):
        for i, (cta, formula, valor, debe) in enumerate(lineas):
            v = fx(formula, n2(valor))
            asientos.append([titulo if i == 0 else "", cta, v if debe else None, None if debe else v])

    ajb = lambda k: f"{AJ}B{AJF[k]}"
    falt = t["noRegistradoCorte"] + t["devengadoNoRegistrado"]
    if falt > 0.005:
        asiento("1 · Gastos del período no registrados", [("Gasto (cuentas de la muestra)", f"{ajb('noReg')}+{ajb('devNoReg')}", falt, True),
                                                           ("Gastos acumulados por pagar (pasivo)", f"{ajb('noReg')}+{ajb('devNoReg')}", falt, False)])
    if t["anticipado"] > 0.005:
        asiento("2 · Gastos pagados por anticipado", [("Gastos pagados por anticipado (activo)", ajb("antic"), t["anticipado"], True),
                                                      ("Gasto (cuentas de la muestra)", ajb("antic"), t["anticipado"], False)])
    if t["otroPeriodo"] > 0.005:
        asiento("3 · Gastos de otro período", [("Cuentas por pagar / anticipos (según el caso)", ajb("otro"), t["otroPeriodo"], True),
                                               ("Gasto (cuentas de la muestra)", ajb("otro"), t["otroPeriodo"], False)])
    for j, x in enumerate(rl):
        asiento(f"{4 + j} · Reclasificación {x['comp']}", [(f"{x['sugerida']} ({x['clasSug']})", f"{REC}E{FILA0 + j}", x["importe"], True),
                                                          (f"{x['cuenta']} ({x['clasReg']})", f"{REC}E{FILA0 + j}", x["importe"], False)])

    ref_res = {"gastoTotal": ajb("sumaria"), "gastoAnterior": f"SUM({_rng(CTA, 'F', nc)})", "noRegistradoCorte": ajb("noReg"),
               "devengadoNoRegistrado": ajb("devNoReg"), "otroPeriodo": ajb("otro"), "anticipado": ajb("antic"), "ajusteGasto": ajb("ajuste"),
               "noSoportado": ajb("noSop"), "reclasificaciones": ajb("reclas"), "partesRelacionadas": ajb("rp"), "rpNoReveladas": ajb("rpNr"),
               "inusuales": ajb("inus"), "noDeducible": ajb("noDed"), "difConciliacion": ajb("difConc")}
    resumen = [[res["labels"][k], fx(ref_res[k], t[k])] for k in res["labels"]]

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Analisis_global", "Análisis global por cuenta (NIA 520)",
             [["Cuenta", "t"], ["Nombre", "t"], ["Línea del estado de resultados", "t"], ["Naturaleza", "t"], ["Saldo actual", "n"],
              ["Saldo anterior", "n"], ["Variación", "n"], ["Variación %", "p"], ["Excede umbral", "t"], ["Presupuesto", "n"],
              ["Variación vs presupuesto", "n"], ["Variación vs presupuesto %", "p"], ["Excede umbral (presupuesto)", "t"],
              ["Explicación", "t"], ["Variación sin explicar", "t"], ["Muestra examinada", "n"], ["Cobertura de la muestra", "p"],
              ["Presentada como extraordinaria", "t"]], analisis, tot_an),
        hoja("04_Presentacion_ERI", "Presentación en el estado de resultados",
             [["Línea del estado de resultados", "t"], ["Cuentas", "i"], ["Año actual", "n"], ["Año anterior", "n"], ["Variación", "n"],
              ["% del gasto total", "p"], ["«Extraordinaria» (prohibido)", "t"]], pres, tot_pres),
        hoja("05_Transacciones", "Transacciones de la muestra",
             [["Comprobante", "t"], ["Fecha documento", "d"], ["Fecha registro", "d"], ["Servicio desde", "d"], ["Servicio hasta", "d"],
              ["Importe", "n"], ["Cuenta", "t"], ["Proveedor", "t"], ["Soporte", "t"], ["Comprobante válido SRI", "t"],
              ["Pagado por banco", "t"], ["Parte relacionada", "t"], ["Categoría parte relacionada", "t"], ["Cuenta sugerida", "t"],
              ["Inusual", "t"], ["Registrado en el ejercicio", "t"], ["Con período de servicio", "t"]], trans, tot_tr),
        hoja("06_Vouching", "Verificación del soporte documental",
             [["Comprobante", "t"], ["Fecha documento", "d"], ["Cuenta", "t"], ["Proveedor", "t"], ["Importe", "n"], ["Tiene soporte", "t"],
              ["Gasto no soportado", "n"], ["Resultado", "t"]], vou, tot_vou),
        hoja("07_Corte", "Corte de gastos",
             [["Comprobante", "t"], ["Proveedor", "t"], ["Cuenta", "t"], ["Fecha documento", "d"], ["Fecha registro", "d"], ["Importe", "n"],
              ["Documento del ejercicio", "t"], ["Registrado en el ejercicio", "t"], ["Gasto de otro período registrado", "n"],
              ["Gasto del ejercicio no registrado", "n"]], cor, tot_cor),
        hoja("08_Devengo", "Devengo y gastos anticipados",
             [["Comprobante", "t"], ["Proveedor", "t"], ["Cuenta", "t"], ["Fecha registro", "d"], ["Servicio desde", "d"], ["Servicio hasta", "d"],
              ["Importe", "n"], ["Días del servicio", "i"], ["Días hasta el corte", "i"], ["Días posteriores", "i"], ["Gasto del período", "n"],
              ["Registrado en el ejercicio", "t"], ["Anticipado llevado a resultados", "n"], ["Devengado no registrado", "n"]], dev, tot_dev),
        hoja("09_Reclasificaciones", "Reclasificaciones",
             [["Comprobante", "t"], ["Proveedor", "t"], ["Cuenta registrada", "t"], ["Cuenta correcta", "t"], ["Importe", "n"],
              ["Línea registrada", "t"], ["Línea correcta", "t"], ["Cambia la línea del estado de resultados", "t"]], rec, tot_rec),
        hoja("10_Partes_relacionadas", "Partes relacionadas",
             [["Categoría", "t"], ["Transacciones", "i"], ["Importe del período", "n"], ["Referencia", "t"]], rps, tot_rp),
        hoja("11_Inusuales", "Partidas inusuales",
             [["Comprobante", "t"], ["Fecha documento", "d"], ["Cuenta", "t"], ["Proveedor", "t"], ["Importe", "n"],
              ["Revelar por separado (≥ materialidad)", "t"]], inu, tot_inu),
        hoja("12_Tributario", "Referencia tributaria (Ecuador)",
             [["Comprobante", "t"], ["Proveedor", "t"], ["Importe", "n"], ["Comprobante válido", "t"], ["Pagado por banco", "t"],
              ["Supera el umbral de bancarización", "t"], ["No deducible: comprobante", "n"], ["No deducible: bancarización", "n"],
              ["No deducible total", "n"]], tri, tot_tri),
        hoja("13_Ajustes", "Ajustes y conciliación", [["Concepto", "t"], ["Importe", "n"], ["Referencia", "t"]], ajustes),
        hoja("14_Asientos", "Asientos propuestos", [["Asiento", "t"], ["Cuenta", "t"], ["Debe", "n"], ["Haber", "n"]], asientos),
        hoja("15_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], n2(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición -----------------------------------------------------------------

def definicion() -> dict:
    cuentas = ("Una fila por cuenta de gasto: código, nombre, línea del estado de resultados (por función o por naturaleza), saldo del año "
               "actual y, si existen, saldo del año anterior, presupuesto, naturaleza del gasto y explicación de la variación. Sin filas de total.")
    trans = ("Una fila por comprobante de la muestra (del ejercicio y posteriores al corte): comprobante, fecha del documento, fecha de registro, "
             "período del servicio (desde/hasta) si es un servicio por tiempo, importe, cuenta, proveedor y las marcas del auditor (soporte, "
             "comprobante válido SRI, pagado por banco, parte relacionada y su categoría, cuenta correcta, inusual).")
    return {
        "name": "Gastos · análisis global, verificación del soporte, corte, devengo, clasificación y partes relacionadas",
        "area": "Costos y gastos",
        "processor": "gastos_analisis",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Compara cada cuenta de gasto con el año anterior y el presupuesto frente a los umbrales de la NIA 520, prueba el soporte "
                    "de una muestra (verificación del soporte), el corte por fechas de documento y registro y el devengo por días del servicio (gastos "
                    "anticipados llevados a resultados y gastos devengados no registrados), cuantifica reclasificaciones, totaliza las "
                    "transacciones con partes relacionadas por categoría frente a lo revelado y señala partidas presentadas como "
                    "«extraordinarias» (prohibido: NIC 1 párr. 87; PYMES 5.10) e inusuales. El requisito de desglose y las categorías de "
                    "partes relacionadas se enrutan por marco (NIC 1 párr. 104 y NIC 24 párr. 19; PYMES 5.11 y 33.10). Incluye una "
                    "referencia tributaria de Ecuador (comprobante válido y bancarización)."),
        "source": {"organization": "IFRS Foundation (texto en español: Reglamento (UE) 2023/1803)", "type": "Norma contable", "date": "",
                   "document": ("NIC 1 párr. 27–28 (devengo), 87 (sin partidas extraordinarias), 97–98 (partidas materiales), 99 y 102–105 "
                                "(desglose por naturaleza o función); NIC 24 párr. 18–19; NIC 8 párr. 41–42 (errores). Marco Conceptual "
                                "párr. 4.69 y 4.72 (definición de gasto): VERIFICAR, no incluido en el Reglamento leído."),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015: párr. 2.23 b) y 2.26 (definición de gasto), 2.36 (base de acumulación o "
                                      "devengo), 5.9 (partidas adicionales), 5.10 (sin partidas extraordinarias), 5.11 (desglose por naturaleza "
                                      "o función; por función, costo de ventas por separado), 33.9–33.10 (partes relacionadas), Sección 10 "
                                      "(errores). Edición 2025 (tercera edición, vigente desde el 1-1-2027): VERIFICAR numeración y redacción en el texto oficial (no leído)."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 520", "section": "párr. 5 y 7", "requirement": "Procedimientos analíticos sustantivos: expectativa, umbral de diferencia aceptable e investigación de las diferencias (VERIFICAR párrafos)."},
            {"document": "NIA 500", "section": "párr. 6 y 9", "requirement": "Evidencia suficiente y adecuada; exactitud e integridad de la sumaria contra el mayor (VERIFICAR párrafos)."},
            {"document": "NIA 550", "section": "párr. 25", "requirement": "Transacciones con partes relacionadas: evaluación de su contabilización y revelación."},
            {"document": "NIA 330", "section": "párr. 18", "requirement": "Procedimientos sustantivos sobre transacciones materiales, incluido el corte."},
            {"document": "NIA 450", "section": "párr. 5", "requirement": "Acumular las incorrecciones identificadas (gastos no soportados, corte, devengo) (VERIFICAR párrafo)."},
        ],
        "calculo": [
            "Variación = saldo actual − saldo anterior (y − presupuesto); variación % = variación ÷ base. Excede el umbral si |variación| > umbral absoluto "
            "(o materialidad de ejecución) y, cuando la base no es cero, |variación %| > umbral %. Sin explicación → problema (NIA 520).",
            "Presentación: gasto por línea del estado de resultados; ninguna línea o cuenta puede llamarse «extraordinaria» (NIC 1 87; PYMES 5.10). "
            "Por función: NIIF completas exige naturaleza (NIC 1 104); PYMES exige costo de ventas por separado (5.11 b).",
            "Verificación del soporte: gasto registrado en el ejercicio sin soporte = gasto no soportado.",
            "Corte (comprobantes sin período de servicio): documento ≤ corte y registro > corte = gasto no registrado; documento > corte y registro ≤ corte = gasto de otro período.",
            "Devengo (con período de servicio): gasto del período = importe × días del servicio hasta el corte ÷ días del servicio. Registrado en el "
            "ejercicio → anticipado = importe × días posteriores ÷ días del servicio; registrado después → devengado no registrado = gasto del período.",
            "Ajuste propuesto al gasto = no registrados + devengados no registrados − otro período − anticipados.",
            "Reclasificación: cuenta correcta según el auditor distinta de la registrada.",
            "Partes relacionadas: importe del período por categoría (NIC 24 19 / PYMES 33.10) frente a lo revelado en notas.",
            "Partida inusual con importe ≥ materialidad: revelación por separado (NIC 1 97; se usa la materialidad de ejecución como aproximación (NIC 1.97 se refiere a la importancia relativa)).",
            "Referencia tributaria: sin comprobante válido (LRTI art. 10 num. 1), o importe > umbral de bancarización sin pago por banco (Reglamento LRTI art. 27) = no deducible (vigente al corte; VERIFICAR).",
        ],
        "fields": _CUENTAS, "rules": [], "control": CONTROL, "primary": "ajusteGasto",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            {"code": "GAS-01", "objective": "Integridad de la sumaria de gastos", "risk": "Sumaria que no concilia con el estado de resultados", "assertion": "Integridad",
             "procedure": "Conciliar la sumaria por cuenta con el estado de resultados y el mayor", "evidence": "Sumaria, balance de comprobación, mayor",
             "criterion": "Diferencia nula o explicada", "source": "NIA 500"},
            {"code": "GAS-02", "objective": "Análisis global", "risk": "Variaciones inusuales no investigadas", "assertion": "Ocurrencia / Integridad",
             "procedure": "Comparar cada cuenta con el año anterior y el presupuesto, fijar el umbral e investigar las variaciones que lo exceden",
             "evidence": "Explicaciones de la gerencia corroboradas", "criterion": "Toda variación sobre el umbral explicada", "source": "NIA 520"},
            {"code": "GAS-03", "objective": "Verificación del soporte documental", "risk": "Gastos sin sustento", "assertion": "Ocurrencia / Exactitud",
             "procedure": "Cotejar la muestra con facturas, contratos, aprobaciones y pagos", "evidence": "Comprobantes de venta y de pago",
             "criterion": "Todo gasto de la muestra soportado", "source": "NIA 500 · NIA 330"},
            {"code": "GAS-04", "objective": "Corte y devengo", "risk": "Gastos de otro período, anticipados en resultados o pasivos no registrados", "assertion": "Corte",
             "procedure": "Comparar fecha de documento, registro y período del servicio alrededor del cierre; buscar facturas posteriores con causa anterior",
             "evidence": "Facturas y pagos posteriores, contratos de servicios", "criterion": "Gasto en el período del devengo",
             "source": "NIC 1 párr. 27–28 · PYMES 2.36 · NIA 330"},
            {"code": "GAS-05", "objective": "Clasificación y presentación", "risk": "Gastos en cuentas o líneas incorrectas; partidas «extraordinarias»",
             "assertion": "Clasificación / Presentación", "procedure": "Revisar la cuenta de cada gasto de la muestra y el desglose del estado de resultados",
             "evidence": "Plan de cuentas, estado de resultados", "criterion": "Desglose conforme; sin partidas extraordinarias",
             "source": "NIC 1 párr. 87, 97–105 · PYMES 5.10–5.11"},
            {"code": "GAS-06", "objective": "Partes relacionadas", "risk": "Transacciones con partes relacionadas no reveladas", "assertion": "Presentación",
             "procedure": "Cruzar proveedores con el maestro de partes relacionadas y comparar con la nota", "evidence": "Maestro de partes relacionadas, nota",
             "criterion": "Todo lo del período revelado por categoría", "source": "NIC 24 párr. 18–19 · PYMES 33.9–33.10 · NIA 550"},
            {"code": "GAS-07", "objective": "Partidas inusuales y referencia tributaria", "risk": "Partidas materiales sin revelar; gastos no deducibles",
             "assertion": "Presentación / Cumplimiento", "procedure": "Identificar partidas inusuales y verificar comprobante válido y bancarización",
             "evidence": "Comprobantes SRI, estados de cuenta bancarios", "criterion": "Revelación separada; no deducibles identificados",
             "source": "NIC 1 párr. 97 · normativa tributaria Ecuador (VERIFICAR)"},
        ],
        "requests": [
            req("RQ-001", "Sumaria de cuentas de gasto (año actual, anterior y presupuesto)", "cuentas", "GAS-01",
                "Población a analizar y conciliar con el estado de resultados", content=cuentas),
            req("RQ-002", "Muestra de transacciones de gasto con fechas, período del servicio y marcas del auditor", "transacciones", "GAS-03",
                "Verificación del soporte, corte, devengo, clasificación, partes relacionadas", content=trans),
            req("RQ-003", "Mayor de gastos y balance de comprobación al corte", None, "GAS-01", "Conciliación de la sumaria", formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-004", "Facturas, contratos, aprobaciones y comprobantes de pago de la muestra", None, "GAS-03", "Sustento de la verificación del soporte",
                formats=("pdf",), use="soporte"),
            req("RQ-005", "Facturas y pagos posteriores al cierre", None, "GAS-04", "Búsqueda de gastos no registrados", formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-006", "Maestro de partes relacionadas y nota de revelación", None, "GAS-06", "Identificación y revelación", formats=("xlsx", "pdf", "docx"), use="soporte"),
            req("RQ-007", "Presupuesto aprobado del ejercicio", None, "GAS-02", "Base de la expectativa", formats=("xlsx", "pdf"), use="soporte", required=False),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo de control (M19) -------------------------------------------------------

def _c(id, nombre, clas, act, ant=None, ppto=None, nat="", expl=""):
    f = {"id": id, "nombre": nombre, "clasificacion": clas, "saldo_actual": act, "naturaleza": nat, "explicacion": expl, "_row": 2}
    if ant is not None:
        f["saldo_anterior"] = ant
    if ppto is not None:
        f["presupuesto"] = ppto
    return f


def _t(id, fdoc, freg, imp, cta, prov, **extra):
    base = {"soporte": "Sí", "comprobante_valido": "Sí", "bancarizado": "Sí", "parte_relacionada": "No", "inusual": "No"}
    return {"id": id, "fecha_documento": fdoc, "fecha_registro": freg, "importe": imp, "cuenta": cta, "proveedor": prov, "_row": 2, **base, **extra}


# Corte 2025-12-31; umbral 10 % y 5.000; materialidad 20.000; bancarización 500 (ningún importe de la muestra está entre 500 y 1.000).
# FC-103 seguro 7.300 del 01-07-2025 al 30-06-2026: 365 días, 184 hasta el corte → anticipado 7.300 × 181 ÷ 365 = 3.620,00.
# FC-107 pauta 12.000 del 01-11-2025 al 30-04-2026: 181 días, 61 hasta el corte → anticipado 12.000 × 120 ÷ 181 = 7.955,80.
# Ajuste = 4.500 (FC-104) + 3.000 (FC-106) − 3.000 (FC-105) − 3.620,00 − 7.955,80 = −7.075,80.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"_marco": MARCO_COMPLETAS, "metodoEri": "Función", "umbralVarPct": 10, "umbralVarAbs": 5000, "materialidadEjecucion": 20000,
                   "umbralBancarizacion": 500, "gastosSegunEri": 1005000, "rpRevelado": 10000},
    "datasets": {
        "cuentas": [
            _c("5101", "Costo de ventas", "Costo de ventas", "600000", "550000", "590000", "Consumo de inventarios", "Mayor volumen de ventas (+9 %)"),
            _c("5201", "Sueldos y beneficios administración", "Gastos de administración", "180000", "150000", "175000", "Beneficios a empleados"),
            _c("5202", "Honorarios profesionales", "Gastos de administración", "45000", "30000", "32000", "", "Asesoría legal por litigio laboral"),
            _c("5203", "Arriendos", "Gastos de administración", "36000", "36000", "36000", "Arrendamientos"),
            _c("5204", "Depreciación", "Gastos de administración", "24000", "22000", None, "Depreciación"),
            _c("5301", "Publicidad", "Gastos de ventas", "60000", "40000", "45000", "Publicidad"),
            _c("5302", "Comisiones y gastos de distribución", "Gastos de ventas", "25000", "27000", "26000", "Comisiones"),
            _c("5401", "Seguros", "Gastos de administración", "12000", "11000", None, "Seguros"),
            _c("5501", "Intereses bancarios", "Gastos financieros", "18000", "20000", None, "Intereses"),
            _c("5601", "Pérdida por siniestro", "Gastos extraordinarios", "8000", "0", None, "", "Incendio en bodega"),
        ],
        "transacciones": [
            _t("FC-101", "2025-03-10", "2025-03-12", "12000", "5202", "Estudio Jurídico Andrade"),
            _t("FC-102", "2025-06-15", "2025-06-16", "18000", "5301", "Medios Creativos S.A.", soporte="No"),
            _t("FC-103", "2025-07-01", "2025-07-02", "7300", "5401", "Aseguradora Sur", servicio_desde="2025-07-01", servicio_hasta="2026-06-30"),
            _t("FC-104", "2025-12-20", "2026-01-08", "4500", "5202", "Consultores Delta"),
            _t("FC-105", "2026-01-05", "2025-12-30", "3000", "5302", "Comisionistas Unidos"),
            _t("FC-106", "2026-01-15", "2026-01-16", "3000", "5203", "Inmobiliaria Norte", servicio_desde="2025-12-01", servicio_hasta="2025-12-31",
               parte_relacionada="Sí", categoria_rp="Otra"),
            _t("FC-107", "2025-11-01", "2025-11-03", "12000", "5301", "Radio Andina", servicio_desde="2025-11-01", servicio_hasta="2026-04-30"),
            _t("FC-108", "2025-09-10", "2025-09-12", "1500", "5202", "Juan Pérez", comprobante_valido="No", bancarizado="No"),
            _t("FC-109", "2025-10-05", "2025-10-06", "2500", "5301", "Publicistas XYZ", bancarizado="No"),
            _t("FC-110", "2025-08-20", "2025-08-21", "2200", "5201", "Taller Mecánico Ruta", cuenta_sugerida="5302"),
            _t("FC-111", "2025-05-10", "2025-05-11", "9000", "5202", "Holding Andes S.A.", parte_relacionada="Sí", categoria_rp="Dominante"),
            _t("FC-112", "2025-04-02", "2025-04-03", "8000", "5601", "Constructora Rápida", inusual="Sí"),
            _t("FC-113", "2025-11-20", "2025-11-21", "22000", "5202", "Acuerdo judicial ex trabajador", inusual="Sí"),
            _t("FC-114", "2025-02-01", "2025-02-02", "3000", "5201", "Gerente General", parte_relacionada="Sí", categoria_rp="Personal clave", soporte=""),
            _t("FC-115", "2025-06-30", "2025-07-01", "1200", "5501", "Banco Relacionado S.A.", parte_relacionada="Sí"),
        ],
    },
}

_P = EJEMPLO["parametros"]
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], _P, EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**_P, "_marco": MARCO_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025_sin_opcionales", EJEMPLO["datasets"], {**_P, "_marco": MARCO_PYMES, "_edicion": "2025", "metodoEri": "Naturaleza",
                                                        "umbralVarAbs": None, "gastosSegunEri": None, "rpRevelado": None}, EJEMPLO["corte"]),
    ("sin_muestra", {"cuentas": EJEMPLO["datasets"]["cuentas"], "transacciones": []}, _P, EJEMPLO["corte"]),
]
