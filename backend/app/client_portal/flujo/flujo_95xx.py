# backend/app/client_portal/flujo/flujo_95xx.py
"""Estado de Flujo de Efectivo — presentación oficial Super Cías (códigos 95xx).

Método DIRECTO (cobros/pagos) con la reconciliación por método indirecto
(96 + 9801..9820), tal como lo exige el formulario de la Superintendencia de
Compañías del Ecuador. Reproduce, celda por celda, la hoja "Estado de Flujo"
del modelo Excel del cliente (validado 48/48 contra el archivo SIGMAN oficial).

A diferencia del ``motor_flujo`` (método indirecto, papel de trabajo interno),
este módulo genera la presentación reglamentaria que se descarga a TXT/Excel.

Arquitectura
------------
La hoja "Estado de Flujo" del modelo referencia cinco hojas:
  * ``Estado de Situacion Financiera`` (ESF): papel de trabajo con columnas
    D=saldo anterior, E=saldo actual, I=usos, J=fuentes, L..V=actividades de
    operación, Y=inversión, W/AA=totales. Los saldos salen de un ``SUMIF`` por
    código EXACTO (sin rollup jerárquico) sobre la balanza.
  * ``Estado de Resultados Integral`` (ERI): valores del ERI por código, con los
    subtotales de la cascada (ganancia bruta, utilidad operativa, etc.).
  * ``Movimiento no Efectivo`` (MNE): activo fijo (adiciones/depreciación),
    provisiones, impuesto renta, participación trabajadores, jubilación patronal.
    Se reproduce evaluando las fórmulas propias del MNE (referencian ESF/ERI).
  * ``Estado de Evolucion del Patrimonio``: la matriz oficial 99xx
    (``patrimonio_matriz``), para los movimientos de patrimonio del financiamiento.
  * la propia hoja (auto-referencias ``D{fila}`` y ``SUM(D..:D..)``).

La estructura de las cinco hojas (mapa fila→código, fórmulas, membresía de
columnas de actividad) se extrajo una sola vez del modelo a
``flujo_95xx_estructura.json``. Este módulo la carga y evalúa las fórmulas con
los saldos calculados en runtime desde la balanza — sin depender del Excel.

Regla contable clave (patrimonio): la variación cruda de las cuentas de
patrimonio incluye la reclasificación del resultado del ejercicio (movimiento
NO monetario). El papel de trabajo la excluye: la cuenta de Otros Resultados
Integrales (30601) usa solo el ORI del período; el resto del patrimonio se
maneja vía la matriz 99xx en el financiamiento.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache

from . import motor, motor_er, motor_f101, patrimonio_matriz, catalogos

_ESTRUCTURA_PATH = os.path.join(os.path.dirname(__file__), "flujo_95xx_estructura.json")

# Mapa columna del Estado de Evolución del Patrimonio -> código de componente 30x
_EP_COMPONENTE = {
    "C": "301", "D": "302", "E": "303", "F": "30401", "G": "30402",
    "H": "30501", "I": "30502", "J": "30503", "K": "30504",
    "L": "30601", "M": "30602", "N": "30603", "O": "30604", "P": "30605",
    "Q": "30606", "R": "30607", "S": "30701", "T": "30702",
}


@lru_cache(maxsize=1)
def _estructura() -> dict:
    with open(_ESTRUCTURA_PATH, encoding="utf-8") as fh:
        d = json.load(fh)
    # JSON convierte las claves int en str; normalizamos a int los mapas por fila
    return {
        "flujo": d["flujo"],
        "esf_cod": {int(k): v for k, v in d["esf_cod"].items()},
        "esf_actf": {int(k): v for k, v in d["esf_actf"].items()},
        "esf_dform": {int(k): v for k, v in d.get("esf_dform", {}).items()},
        "esf_eform": {int(k): v for k, v in d.get("esf_eform", {}).items()},
        "esf_sumrows": d["esf_sumrows"],
        "eri_cod": {int(k): v for k, v in d["eri_cod"].items()},
        "mne": {int(k): v for k, v in d["mne"].items()},
        "ep_cod": {int(k): v for k, v in d["ep_cod"].items()},
    }


def _r2(x) -> float:
    return round((x or 0.0) * 100) / 100


def _mapa_exacto(balanza: list[dict]) -> dict[str, float]:
    """Saldo por código EXACTO (réplica del SUMIF del modelo, sin rollup)."""
    m: dict[str, float] = {}
    for e in balanza:
        cod = str(e.get("super_cias") or "").replace(".", "").strip()
        if cod:
            m[cod] = m.get(cod, 0.0) + (e.get("saldo") or 0.0)
    return m


def calcular_flujo_95xx(bal_ant: list[dict], bal_act: list[dict]) -> dict:
    """Devuelve la presentación oficial del flujo de efectivo (códigos 95xx).

    ``{"lineas": [{"codigo","etiqueta","valor"}...],
       "totales": {"95":..,"9501":..,"9502":..,"9503":..,"9506":..,"9507":..}}``
    """
    est = _estructura()
    EA = _mapa_exacto(bal_ant)
    EC = _mapa_exacto(bal_act)

    # ERI (con rollup, como los demás motores) + cascada + ORI + matriz 99xx
    E_eri = catalogos.cargar_estructura("eri")
    sc, _ = motor.homologar_balanza(bal_act)
    teri = motor.totales_por_codigo(E_eri, sc)
    casc = motor_er.cascada_resultados(teri)
    ori = motor_f101.ori_del_periodo(bal_ant, bal_act)
    mat = patrimonio_matriz.matriz_patrimonio(bal_ant, bal_act)
    matD = {f["codigo"]: f["celdas"] for f in mat["filas"]}

    eri_sub = {
        "402": casc["ganancia_bruta"], "600": casc["utilidad_operativa"],
        "602": casc["utilidad_antes_ir"], "604": casc["utilidad_operaciones"],
        "607": casc["utilidad_neta"], "707": casc["utilidad_neta"],
        "800": ori, "80005": ori,
    }

    esf_cod = est["esf_cod"]
    esf_actf = est["esf_actf"]
    esf_dform = est["esf_dform"]
    esf_eform = est["esf_eform"]
    esf_sumrows = est["esf_sumrows"]
    eri_cod = est["eri_cod"]
    mne_form = est["mne"]
    ep_cod = est["ep_cod"]

    def sD(cod):  # saldo anterior por código exacto
        return _r2(EA.get(cod, 0.0))

    def sE(cod):  # saldo actual por código exacto
        return _r2(EC.get(cod, 0.0))

    def var_wp(cod):
        # Patrimonio: excluir la reclasificación del resultado (no monetaria).
        if cod == "30601":
            return _r2(ori)          # Otros Resultados Integrales = solo ORI
        if cod and cod[:1] == "3":
            return 0.0               # resto del patrimonio va por la matriz 99xx
        return _r2(sE(cod) - sD(cod))

    _esf_memo: dict[tuple, float] = {}

    def _esf_subtotal(col, fila, formula):
        """Evalúa una fila subtotal del ESF (=SUM(D..:D..) o =D..+D..) que
        referencia otras celdas D/E de la misma hoja, recursivamente."""
        e = formula[1:]
        e = re.sub(r"SUM\(([DE])(\d+):([DE])(\d+)\)",
                   lambda m: "(%r)" % _r2(sum(esf_cell(m.group(1), rr)
                                              for rr in range(int(m.group(2)), int(m.group(4)) + 1))), e)
        e = re.sub(r"(?<![A-Za-z0-9_])([DE])(\d+)",
                   lambda m: "(%r)" % esf_cell(m.group(1), int(m.group(2))), e)
        if not re.match(r"^[\d\.\+\-\*\/\(\)eE ,]*$", e):
            return 0.0
        try:
            return _r2(eval(e))  # noqa: S307 — expresión saneada a solo números
        except Exception:
            return 0.0

    def esf_cell(col, fila):
        cod = esf_cod.get(fila)
        if col == "D":
            sub = esf_dform.get(fila)          # fila subtotal: suma sus hijas
            if sub is not None:
                key = ("D", fila)
                if key not in _esf_memo:
                    _esf_memo[key] = 0.0
                    _esf_memo[key] = _esf_subtotal("D", fila, sub)
                return _esf_memo[key]
            return sD(cod) if cod else 0.0
        if col == "E":
            sub = esf_eform.get(fila)
            if sub is not None:
                key = ("E", fila)
                if key not in _esf_memo:
                    _esf_memo[key] = 0.0
                    _esf_memo[key] = _esf_subtotal("E", fila, sub)
                return _esf_memo[key]
            return sE(cod) if cod else 0.0
        if cod is None:
            return 0.0
        v = var_wp(cod)
        if col == "I":                       # usos
            return v if v > 0 else 0.0
        if col == "J":                       # fuentes
            return -v if v < 0 else 0.0
        # columnas de actividad (operación/inversión/financiamiento): -variación,
        # solo si la celda tiene fórmula en el modelo (las vacías valen 0).
        if col in esf_actf.get(fila, ()):
            return -v
        return 0.0

    def esf_ref(col, fila):
        key = "%s%d" % (col, fila)
        rng = esf_sumrows.get(key)
        if rng:                              # celda total: SUM(col{r1}:col{r2})
            c, r1, r2 = rng
            return _r2(sum(esf_cell(c, rr) for rr in range(r1, r2 + 1)))
        return esf_cell(col, fila)

    def eri_ref(col, fila):
        cod = eri_cod.get(fila)
        if cod in eri_sub:
            return _r2(eri_sub[cod])
        return _r2(teri.get(cod, 0.0)) if cod else 0.0

    _mne_memo: dict[int, float] = {}

    def mne_ref(col, fila):
        if col != "C":
            return 0.0
        if fila in _mne_memo:
            return _mne_memo[fila]
        _mne_memo[fila] = 0.0
        spec = mne_form.get(fila)
        if spec is None:
            return 0.0
        if isinstance(spec, dict):           # valor fijo
            _mne_memo[fila] = _r2(spec.get("fijo", 0.0))
            return _mne_memo[fila]
        _mne_memo[fila] = _eval_formula(spec, esf_ref, eri_ref, mne_ref, ep_ref, None)
        return _mne_memo[fila]

    def ep_ref(col, fila):
        mov = ep_cod.get(fila)
        comp = _EP_COMPONENTE.get(col)
        if mov in matD and comp:
            return _r2(matD[mov].get(comp, 0.0))
        return 0.0

    # --- resolvedor recursivo de la propia hoja de flujo ---
    flujo_por_fila = {ln["row"]: ln for ln in est["flujo"]}
    _flujo_memo: dict[int, float] = {}

    def flujo_D(fila):
        if fila in _flujo_memo:
            return _flujo_memo[fila]
        _flujo_memo[fila] = 0.0
        ln = flujo_por_fila.get(fila)
        if ln is None:
            return 0.0
        if not ln.get("formula"):
            vf = ln.get("valor_fijo")
            _flujo_memo[fila] = _r2(vf) if isinstance(vf, (int, float)) else 0.0
            return _flujo_memo[fila]
        _flujo_memo[fila] = _eval_formula(
            ln["formula"], esf_ref, eri_ref, mne_ref, ep_ref, flujo_D)
        return _flujo_memo[fila]

    # calcular todas las líneas 95xx
    lineas = []
    totales = {}
    for ln in est["flujo"]:
        cod = ln.get("codigo")
        if not cod or not cod.startswith(("95", "96", "98")):
            continue
        val = flujo_D(ln["row"])
        lineas.append({"codigo": cod, "etiqueta": ln.get("etiqueta", ""), "valor": val})
        if cod in ("95", "9501", "9502", "9503", "9505", "9506", "9507"):
            totales[cod] = val

    return {"lineas": lineas, "totales": totales}


def _eval_formula(formula, esf_ref, eri_ref, mne_ref, ep_ref, flujo_D):
    """Evalúa una fórmula del modelo sustituyendo cada referencia por su valor.

    Maneja las cinco hojas + rangos SUM + auto-referencias del flujo. ``flujo_D``
    puede ser None cuando se evalúan fórmulas del MNE (que no se auto-refieren al
    flujo). Nunca ejecuta código arbitrario: solo aritmética con números.
    """
    e = formula[1:]

    def _sum_eri(m):
        c, r1, r2 = m.group(1), int(m.group(2)), int(m.group(4))
        return "(%r)" % _r2(sum(eri_ref(c, rr) for rr in range(r1, r2 + 1)))

    def _sum_esf(m):
        c, r1, r2 = m.group(1), int(m.group(2)), int(m.group(4))
        return "(%r)" % _r2(sum(esf_ref(c, rr) for rr in range(r1, r2 + 1)))

    e = re.sub(r"SUM\('Estado de Resultados Integral'!([A-Z]+)(\d+):([A-Z]+)(\d+)\)", _sum_eri, e)
    e = re.sub(r"SUM\('Estado de Situacion Financiera'!([A-Z]+)(\d+):([A-Z]+)(\d+)\)", _sum_esf, e)
    # IF(MNE!Cx>0, MNE!Cx, 0) — adiciones netas (solo si son positivas)
    e = re.sub(
        r"IF\('Movimiento no Efectivo'!([A-Z]+)(\d+)>0,'Movimiento no Efectivo'!([A-Z]+)(\d+),0\)",
        lambda m: "(%r)" % (mne_ref(m.group(1), int(m.group(2)))
                            if mne_ref(m.group(1), int(m.group(2))) > 0 else 0.0),
        e)
    e = re.sub(r"'Movimiento no Efectivo'!([A-Z]+)(\d+)",
               lambda m: "(%r)" % mne_ref(m.group(1), int(m.group(2))), e)
    e = re.sub(r"'Estado de Evolucion del Patrimo'!([A-Z]+)(\d+)",
               lambda m: "(%r)" % ep_ref(m.group(1), int(m.group(2))), e)
    e = re.sub(r"'Estado de Resultados Integral'!([A-Z]+)(\d+)",
               lambda m: "(%r)" % eri_ref(m.group(1), int(m.group(2))), e)
    e = re.sub(r"'Estado de Situacion Financiera'!([A-Z]+)(\d+)",
               lambda m: "(%r)" % esf_ref(m.group(1), int(m.group(2))), e)
    if flujo_D is not None:
        e = re.sub(r"SUM\(D(\d+):D(\d+)\)",
                   lambda m: "(%r)" % _r2(sum(flujo_D(rr) for rr in range(int(m.group(1)), int(m.group(2)) + 1))), e)
        e = re.sub(r"'?Estado de Flujo ?'?!?D(\d+)",
                   lambda m: "(%r)" % flujo_D(int(m.group(1))), e)
        e = re.sub(r"(?<![A-Za-z0-9_'!.])D(\d+)",
                   lambda m: "(%r)" % flujo_D(int(m.group(1))), e)
    else:
        # Contexto MNE: las auto-referencias son celdas C{fila} desnudas de la
        # propia hoja Movimiento no Efectivo. Manejar rangos SUM(C..:C..) antes
        # que las celdas sueltas (ej. filas SALDO FINAL = SUM(Cx:Cy)).
        e = re.sub(r"SUM\(C(\d+):C(\d+)\)",
                   lambda m: "(%r)" % _r2(sum(mne_ref("C", rr)
                                              for rr in range(int(m.group(1)), int(m.group(2)) + 1))), e)
        e = re.sub(r"(?<![A-Za-z0-9_'!.])C(\d+)",
                   lambda m: "(%r)" % mne_ref("C", int(m.group(1))), e)
    # Guarda de seguridad: solo aritmética con números.
    if not re.match(r"^[\d\.\+\-\*\/\(\)eE ,]*$", e):
        return 0.0
    try:
        return _r2(eval(e))  # noqa: S307 — expresión saneada a solo números/operadores
    except Exception:
        return 0.0
