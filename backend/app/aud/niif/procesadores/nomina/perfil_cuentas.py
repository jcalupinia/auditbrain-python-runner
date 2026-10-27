# -*- coding: utf-8 -*-
"""Adaptador de plan de cuentas para la herramienta de nómina (soporte multi-cliente).

El motor fue escrito para el plan de cuentas del encargo de referencia (IESS por pagar
``5BS.21203.*``, beneficios por pagar ``5BS.21204.*``, gastos por concepto). Otros clientes
usan otros códigos (p. ej. ``2.1.7.1.*`` / ``2.1.7.6.*`` pasivos, ``5.2.1.2.1.*`` gastos) y
pueden traer el pasivo en UN solo mayor.

Este módulo traduce los mayores de un cliente a la "forma" que el motor ya entiende,
clasificando CADA cuenta por el NOMBRE de la cuenta (no por su código), de modo que funciona
con distintos planes de cuentas sin cablear cada cliente. Lo que NO reconoce no se clasifica a
ciegas: queda en el reporte ``no_reconocidas`` para que el auditor lo revise.

Qué hace:
- Gasto: fija ``concepto`` por el nombre de la cuenta (→ textos de ``GKEY``), para que
  ``gasto_mes``/``gasto_cta`` del motor funcionen igual.
- Pasivo (un solo mayor): remapea el ``cta`` al código de referencia equivalente y fija
  ``clase`` desde la columna de referencia/observación del cliente
  (provisión/pagos/finiquitos/goces/saldo inicial). Se usa el MISMO df como I y B porque el
  motor filtra por código (``5BS.21203.*`` para IESS, ``5BS.21204.*`` para beneficios).

VERIFICACIÓN (regla de la casa): el mapeo se valida contra el propio anexo del cliente
(saldo anterior ± movimientos = saldo al corte). El desglose fino que el cliente no tagea
(p. ej. GOCES de vacaciones) queda para validación del socio, no se inventa.
"""
import re
import unicodedata

import pandas as pd


def _n(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


# Nombre de cuenta de GASTO → concepto del motor (texto de GKEY). Orden: específico primero;
# «sueldo» va al final porque es amplio (p. ej. «décimo tercer sueldo» no debe caer en Sueldos).
_GASTO = [
    (("aporte", "patronal"), "Aporte Patronal"),
    (("decimo", "tercer"), "Décimo Tercer Sueldo"),
    (("decimo", "cuarto"), "Décimo Cuarto Sueldo"),
    (("fondo", "reserva"), "Fondos de Reserva"),
    (("vacacion",), "Vacaciones"),
    (("comision",), "Comisiones"),
    (("hora", "extra"), "Horas Extras"),
    (("bono", "familiar"), "Bono Familiar"),
    (("premio",), "Premios"),
    (("estipendio",), "Estipendio Pasantes"),
    (("pasante",), "Estipendio Pasantes"),
    (("bono",), "Bono Desempeño"),
    (("sueldo",), "Sueldos"),
]

# Nombre de cuenta de PASIVO → código de referencia que usa el motor.
_PASIVO = [
    (("decimo", "tercer"), "5BS.21204.001"),
    (("decimo", "cuarto"), "5BS.21204.002"),
    (("vacacion",), "5BS.21204.003"),
    (("sueldo", "pagar"), "5BS.21204.004"),
    (("fondo", "reserva"), "5BS.21203.004"),
    (("quirografario",), "5BS.21203.003"),
    (("hipotecario",), "5BS.21203.005"),
    (("aporte",), "5BS.21203.001"),  # aportes por pagar (patronal + individual, el motor los suma)
]


def _match(nombre, reglas):
    t = _n(nombre)
    for claves, destino in reglas:
        if all(k in t for k in claves):
            return destino
    return None


def _clase(ref) -> str:
    """Categoría de movimiento del motor a partir de la referencia/observación del cliente."""
    r = _n(ref)
    if "provision" in r:
        return "PROVISION"
    if "finiquito" in r:
        return "FINIQUITOS"
    if "goce" in r or ("vac" in r and "tomad" in r):
        return "GOCES"
    if "pago" in r:
        return "PAGOS"
    if "inicial" in r:  # «saldo inicial»: la apertura la toma el motor del anexo, no del mayor
        return "SALDO_INICIAL"
    return "AJUSTES"  # «otros» o desconocido


def _col_nombre(df):
    """Columna con el NOMBRE de la cuenta (no el código ni la glosa del asiento)."""
    for c in df.columns:
        if _n(c) in ("cuenta", "cuenta contable", "nombre de cuenta", "nombre cuenta"):
            return c
    return None


def es_plan_de_referencia(df) -> bool:
    """¿El mayor ya viene en el plan de cuentas del motor (no hay que adaptar)?"""
    cta = df["cta"].astype(str) if "cta" in df.columns else df["Nºcuenta"].astype(str)
    return cta.str.startswith(("5BS.", "5PYG", "5D")).any()


def adaptar_gasto(G):
    """Fija ``concepto`` (y ``mqla``) en el mayor de gasto por el nombre de cada cuenta.
    Devuelve (G, no_reconocidas: list[(cta, nombre)])."""
    col = _col_nombre(G)
    G = G.copy()
    no_rec = []
    if col is None:  # sin columna de nombre no se puede clasificar por nombre
        G["concepto"] = G["desc"].astype(str)
        return G, [("(sin columna de nombre de cuenta)", "")]
    concepto, nombres = [], G[col].astype(str)
    for cta, nom in zip(G["cta"].astype(str), nombres):
        c = _match(nom, _GASTO)
        concepto.append(c if c is not None else nom)
        if c is None and str(nom).strip() and str(nom).lower() != "nan":
            no_rec.append((cta, nom))
    G["concepto"] = concepto
    G["mqla"] = False  # el prefijo 'MQLA' es del cliente de referencia; otros no lo usan
    # cuentas no reconocidas: únicas
    vistos, uniq = set(), []
    for cta, nom in no_rec:
        if cta not in vistos:
            vistos.add(cta); uniq.append((cta, nom))
    return G, uniq


def adaptar_pasivo(P):
    """Remapea el mayor de pasivo combinado al plan del motor y fija ``clase``.
    Devuelve (df_remapeado, no_reconocidas: list[(cta, nombre)])."""
    col = _col_nombre(P)
    P = P.copy()
    no_rec = []
    if col is None:
        raise ValueError("El Mayor de pasivo no trae una columna con el NOMBRE de la cuenta; "
                         "no se puede mapear por nombre.")
    nuevo_cta, nombres = [], P[col].astype(str)
    for cta, nom in zip(P["cta"].astype(str), nombres):
        dest = _match(nom, _PASIVO)
        if dest is None:
            no_rec.append((cta, nom)); nuevo_cta.append(cta)  # se deja tal cual (no se inventa)
        else:
            nuevo_cta.append(dest)
    P["cta"] = nuevo_cta
    P["Nºcuenta"] = nuevo_cta
    # clase desde la columna de referencia/observación del cliente
    ref_col = next((c for c in P.columns if _n(c) in ("referencia", "ref", "explicacion observacion", "observacion")), None)
    P["clase"] = (P[ref_col].map(_clase) if ref_col is not None else "AJUSTES")
    vistos, uniq = set(), []
    for cta, nom in no_rec:
        if cta not in vistos:
            vistos.add(cta); uniq.append((cta, nom))
    return P, uniq


def adaptar(G, P):
    """Adapta un cliente con mayor de gasto (G) y mayor de pasivo combinado (P) al plan del
    motor. Devuelve (G, I, B, no_reconocidas). I y B son el MISMO pasivo remapeado: el motor
    filtra por código (5BS.21203.* IESS, 5BS.21204.* beneficios)."""
    G2, nr_g = adaptar_gasto(G)
    P2, nr_p = adaptar_pasivo(P)
    I = P2.copy()
    B = P2.copy()
    B["concepto"] = B["clase"]  # compat: algún paso leía B.concepto; la clase ya está fijada
    return G2, I, B, {"gasto": nr_g, "pasivo": nr_p}
