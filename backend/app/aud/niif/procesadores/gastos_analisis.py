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
   «extraordinaria» (NIC 1 87; PYMES 5.10). Si el método es por función, los dos marcos exigen revelar el costo
   de ventas por separado (NIC 1 103 / PYMES 5.11 b) y NIIF completas exige además información por naturaleza (NIC 1 104).
3. Vouching (NIA 500): gasto registrado sin soporte = gasto no soportado.
4. Corte (transacciones sin período de servicio): documento del ejercicio registrado después del corte =
   gasto no registrado; documento posterior registrado en el ejercicio = gasto de otro período.
5. Devengo (transacciones con período de servicio; NIC 1 27–28; PYMES 2.36): gasto del período = importe ×
   días del servicio hasta el corte ÷ días del servicio. Registrado en el ejercicio → la porción posterior
   al corte es gasto anticipado llevado a resultados; registrado después → la porción del período es gasto
   devengado no registrado (pasivo).
6. Clasificación: cuenta sugerida por el auditor ≠ cuenta registrada = reclasificación.
7. Partes relacionadas (NIC 24 18–19; PYMES 33.9–33.10): importe del período por categoría (las categorías
   cambian por marco) frente a lo revelado en notas. El maestro completo de partes relacionadas es un
   requerimiento obligatorio. La herramienta procesa la población que reciba, pero **no concluye** sobre la
   integridad de la revelación mientras no conste la evidencia de población completa (manifestación escrita de
   la administración, NIA 550 párr. 26, o corte certificado del maestro): la conclusión queda «no concluida por
   falta de evidencia de población completa» y se pide el papel (decisión del socio).
8. Partidas inusuales: las de importe igual o mayor a la materialidad se revelan por separado (NIC 1 97; se usa la materialidad de ejecución como aproximación (NIC 1.97 se refiere a la importancia relativa)).
9. Tributario Ecuador (referencia): sin comprobante de venta válido (LRTI art. 10 num. 1) o sin bancarización sobre el
   umbral (Reglamento LRTI art. 27, reforma 2024, por caso entendido; el art. 103 de la LRTI fija el uso del sistema
   financiero) → no deducible (umbral como parámetro; confirmar que sigue vigente al corte).
10. Ajuste propuesto al gasto = no registrados + devengados no registrados − otro período − anticipados (M09).

Norma leída (M03): NIA 550 párr. 13 (preguntar a la dirección la identidad de las partes relacionadas), 25
(evaluar contabilización y revelación) y 26 (manifestaciones escritas: la dirección ha revelado la identidad de
todas las partes relacionadas y todas las transacciones de las que tiene conocimiento).
NIC 1 párr. 27–28, 87, 97–99, 102–105; NIC 24 párr. 18–19; NIC 8 párr. 41–42 en el
Reglamento (UE) 2023/1803 (EUR-Lex, español); NIIF para las PYMES 2015 párr. 2.23, 2.26, 2.36, 5.9–5.11,
33.9–33.10. Marco Conceptual 4.69 y 4.72 y la numeración de PYMES 2025 (2.63, 3.16A, 5.9–5.11) están contrastados con el texto oficial.
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores import problemas
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
    campo("revelada_rp", "Incluida en la nota de partes relacionadas (Sí/No)", requerido=False,
          alias=("revelada", "revelada rp", "en la nota", "incluida en la nota", "revelada en notas"), ejemplo=""),
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
              "umbralBancarizacion": 500, "gastosSegunEri": None, "rpRevelado": None, "rpEvidenciaIntegridad": ""}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "metodoEri": "Método de desglose del estado de resultados (Función / Naturaleza)",
    "umbralVarPct": "Umbral de variación de la NIA 520 (%)",
    "umbralVarAbs": "Umbral de variación de la NIA 520 (importe; vacío = materialidad de ejecución)",
    "materialidadEjecucion": "Materialidad de ejecución",
    "umbralBancarizacion": "Umbral de bancarización (USD por caso entendido — contrato —, Reglamento LRTI art. 27; confirmar que sigue vigente al corte)",
    "gastosSegunEri": "Total de gastos según el estado de resultados / mayor",
    "rpRevelado": "Transacciones con partes relacionadas reveladas en notas",
    "rpEvidenciaIntegridad": ("Evidencia de que el maestro de partes relacionadas es la población completa (referencia del papel: "
                              "manifestación escrita de la administración — NIA 550 párr. 26 — o corte certificado del maestro). "
                              "Vacío: la integridad de la revelación no se concluye"),
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
    ("11_RP_Integridad", "Integridad de la revelación de partes relacionadas"),
    ("12_Inusuales", "Partidas inusuales"), ("13_Tributario", "Referencia tributaria (Ecuador)"),
    ("14_Ajustes", "Ajustes y conciliación"), ("15_Asientos", "Asientos propuestos"), ("16_Problemas", "Problemas encontrados"),
]

_SI = {"si", "s", "x", "yes", "y", "1", "true", "verdadero"}
_NO = {"no", "n", "0", "false", "falso"}
_BOOL = ("soporte", "comprobante_valido", "bancarizado", "parte_relacionada", "inusual", "revelada_rp")


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
    rp_evid = str(p.get("rpEvidenciaIntegridad") or "").strip()
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
    for t in rp:
        t["catValida"] = "Sí" if t["categoria"].lower() in validas else "No"
        t["noReveladaMarca"] = t["importe"] if t["revelada_rp"] == "No" else 0

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
    rp_nr_marca = sum(t["noReveladaMarca"] for t in rp)
    # Integridad de la revelación (decisión del socio): sin evidencia de población completa no se concluye.
    if not rp_evid:
        rp_estado = "No concluida por falta de evidencia de población completa"
    elif rp_tot == 0:
        rp_estado = "Sin transacciones con partes relacionadas en la muestra"
    elif rp_rev is None:
        rp_estado = "No concluida: falta el importe revelado en notas"
    elif rp_nr > 0.005 or rp_nr_marca > 0.005:
        rp_estado = "Revelación incompleta: hay transacciones sin revelar"
    else:
        rp_estado = "Revelación completa según la evidencia examinada"

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
        # NIC 1.103 lo exige igual que PYMES 5.11 b): con el método por función, el costo de ventas va por separado.
        if not any("costo de venta" in g["clas"].lower() or "coste de venta" in g["clas"].lower() for g in eri_l):
            problemas.append(problema("COSTO_VENTAS_NO_SEPARADO", "Método por función sin línea de costo de ventas: "
                                      + ("la Sección 5.11 b)" if pymes else "la NIC 1 párr. 103")
                                      + " exige revelar el costo de ventas por separado de otros gastos."))
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
        for t in rp:
            if t["noReveladaMarca"]:
                problemas.append(problema("RP_TRANSACCION_NO_REVELADA", f"{t['comp']} {t['proveedor']}: transacción con parte relacionada marcada como "
                                          "no incluida en la nota; revélela con la naturaleza de la relación y el importe "
                                          + ("(Sección 33.9–33.10)." if pymes else "(NIC 24 párr. 18–19)."), t["importe"]))
        sm = [t for t in rp if t["revelada_rp"] is None]
        if sm:
            problemas.append(problema("DATO_RP_REVELADA_FALTANTE", f"{len(sm)} transacción(es) con partes relacionadas sin indicar si están en la nota: "
                                      + ", ".join(t["comp"] for t in sm) + ". Complete la columna «Incluida en la nota de partes relacionadas».",
                                      sum(t["importe"] for t in sm)))
    if not rp_evid:
        problemas.append(problema("RP_INTEGRIDAD_NO_CONCLUIDA", "No se concluye sobre la integridad de la revelación de partes relacionadas: no consta "
                                  "evidencia de que el maestro recibido sea la población completa. Obtenga la manifestación escrita de la administración "
                                  "sobre la identidad de todas las partes relacionadas y de todas las transacciones de las que tiene conocimiento "
                                  "(NIA 550 párr. 26) o el corte certificado del maestro (nombre, relación y período) y regístrelo en el parámetro "
                                  "«Evidencia de integridad de la población de partes relacionadas». La herramienta procesa la población recibida, pero "
                                  "la conclusión de integridad queda «no concluida».", rp_tot))
    for t in inus:
        det = ("iguala o supera la materialidad: revele su naturaleza e importe por separado (NIC 1 párr. 97" + ("; PYMES 5.9" if pymes else "") + "; se usa la materialidad de ejecución como aproximación (NIC 1.97 se refiere a la importancia relativa))"
               if t["revelarSep"] == "Sí" else "evalúe su naturaleza y si requiere revelación separada"
               + (" (materialidad no informada)" if mat is None else ""))
        problemas.append(problema("PARTIDA_INUSUAL", f"{t['comp']} {t['proveedor']}: partida inusual; {det}.", t["importe"]))
    for t in reg:
        if t["ndComp"]:
            problemas.append(problema("SIN_COMPROBANTE_VALIDO", f"{t['comp']} {t['proveedor']}: sin comprobante de venta válido; no deducible "
                                      "(LRTI art. 10 num. 1, texto oficial del SRI vigente hasta el 2-7-2021: confirmar reformas posteriores).", t["importe"]))
        if t["ndBanco"]:
            problemas.append(problema("SIN_BANCARIZACION", f"{t['comp']} {t['proveedor']}: pago mayor a {m(uban)} sin bancarización; no deducible "
                                      "(Reglamento LRTI art. 27, por caso entendido; confirmar que el umbral sigue vigente al corte).", t["importe"]))
    fuera = sorted({t["cuenta"] for t in trans if t["cuenta"].lower() not in idx_cta})
    if fuera:
        problemas.append(problema("CUENTA_FUERA_DE_SUMARIA", "Cuentas de la muestra que no están en la sumaria: " + ", ".join(fuera) + "."))

    iso = lambda d: d.isoformat() if d else None
    rows = [{"id": c["cuenta"], "nombre": c["nombre"], "clasificacion": c["clas"], "saldoActual": r2(c["actual"]),
             "saldoAnterior": "" if c["anterior"] is None else r2(c["anterior"]), "variacion": "" if c["var"] is None else r2(c["var"]),
             "variacionPct": "" if c["pct"] is None else f"{c['pct']:.6f}", "excedeUmbral": c["excede"] or "", "_row": c["_row"]} for c in cuentas]
    totales = {"gastoTotal": total, "gastoAnterior": sum(c["anterior"] or 0 for c in cuentas), "noRegistradoCorte": no_reg,
               "devengadoNoRegistrado": dev_nr, "otroPeriodo": otro, "anticipado": antic, "ajusteGasto": ajuste, "noSoportado": no_sop,
               "reclasificaciones": rec_tot, "partesRelacionadas": rp_tot, "rpNoReveladas": rp_nr, "rpNoReveladaMarcada": rp_nr_marca,
               "inusuales": inus_tot, "noDeducible": no_ded}
    etiquetas = {"gastoTotal": "Gastos según la sumaria (año actual)", "gastoAnterior": "Gastos año anterior",
                 "noRegistradoCorte": "Gastos del ejercicio no registrados (corte)", "devengadoNoRegistrado": "Gastos devengados no registrados",
                 "otroPeriodo": "Gastos de otro período registrados (corte)", "anticipado": "Gastos anticipados llevados a resultados",
                 "ajusteGasto": "Ajuste propuesto al gasto (neto)", "noSoportado": "Gastos no soportados",
                 "reclasificaciones": "Reclasificaciones entre cuentas", "partesRelacionadas": "Transacciones con partes relacionadas",
                 "rpNoReveladas": "Partes relacionadas no reveladas", "rpNoReveladaMarcada": "Partes relacionadas marcadas como no incluidas en la nota",
                 "inusuales": "Partidas inusuales",
                 "noDeducible": "No deducible (referencia tributaria)"}
    if dif_conc is not None:
        totales["difConciliacion"] = dif_conc
        etiquetas["difConciliacion"] = "Diferencia sumaria vs estado de resultados"
    detalle = {"cortes": {"actual": corte_a.isoformat()}, "parametros": p, "pymes": pymes, "edicion": edicion_pymes(p) if pymes else "",
               "metodo": metodo, "upct": upct, "uabsIn": uabs_in, "mat": mat, "uabs": uabs, "uban": uban, "eri": eri, "rpRev": rp_rev,
               "cuentas": cuentas, "eri_l": eri_l, "rpCat": rp_cat, "categorias": cats, "rpEvid": rp_evid, "rpEstado": rp_estado,
               "trans": [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in t.items()} for t in trans]}
    return {"engine": VERSION, "rows": rows, "totals": {k: r2(v) for k, v in totales.items()}, "labels": etiquetas,
            "primary": "ajusteGasto", "exceptions": problemas, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

P = ref("02_Parametros")
CTA, TRX, VOU, COR, DEV, REC, RPS, RPI, INU, TRI, AJ = (ref(n) for n in (
    "03_Analisis_global", "05_Transacciones", "06_Vouching", "07_Corte", "08_Devengo", "09_Reclasificaciones",
    "10_Partes_relacionadas", "11_RP_Integridad", "12_Inusuales", "13_Tributario", "14_Ajustes"))
_PAR = ["corte", "marco", "metodoEri", "requisito", "umbralVarPct", "umbralVarAbs", "materialidadEjecucion", "umbralAbs",
        "umbralBancarizacion", "gastosSegunEri", "rpRevelado", "rpEvidencia"]
PAR = {k: FILA0 + i for i, k in enumerate(_PAR)}
_AJ = ["noReg", "devNoReg", "otro", "antic", "ajuste", "noSop", "reclas", "rp", "rpRev", "rpNr", "sumaria", "eri", "difConc", "noDed", "inus"]
AJF = {k: FILA0 + i for i, k in enumerate(_AJ)}


def _pb(k):
    return f"{P}$B${PAR[k]}"


def _rng(hoja_ref: str, col: str, n: int) -> str:
    return f"{hoja_ref}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


_IMP_05 = "Trae el importe del comprobante desde la hoja 05 (Transacciones de la muestra); "

# Explicaciones humanas de «Cómo se calcula esta hoja» (una por columna calculada).
EXPLICA = {
    "01_Resumen": {
        "Importe": ("Trae cada importe de la hoja 14 (Ajustes y conciliación), concepto por concepto; los gastos del año anterior "
                    "suman la columna «Saldo anterior» de la hoja 03 (Análisis global) y las partes relacionadas marcadas como no "
                    "incluidas salen del total de la hoja 11 (Integridad de la revelación)."),
    },
    "02_Parametros": {
        "Valor": ("Solo el «Umbral absoluto aplicado» se calcula: usa el umbral de variación en importe y, si está vacío, la "
                  "materialidad de ejecución; los demás valores son datos de la ficha del encargo y del auditor."),
    },
    "03_Analisis_global": {
        "Variación": "Resta el saldo del año anterior al saldo actual de la cuenta; si no hay saldo anterior, queda en blanco.",
        "Variación %": ("Divide la variación para el saldo del año anterior; queda en blanco si no hay saldo anterior o si "
                        "ese saldo es cero."),
        "Excede umbral": ("Compara la variación con los umbrales de la hoja 02 (Parámetros): si en valor absoluto no pasa el "
                          "umbral absoluto aplicado es «No»; si lo pasa, es «Sí» cuando el saldo anterior es cero o la "
                          "variación % supera el umbral en %."),
        "Variación vs presupuesto": ("Resta el presupuesto de la cuenta a su saldo actual; si la cuenta no tiene presupuesto, "
                                     "queda en blanco."),
        "Variación vs presupuesto %": ("Divide la variación contra el presupuesto para el presupuesto; queda en blanco si no "
                                       "hay presupuesto o si es cero."),
        "Excede umbral (presupuesto)": ("Aplica la misma prueba de umbrales de la hoja 02 (Parámetros) a la variación contra "
                                        "el presupuesto: «Sí» solo si supera el umbral absoluto y, además, el presupuesto es "
                                        "cero o la variación % supera el umbral en %."),
        "Variación sin explicar": ("Marca «Sí» cuando la cuenta excede el umbral (contra el año anterior o contra el "
                                   "presupuesto) y la columna «Explicación» está vacía; en otro caso, «No»."),
        "Muestra examinada": ("Suma los importes de las transacciones de la hoja 05 (Transacciones de la muestra) "
                              "registradas en esta cuenta y dentro del ejercicio."),
        "Cobertura de la muestra": ("Divide la muestra examinada para el saldo actual de la cuenta: indica qué parte del "
                                    "gasto se revisó con documentos; en blanco si el saldo es cero."),
        "Presentada como extraordinaria": ("Marca «Sí» si el nombre de la cuenta o su línea del estado de resultados "
                                           "contiene la palabra «extraordinario/a»; en otro caso, «No»."),
    },
    "04_Presentacion_ERI": {
        "Cuentas": ("Cuenta cuántas cuentas de la hoja 03 (Análisis global) están asignadas a esta línea del estado de "
                    "resultados."),
        "Año actual": "Suma el saldo actual de las cuentas de la hoja 03 (Análisis global) asignadas a esta línea.",
        "Año anterior": "Suma el saldo del año anterior de las cuentas de la hoja 03 (Análisis global) asignadas a esta línea.",
        "Variación": "Resta el importe del año anterior al del año actual de esta línea del estado de resultados.",
        "% del gasto total": ("Divide el gasto del año actual de la línea para el total de saldos actuales de la hoja 03 "
                              "(Análisis global); en blanco si ese total es cero."),
        "«Extraordinaria» (prohibido)": ("Marca «Sí» si el nombre de la línea del estado de resultados contiene la palabra "
                                         "«extraordinario/a»; en otro caso, «No»."),
    },
    "05_Transacciones": {
        "Registrado en el ejercicio": ("Marca «Sí» si la fecha de registro del comprobante es igual o anterior a la fecha de "
                                       "corte de la hoja 02 (Parámetros)."),
        "Con período de servicio": ("Marca «Sí» cuando el comprobante tiene fechas de inicio y de fin del servicio; esas "
                                    "partidas se analizan por devengo en la hoja 08 y las demás por corte en la hoja 07."),
    },
    "06_Vouching": {
        "Importe": _IMP_05 + "aquí solo aparecen los registrados en el ejercicio.",
        "Gasto no soportado": "Si la columna «Tiene soporte» dice «No», toma el importe completo del comprobante; si no, cero.",
        "Resultado": ("Traduce la columna «Tiene soporte»: «Sí» es «Soportado», «No» es «No soportado» y, si está vacía, "
                      "«Sin resultado informado»."),
    },
    "07_Corte": {
        "Importe": _IMP_05 + "aquí solo aparecen los que no tienen período de servicio.",
        "Documento del ejercicio": ("Marca «Sí» si la fecha del documento es igual o anterior al corte de la hoja 02 "
                                    "(Parámetros)."),
        "Registrado en el ejercicio": ("Marca «Sí» si la fecha de registro contable es igual o anterior al corte de la hoja "
                                       "02 (Parámetros)."),
        "Gasto de otro período registrado": ("Si el documento es posterior al corte pero se registró dentro del ejercicio, "
                                             "toma su importe: es gasto del año siguiente; si no, cero."),
        "Gasto del ejercicio no registrado": ("Si el documento es del ejercicio pero se registró después del corte, toma su "
                                              "importe: es gasto que faltó registrar; si no, cero."),
    },
    "08_Devengo": {
        "Importe": _IMP_05 + "aquí solo aparecen los que tienen período de servicio.",
        "Días del servicio": "Cuenta los días del servicio, desde la fecha de inicio hasta la de fin, incluidos ambos días.",
        "Días hasta el corte": ("Cuenta los días del servicio desde su inicio hasta la fecha de fin o hasta el corte de la "
                                "hoja 02 (Parámetros), lo que ocurra primero; nunca menos de cero."),
        "Días posteriores": ("Resta los días hasta el corte a los días totales del servicio: son los días que corresponden "
                             "al año siguiente."),
        "Gasto del período": ("Reparte el importe en proporción a los días: importe × días hasta el corte ÷ días del "
                              "servicio."),
        "Registrado en el ejercicio": ("Marca «Sí» si la fecha de registro es igual o anterior al corte de la hoja 02 "
                                       "(Parámetros)."),
        "Anticipado llevado a resultados": ("Si el comprobante se registró en el ejercicio, calcula la parte del importe de "
                                            "los días posteriores al corte (importe × días posteriores ÷ días del "
                                            "servicio): es gasto pagado por anticipado; si no, cero."),
        "Devengado no registrado": ("Si el comprobante se registró después del corte, toma el gasto del período: es "
                                    "servicio consumido en el año que no llegó a registrarse; si no, cero."),
    },
    "09_Reclasificaciones": {
        "Importe": _IMP_05 + "aquí solo aparecen los registrados en una cuenta distinta de la cuenta sugerida.",
        "Línea registrada": ("Busca en la hoja 03 (Análisis global) la línea del estado de resultados de la cuenta donde se "
                             "registró; si la cuenta no está en la sumaria, lo indica."),
        "Línea correcta": ("Busca en la hoja 03 (Análisis global) la línea del estado de resultados de la cuenta correcta; "
                           "si no está en la sumaria, lo indica."),
        "Cambia la línea del estado de resultados": ("Marca «Sí» cuando la línea registrada y la correcta son distintas, es "
                                                     "decir, cuando la reclasificación cambia la presentación en el estado "
                                                     "de resultados."),
    },
    "10_Partes_relacionadas": {
        "Transacciones": ("Cuenta las transacciones de la hoja 05 (Transacciones de la muestra) marcadas como parte "
                          "relacionada, registradas en el ejercicio y con esta categoría; la fila «Sin categoría válida» "
                          "cuenta las que quedan fuera de las categorías del marco."),
        "Importe del período": ("Suma el importe de esas mismas transacciones de la hoja 05 por categoría; la fila «Sin "
                                "categoría válida» es el total con partes relacionadas menos lo ya asignado a las "
                                "categorías del marco."),
    },
    "11_RP_Integridad": {
        "Importe": _IMP_05 + "aquí solo aparecen las transacciones con partes relacionadas registradas en el ejercicio.",
        "Categoría válida para el marco": ("Marca «Sí» si la categoría informada está entre las categorías del marco "
                                           "listadas en la hoja 10 (Partes relacionadas); si está vacía o no coincide, "
                                           "«No»."),
        "Importe no revelado (marca)": ("Si la transacción está marcada como no incluida en la nota, toma su importe; "
                                        "si no, cero."),
        "Conclusión de integridad de la revelación": ("Solo en la fila TOTAL: sin evidencia de integridad en la hoja 02 "
                                                      "(Parámetros) no se concluye; con ella, revisa si hay importes con "
                                                      "partes relacionadas, si se informó lo revelado en notas y si queda "
                                                      "algo sin revelar."),
    },
    "12_Inusuales": {
        "Importe": _IMP_05 + "aquí solo aparecen las partidas marcadas como inusuales y registradas en el ejercicio.",
        "Revelar por separado (≥ materialidad)": ("Marca «Sí» si el importe iguala o supera la materialidad de ejecución de "
                                                  "la hoja 02 (Parámetros); si no hay materialidad informada, queda en "
                                                  "blanco."),
    },
    "13_Tributario": {
        "Importe": _IMP_05 + "aquí aparecen todos los registrados en el ejercicio.",
        "Supera el umbral de bancarización": ("Marca «Sí» si el importe es mayor que el umbral de bancarización de la hoja "
                                              "02 (Parámetros)."),
        "No deducible: comprobante": ("Si el comprobante no es válido, todo su importe queda como no deducible; si no, "
                                      "cero."),
        "No deducible: bancarización": ("Si el pago supera el umbral de bancarización, no se pagó por banco y el comprobante "
                                        "no está marcado como inválido, su importe queda como no deducible; si no, cero "
                                        "(así no se cuenta dos veces)."),
        "No deducible total": "Suma lo no deducible por comprobante y lo no deducible por bancarización del mismo pago.",
    },
    "14_Ajustes": {
        "Importe": ("Trae cada importe del total de su hoja de origen (06, 07, 08, 09, 10, 12 y 13) o de la hoja 02 "
                    "(Parámetros); el ajuste neto = no registrados + devengados no registrados − otro período − "
                    "anticipados; las partes relacionadas no reveladas = identificadas − reveladas (nunca negativo); la "
                    "diferencia = gastos de la sumaria (hoja 03) − estado de resultados."),
    },
    "15_Asientos": {
        "Debe": ("Trae de la hoja 14 (Ajustes y conciliación) el importe de cada ajuste —o de la hoja 09 "
                 "(Reclasificaciones) en las reclasificaciones— para la cuenta que se debita."),
        "Haber": ("Trae el mismo importe del ajuste de la hoja 14 (Ajustes y conciliación) o de la hoja 09 "
                  "(Reclasificaciones) para la cuenta que se acredita, de modo que el asiento cuadra."),
    },
}

# Panel del dashboard (formato en graficos.py): la población es el gasto de la sumaria; el auditor recalcula por días
# el gasto devengado de los servicios con período y lo compara con lo que el cliente llevó a gasto en el ejercicio
# (las facturas contabilizadas; una registrada después del corte queda fuera del registrado).
PANEL = {
    "poblacion": {"rotulo": "Gasto total de la sumaria", "hoja": "03_Analisis_global", "col": "Saldo actual"},
    "recalculado": {"rotulo": "Gasto devengado del período (muestra)", "hoja": "08_Devengo", "col": "Gasto del período"},
    "registrado": {"rotulo": "Gasto registrado en el período (muestra)", "hoja": "08_Devengo", "col": "Importe",
                   "donde": {"Registrado en el ejercicio": ["Sí"]}},
    "composicion": {"rotulo": "Gasto devengado por proveedor", "hoja": "08_Devengo", "etiqueta": "Proveedor",
                    "valor": "Gasto del período"},
    "distribucion": {"rotulo": "Gasto por línea del ERI", "hoja": "04_Presentacion_ERI",
                     "etiqueta": "Línea del estado de resultados", "valor": "Año actual"},
}


# --- origen del importe de cada problema (ver procesadores/problemas.py) --------------

_T = problemas._texto


def _pr_hoja(hojas, nombre):
    return next((x for x in hojas if x["name"] == nombre), None)


def _pr_rango(hojas, hoja_: str, col: str) -> str:
    """Rango de la columna sobre las filas de datos de la cédula (sin la fila TOTAL)."""
    n = max(len(_pr_hoja(hojas, hoja_)["rows"]), 1)
    return f"{problemas.celda(hojas, hoja_, col, 0)}:{problemas.celda(hojas, hoja_, col, n - 1).split('!')[1]}"


def _por_fila(hoja_: str, columna, id_col: int, prov_col: int | None = None):
    """Celda de la columna en la fila que abre la descripción del problema: «cuenta nombre…» o
    «comprobante proveedor:». ``columna`` puede ser una función (fila, columnas) -> título."""
    def f(hojas, e):
        h = _pr_hoja(hojas, hoja_)
        if h is None:
            return None
        msg = e.get("message") or ""
        cols = [c[0] for c in h["cols"]]
        for i, fila in enumerate(h["rows"]):
            pref = f"{_T(fila[id_col])} {_T(fila[prov_col])}" if prov_col is not None else _T(fila[id_col])
            if msg.startswith(f"{pref}:") or msg.startswith(f"{pref} ("):
                col = columna(fila, cols) if callable(columna) else columna
                return problemas.celda(hojas, hoja_, col, i), fila[cols.index(col)]
        return None
    return f


def _fila_ajustes(clave: str):
    """Fila de la hoja 14 (Ajustes y conciliación) donde se calcula el concepto."""
    def f(hojas, e):
        i = _AJ.index(clave)
        return problemas.celda(hojas, "14_Ajustes", "Importe", i), _pr_hoja(hojas, "14_Ajustes")["rows"][i][1]
    return f


def _sumif(hoja_: str, col_crit: str, criterio: str, cond, col_suma: str):
    """SUMIF(rango de criterio; criterio; rango a sumar) sobre las filas de datos de la cédula."""
    def f(hojas, e):
        h = _pr_hoja(hojas, hoja_)
        if h is None or not h["rows"]:
            return None
        cols = [c[0] for c in h["cols"]]
        jc, js = cols.index(col_crit), cols.index(col_suma)
        valor = sum(problemas._num(x[js]) or 0 for x in h["rows"] if cond(x[jc]))
        return f"SUMIF({_pr_rango(hojas, hoja_, col_crit)},{criterio},{_pr_rango(hojas, hoja_, col_suma)})", valor
    return f


def _col_variacion(fila, cols):
    """La variación que supera el umbral: contra el año anterior o, si no, contra el presupuesto."""
    return "Variación" if _T(fila[cols.index("Excede umbral")]) == "Sí" else "Variación vs presupuesto"


def _rp_sin_categoria(hojas, e):
    """Importe de la fila «Sin categoría válida» de la hoja 10 (Partes relacionadas)."""
    h = _pr_hoja(hojas, "10_Partes_relacionadas")
    i = next((k for k, x in enumerate(h["rows"]) if _T(x[0]) == SIN_CATEGORIA), None)
    return None if i is None else (problemas.celda(hojas, "10_Partes_relacionadas", "Importe del período", i), h["rows"][i][2])


def _vacio(v) -> bool:
    return _T(v) == "" and problemas._num(v) is None


# De qué celda sale el importe de cada problema.
REF_PROBLEMAS = {
    "VARIACION_SIN_EXPLICAR": _por_fila("03_Analisis_global", _col_variacion, 0, 1),        # variación sobre el umbral
    "PARTIDA_EXTRAORDINARIA": _por_fila("03_Analisis_global", "Saldo actual", 0, 1),        # saldo de la cuenta «extraordinaria»
    "NATURALEZA_NO_REVELADA": _sumif("03_Analisis_global", "Naturaleza", '""', _vacio, "Saldo actual"),  # cuentas sin naturaleza
    "DIF_CONCILIACION": _fila_ajustes("difConc"),                                            # sumaria − estado de resultados
    "SALDO_ACREEDOR": _por_fila("03_Analisis_global", "Saldo actual", 0, 1),                # saldo acreedor de la cuenta
    "GASTO_NO_SOPORTADO": _por_fila("06_Vouching", "Gasto no soportado", 0, 3),             # importe sin soporte
    "DATO_VOUCHING_FALTANTE": _sumif("06_Vouching", "Resultado", '"Sin resultado informado"',
                                     lambda v: _T(v) == "Sin resultado informado", "Importe"),  # transacciones sin resultado
    "CORTE_OTRO_PERIODO": _por_fila("07_Corte", "Gasto de otro período registrado", 0, 1),  # documento posterior registrado
    "CORTE_NO_REGISTRADO": _por_fila("07_Corte", "Gasto del ejercicio no registrado", 0, 1),  # documento del año sin registrar
    "GASTO_ANTICIPADO_EN_RESULTADOS": _por_fila("08_Devengo", "Anticipado llevado a resultados", 0, 1),  # días posteriores al corte
    "DEVENGADO_NO_REGISTRADO": _por_fila("08_Devengo", "Devengado no registrado", 0, 1),    # gasto del período no registrado
    "CLASIFICACION_INCORRECTA": _por_fila("09_Reclasificaciones", "Importe", 0, 1),         # importe a reclasificar
    "SIN_RP_REVELADO": ("10_Partes_relacionadas", "Importe del período", "total"),          # partes relacionadas de la muestra
    "RP_NO_REVELADAS": _fila_ajustes("rpNr"),                                                # MAX(muestra − revelado, 0)
    "RP_SIN_CATEGORIA": _rp_sin_categoria,                                                   # fila «Sin categoría válida»
    "RP_TRANSACCION_NO_REVELADA": _por_fila("11_RP_Integridad", "Importe no revelado (marca)", 0, 1),  # marcada fuera de la nota
    "DATO_RP_REVELADA_FALTANTE": _sumif("11_RP_Integridad", "Incluida en la nota", '""', _vacio, "Importe"),  # sin indicar
    "RP_INTEGRIDAD_NO_CONCLUIDA": ("11_RP_Integridad", "Importe", "total"),                  # población sin conclusión
    "PARTIDA_INUSUAL": _por_fila("12_Inusuales", "Importe", 0, 3),                          # importe de la partida inusual
    "SIN_COMPROBANTE_VALIDO": _por_fila("13_Tributario", "No deducible: comprobante", 0, 1),  # no deducible por comprobante
    "SIN_BANCARIZACION": _por_fila("13_Tributario", "No deducible: bancarización", 0, 1),   # no deducible por bancarización
}


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
                     else "Revelar el costo de ventas por separado (NIC 1 párr. 103) e información por naturaleza: "
                          "amortización y retribuciones a los empleados (NIC 1 párr. 104)")
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
        ["Umbral de bancarización (USD)", d["uban"], "Por caso entendido (contrato), Reglamento LRTI art. 27 (reforma de 15-7-2025) — confirmar que sigue vigente al corte"],
        ["Gastos según el estado de resultados / mayor", d["eri"], "Estado de resultados o balance de comprobación"],
        ["Partes relacionadas reveladas en notas", d["rpRev"], "Nota de partes relacionadas (NIC 24 párr. 18 / PYMES 33.9)"],
        ["Evidencia de integridad de la población de partes relacionadas", d["rpEvid"] or None,
         "Manifestación escrita de la administración (NIA 550 párr. 26) o corte certificado del maestro. Vacío: la integridad no se concluye"],
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

    # 11 · Integridad de la revelación: detalle por transacción y estado de la conclusión (decisión del socio).
    rpl = [x for x in reg if x["parte_relacionada"] == "Sí"]
    cat_val = _rng(RPS, "A", nrp - 1)       # categorías del marco, sin la fila «Sin categoría válida»
    rpi = []
    for j, x in enumerate(rpl):
        r = FILA0 + j
        rpi.append([x["comp"], x["proveedor"], x["cuenta"], imp(x), x["categoria"] or None,
                    fx(f'IF(E{r}="","No",IF(COUNTIF({cat_val},E{r})>0,"Sí","No"))', x["catValida"]),
                    x["revelada_rp"], fx(f'IF(G{r}="No",D{r},0)', n2(x["noReveladaMarca"])), ""])
    fin_rpi = FILA0 + len(rpl) - 1
    trp = FILA0 + len(rpl)                  # fila TOTAL de esta cédula
    ev, rv = _pb("rpEvidencia"), _pb("rpRevelado")
    conclusion = (f'IF({ev}="","No concluida por falta de evidencia de población completa",'
                  f'IF(D{trp}=0,"Sin transacciones con partes relacionadas en la muestra",'
                  f'IF({rv}="","No concluida: falta el importe revelado en notas",'
                  f'IF(OR(MAX(D{trp}-{rv},0)>0.005,H{trp}>0.005),"Revelación incompleta: hay transacciones sin revelar",'
                  '"Revelación completa según la evidencia examinada"))))')
    tot_rpi = ["TOTAL", "", "", suma("D", fin_rpi, t["partesRelacionadas"]) if rpl else 0, "", "",
               "", suma("H", fin_rpi, t["rpNoReveladaMarcada"]) if rpl else 0, fx(conclusion, d["rpEstado"])]

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
        ["No deducible (referencia tributaria)", fx(tot_ref(TRI, "I", len(reg)), t["noDeducible"]), "13_Tributario"],
        ["Partidas inusuales", fx(tot_ref(INU, "E", len(il)), t["inusuales"]), "12_Inusuales"],
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
               "rpNoReveladaMarcada": f"{RPI}H{trp}", "inusuales": ajb("inus"), "noDeducible": ajb("noDed"), "difConciliacion": ajb("difConc")}
    resumen = [[res["labels"][k], fx(ref_res[k], t[k])] for k in res["labels"]]

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen, explica=EXPLICA["01_Resumen"]),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros, explica=EXPLICA["02_Parametros"]),
        hoja("03_Analisis_global", "Análisis global por cuenta (NIA 520)",
             [["Cuenta", "t"], ["Nombre", "t"], ["Línea del estado de resultados", "t"], ["Naturaleza", "t"], ["Saldo actual", "n"],
              ["Saldo anterior", "n"], ["Variación", "n"], ["Variación %", "p"], ["Excede umbral", "t"], ["Presupuesto", "n"],
              ["Variación vs presupuesto", "n"], ["Variación vs presupuesto %", "p"], ["Excede umbral (presupuesto)", "t"],
              ["Explicación", "t"], ["Variación sin explicar", "t"], ["Muestra examinada", "n"], ["Cobertura de la muestra", "p"],
              ["Presentada como extraordinaria", "t"]], analisis, tot_an, explica=EXPLICA["03_Analisis_global"]),
        hoja("04_Presentacion_ERI", "Presentación en el estado de resultados",
             [["Línea del estado de resultados", "t"], ["Cuentas", "i"], ["Año actual", "n"], ["Año anterior", "n"], ["Variación", "n"],
              ["% del gasto total", "p"], ["«Extraordinaria» (prohibido)", "t"]], pres, tot_pres, explica=EXPLICA["04_Presentacion_ERI"]),
        hoja("05_Transacciones", "Transacciones de la muestra",
             [["Comprobante", "t"], ["Fecha documento", "d"], ["Fecha registro", "d"], ["Servicio desde", "d"], ["Servicio hasta", "d"],
              ["Importe", "n"], ["Cuenta", "t"], ["Proveedor", "t"], ["Soporte", "t"], ["Comprobante válido SRI", "t"],
              ["Pagado por banco", "t"], ["Parte relacionada", "t"], ["Categoría parte relacionada", "t"], ["Cuenta sugerida", "t"],
              ["Inusual", "t"], ["Registrado en el ejercicio", "t"], ["Con período de servicio", "t"]], trans, tot_tr, explica=EXPLICA["05_Transacciones"]),
        hoja("06_Vouching", "Verificación del soporte documental",
             [["Comprobante", "t"], ["Fecha documento", "d"], ["Cuenta", "t"], ["Proveedor", "t"], ["Importe", "n"], ["Tiene soporte", "t"],
              ["Gasto no soportado", "n"], ["Resultado", "t"]], vou, tot_vou, explica=EXPLICA["06_Vouching"]),
        hoja("07_Corte", "Corte de gastos",
             [["Comprobante", "t"], ["Proveedor", "t"], ["Cuenta", "t"], ["Fecha documento", "d"], ["Fecha registro", "d"], ["Importe", "n"],
              ["Documento del ejercicio", "t"], ["Registrado en el ejercicio", "t"], ["Gasto de otro período registrado", "n"],
              ["Gasto del ejercicio no registrado", "n"]], cor, tot_cor, explica=EXPLICA["07_Corte"]),
        hoja("08_Devengo", "Devengo y gastos anticipados",
             [["Comprobante", "t"], ["Proveedor", "t"], ["Cuenta", "t"], ["Fecha registro", "d"], ["Servicio desde", "d"], ["Servicio hasta", "d"],
              ["Importe", "n"], ["Días del servicio", "i"], ["Días hasta el corte", "i"], ["Días posteriores", "i"], ["Gasto del período", "n"],
              ["Registrado en el ejercicio", "t"], ["Anticipado llevado a resultados", "n"], ["Devengado no registrado", "n"]], dev, tot_dev, explica=EXPLICA["08_Devengo"]),
        hoja("09_Reclasificaciones", "Reclasificaciones",
             [["Comprobante", "t"], ["Proveedor", "t"], ["Cuenta registrada", "t"], ["Cuenta correcta", "t"], ["Importe", "n"],
              ["Línea registrada", "t"], ["Línea correcta", "t"], ["Cambia la línea del estado de resultados", "t"]], rec, tot_rec, explica=EXPLICA["09_Reclasificaciones"]),
        hoja("10_Partes_relacionadas", "Partes relacionadas",
             [["Categoría", "t"], ["Transacciones", "i"], ["Importe del período", "n"], ["Referencia", "t"]], rps, tot_rp, explica=EXPLICA["10_Partes_relacionadas"]),
        hoja("11_RP_Integridad", "Integridad de la revelación de partes relacionadas",
             [["Comprobante", "t"], ["Proveedor", "t"], ["Cuenta", "t"], ["Importe", "n"], ["Categoría informada", "t"],
              ["Categoría válida para el marco", "t"], ["Incluida en la nota", "t"], ["Importe no revelado (marca)", "n"],
              ["Conclusión de integridad de la revelación", "t"]], rpi, tot_rpi, explica=EXPLICA["11_RP_Integridad"]),
        hoja("12_Inusuales", "Partidas inusuales",
             [["Comprobante", "t"], ["Fecha documento", "d"], ["Cuenta", "t"], ["Proveedor", "t"], ["Importe", "n"],
              ["Revelar por separado (≥ materialidad)", "t"]], inu, tot_inu, explica=EXPLICA["12_Inusuales"]),
        hoja("13_Tributario", "Referencia tributaria (Ecuador)",
             [["Comprobante", "t"], ["Proveedor", "t"], ["Importe", "n"], ["Comprobante válido", "t"], ["Pagado por banco", "t"],
              ["Supera el umbral de bancarización", "t"], ["No deducible: comprobante", "n"], ["No deducible: bancarización", "n"],
              ["No deducible total", "n"]], tri, tot_tri, explica=EXPLICA["13_Tributario"]),
        hoja("14_Ajustes", "Ajustes y conciliación", [["Concepto", "t"], ["Importe", "n"], ["Referencia", "t"]], ajustes, explica=EXPLICA["14_Ajustes"]),
        hoja("15_Asientos", "Asientos propuestos", [["Asiento", "t"], ["Cuenta", "t"], ["Debe", "n"], ["Haber", "n"]], asientos, explica=EXPLICA["15_Asientos"]),
        hoja("16_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], n2(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición -----------------------------------------------------------------

def definicion() -> dict:
    cuentas = ("Una fila por cuenta de gasto: código, nombre, línea del estado de resultados (por función o por naturaleza), saldo del año "
               "actual y, si existen, saldo del año anterior, presupuesto, naturaleza del gasto y explicación de la variación. Sin filas de total.")
    trans = ("Una fila por comprobante de la muestra (del ejercicio y posteriores al corte): comprobante, fecha del documento, fecha de registro, "
             "período del servicio (desde/hasta) si es un servicio por tiempo, importe, cuenta, proveedor y las marcas del auditor (soporte, "
             "comprobante válido SRI, pagado por banco, parte relacionada y su categoría, si la transacción está incluida en la nota de partes "
             "relacionadas, cuenta correcta, inusual).")
    maestro = ("Población COMPLETA de partes relacionadas al corte: una fila por parte relacionada con su nombre o razón social, la naturaleza "
               "de la relación (controladora, controlada, asociada, negocio conjunto, personal clave de la gerencia, otras) y el período en que "
               "tuvo esa condición durante el ejercicio. Sin este maestro no se puede concluir sobre la integridad de la revelación.")
    return {
        "name": "Gastos · análisis global, verificación del soporte, corte, devengo, clasificación y partes relacionadas",
        "area": "Costos y gastos",
        "processor": "gastos_analisis",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Compara cada cuenta de gasto con el año anterior y el presupuesto frente a los umbrales de la NIA 520, prueba el soporte "
                    "de una muestra (verificación del soporte), el corte por fechas de documento y registro y el devengo por días del servicio (gastos "
                    "anticipados llevados a resultados y gastos devengados no registrados), cuantifica reclasificaciones, totaliza las "
                    "transacciones con partes relacionadas por categoría frente a lo revelado —exige el maestro completo de partes relacionadas y "
                    "no concluye sobre la integridad de la revelación sin evidencia de población completa (NIA 550 párr. 26)— y señala partidas presentadas como "
                    "«extraordinarias» (prohibido: NIC 1 párr. 87; PYMES 5.10) e inusuales. El requisito de desglose y las categorías de "
                    "partes relacionadas se enrutan por marco (NIC 1 párr. 103–104 y NIC 24 párr. 19; PYMES 5.11 y 33.10). Incluye una "
                    "referencia tributaria de Ecuador (comprobante válido y bancarización)."),
        "source": {"organization": "IFRS Foundation (texto en español: Reglamento (UE) 2023/1803)", "type": "Norma contable", "date": "",
                   "document": ("NIC 1 párr. 27–28 (devengo), 87 (sin partidas extraordinarias), 97–98 (partidas materiales), 99 y 102–105 "
                                "(desglose por naturaleza o función; 103: por función, costo de ventas por separado); NIC 24 párr. 18–19; NIC 8 párr. 41–42 (errores). Marco "
                                "Conceptual párr. 4.69 (definición de gasto) y 4.72 (separar ingresos y gastos de distintas características): no forma "
                                "parte del Reglamento (UE) 2023/1803; contrastado con la traducción oficial al español de la IFRS Foundation."),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015: párr. 2.23 b) y 2.26 (definición de gasto), 2.36 (base de acumulación o "
                                      "devengo), 5.9 (partidas adicionales), 5.10 (sin partidas extraordinarias), 5.11 (desglose por naturaleza "
                                      "o función; por función, costo de ventas por separado), 33.9–33.10 (partes relacionadas), Sección 10 "
                                      "(errores). Edición 2025 (tercera edición, vigente desde el 1-1-2027), numeración contrastada con el texto "
                                      "oficial: 2.63 (definición de gasto), 3.16A (devengo), 5.9, 5.10 y 5.11 y 33.9–33.10 sin cambio de número."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 520", "section": "párr. 5 y 7", "requirement": "Procedimientos analíticos sustantivos: expectativa y umbral de diferencia aceptable (párr. 5) e investigación de las diferencias (párr. 7)."},
            {"document": "NIA 500", "section": "párr. 6 y 9", "requirement": "Evidencia suficiente y adecuada (párr. 6); exactitud e integridad de la información producida por la entidad —la sumaria contra el mayor— (párr. 9)."},
            {"document": "NIA 550", "section": "párr. 13", "requirement": "Preguntar a la dirección la identidad de las partes relacionadas (y sus cambios), la naturaleza de cada relación y si hubo transacciones en el período."},
            {"document": "NIA 550", "section": "párr. 25", "requirement": "Transacciones con partes relacionadas: evaluación de su contabilización y revelación."},
            {"document": "NIA 550", "section": "párr. 26", "requirement": "Manifestaciones escritas de la administración de que reveló la identidad de todas las partes relacionadas y todas las transacciones de las que tiene conocimiento, y de que las contabilizó y reveló conforme al marco."},
            {"document": "NIA 330", "section": "párr. 18", "requirement": "Procedimientos sustantivos sobre transacciones materiales, incluido el corte."},
            {"document": "NIA 450", "section": "párr. 5", "requirement": "Acumular las incorrecciones identificadas, salvo las claramente triviales (gastos no soportados, corte, devengo)."},
        ],
        "calculo": [
            "Variación = saldo actual − saldo anterior (y − presupuesto); variación % = variación ÷ base. Excede el umbral si |variación| > umbral absoluto "
            "(o materialidad de ejecución) y, cuando la base no es cero, |variación %| > umbral %. Sin explicación → problema (NIA 520).",
            "Presentación: gasto por línea del estado de resultados; ninguna línea o cuenta puede llamarse «extraordinaria» (NIC 1 87; PYMES 5.10). "
            "Por función: los dos marcos exigen el costo de ventas por separado (NIC 1 103 / PYMES 5.11 b) y NIIF completas exige además naturaleza (NIC 1 104).",
            "Verificación del soporte: gasto registrado en el ejercicio sin soporte = gasto no soportado.",
            "Corte (comprobantes sin período de servicio): documento ≤ corte y registro > corte = gasto no registrado; documento > corte y registro ≤ corte = gasto de otro período.",
            "Devengo (con período de servicio): gasto del período = importe × días del servicio hasta el corte ÷ días del servicio. Registrado en el "
            "ejercicio → anticipado = importe × días posteriores ÷ días del servicio; registrado después → devengado no registrado = gasto del período.",
            "Ajuste propuesto al gasto = no registrados + devengados no registrados − otro período − anticipados.",
            "Reclasificación: cuenta correcta según el auditor distinta de la registrada.",
            "Partes relacionadas: importe del período por categoría (NIC 24 19 / PYMES 33.10) frente a lo revelado en notas. El maestro completo "
            "de partes relacionadas es obligatorio; la herramienta procesa la población que reciba, pero solo concluye sobre la integridad de la "
            "revelación si consta la evidencia de población completa (manifestación escrita de la administración, NIA 550 párr. 26, o corte "
            "certificado del maestro). Sin esa evidencia la conclusión queda «no concluida por falta de evidencia de población completa».",
            "Partida inusual con importe ≥ materialidad: revelación por separado (NIC 1 97; se usa la materialidad de ejecución como aproximación (NIC 1.97 se refiere a la importancia relativa)).",
            "Referencia tributaria: sin comprobante válido (LRTI art. 10 num. 1), o importe > umbral de bancarización sin pago por banco (Reglamento LRTI art. 27) = no deducible (confirmar que sigue vigente al corte).",
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
            {"code": "GAS-06", "objective": "Partes relacionadas: identificación, integridad de la población y revelación",
             "risk": "Maestro incompleto y transacciones con partes relacionadas no reveladas", "assertion": "Integridad / Presentación",
             "procedure": "Obtener el maestro COMPLETO de partes relacionadas (nombre, relación y período), preguntar a la dirección por la identidad "
                          "de las partes relacionadas y sus cambios (NIA 550 párr. 13), cruzar los proveedores de la muestra con ese maestro, "
                          "clasificar por categoría y comparar con la nota; obtener la manifestación escrita de la administración (NIA 550 párr. 26) "
                          "antes de concluir sobre la integridad de la revelación",
             "evidence": "Maestro completo de partes relacionadas, manifestación escrita de la administración, nota de revelación",
             "criterion": "Población completa evidenciada y todo lo del período revelado por categoría; sin la manifestación escrita o el corte "
                          "certificado del maestro, la integridad queda no concluida",
             "source": "NIC 24 párr. 18–19 · PYMES 33.9–33.10 · NIA 550 párr. 13, 25 y 26"},
            {"code": "GAS-07", "objective": "Partidas inusuales y referencia tributaria", "risk": "Partidas materiales sin revelar; gastos no deducibles",
             "assertion": "Presentación / Cumplimiento", "procedure": "Identificar partidas inusuales y verificar comprobante válido y bancarización",
             "evidence": "Comprobantes SRI, estados de cuenta bancarios", "criterion": "Revelación separada; no deducibles identificados",
             "source": "NIC 1 párr. 97 (partidas materiales por separado) · LRTI art. 10 num. 1 y Reglamento LRTI art. 27 (Ecuador)"},
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
            req("RQ-006", "Maestro COMPLETO de partes relacionadas al corte (nombre, relación y período) y nota de revelación", None, "GAS-06",
                "Población de partes relacionadas: identificación, categorías de NIC 24 párr. 19 / Sección 33.10 y revelación",
                formats=("xlsx", "pdf", "docx"), use="soporte", required=True, content=maestro),
            req("RQ-007", "Presupuesto aprobado del ejercicio", None, "GAS-02", "Base de la expectativa", formats=("xlsx", "pdf"), use="soporte", required=False),
            req("RQ-008", "Manifestación escrita de la administración sobre partes relacionadas (o corte certificado del maestro)", None, "GAS-06",
                "Evidencia de que el maestro es la población completa; sin ella la integridad de la revelación no se concluye",
                formats=("pdf", "docx"), use="soporte", required=True,
                content=("Declaración firmada por la administración de que ha revelado al auditor la identidad de todas las partes relacionadas "
                         "de la entidad y todas las relaciones y transacciones con partes relacionadas de las que tiene conocimiento, y de que "
                         "las ha contabilizado y revelado conforme al marco aplicable (NIA 550 párr. 26). Alternativa: corte del maestro "
                         "certificado por la administración, con la fecha de corte y el responsable.")),
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
# Partes relacionadas registradas en el ejercicio: FC-111 9.000 (Dominante, en la nota), FC-114 3.000 (Personal clave, sin
# informar si está en la nota) y FC-115 1.200 (sin categoría, marcada como no incluida en la nota) = 13.200. La nota revela
# 10.000 (incluye una transacción fuera de la muestra) → 3.200 sin revelar. Con la manifestación escrita de la administración
# la integridad SÍ se concluye; el escenario «sin_evidencia_integridad» la deja vacía y la conclusión queda no concluida.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"_marco": MARCO_COMPLETAS, "metodoEri": "Función", "umbralVarPct": 10, "umbralVarAbs": 5000, "materialidadEjecucion": 20000,
                   "umbralBancarizacion": 500, "gastosSegunEri": 1005000, "rpRevelado": 10000,
                   "rpEvidenciaIntegridad": "MR-05 manifestación escrita de la administración del 15-01-2026 (NIA 550 párr. 26) y maestro de "
                                            "partes relacionadas certificado al 31-12-2025"},
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
               parte_relacionada="Sí", categoria_rp="Otra", revelada_rp="Sí"),
            _t("FC-107", "2025-11-01", "2025-11-03", "12000", "5301", "Radio Andina", servicio_desde="2025-11-01", servicio_hasta="2026-04-30"),
            _t("FC-108", "2025-09-10", "2025-09-12", "1500", "5202", "Juan Pérez", comprobante_valido="No", bancarizado="No"),
            _t("FC-109", "2025-10-05", "2025-10-06", "2500", "5301", "Publicistas XYZ", bancarizado="No"),
            _t("FC-110", "2025-08-20", "2025-08-21", "2200", "5201", "Taller Mecánico Ruta", cuenta_sugerida="5302"),
            _t("FC-111", "2025-05-10", "2025-05-11", "9000", "5202", "Holding Andes S.A.", parte_relacionada="Sí", categoria_rp="Dominante",
               revelada_rp="Sí"),
            _t("FC-112", "2025-04-02", "2025-04-03", "8000", "5601", "Constructora Rápida", inusual="Sí"),
            _t("FC-113", "2025-11-20", "2025-11-21", "22000", "5202", "Acuerdo judicial ex trabajador", inusual="Sí"),
            _t("FC-114", "2025-02-01", "2025-02-02", "3000", "5201", "Gerente General", parte_relacionada="Sí", categoria_rp="Personal clave", soporte=""),
            _t("FC-115", "2025-06-30", "2025-07-01", "1200", "5501", "Banco Relacionado S.A.", parte_relacionada="Sí", revelada_rp="No"),
        ],
    },
}

_P = EJEMPLO["parametros"]
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], _P, EJEMPLO["corte"]),
    ("sin_evidencia_integridad", EJEMPLO["datasets"], {**_P, "rpEvidenciaIntegridad": None}, EJEMPLO["corte"]),
    ("rp_revelacion_completa", {"cuentas": EJEMPLO["datasets"]["cuentas"],
                                "transacciones": [dict(x, revelada_rp="Sí") if x.get("parte_relacionada") == "Sí" else x
                                                  for x in EJEMPLO["datasets"]["transacciones"]]},
     {**_P, "rpRevelado": 13200}, EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**_P, "_marco": MARCO_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025_sin_opcionales", EJEMPLO["datasets"], {**_P, "_marco": MARCO_PYMES, "_edicion": "2025", "metodoEri": "Naturaleza",
                                                        "umbralVarAbs": None, "gastosSegunEri": None, "rpRevelado": None}, EJEMPLO["corte"]),
    ("sin_muestra", {"cuentas": EJEMPLO["datasets"]["cuentas"], "transacciones": []}, _P, EJEMPLO["corte"]),
]
