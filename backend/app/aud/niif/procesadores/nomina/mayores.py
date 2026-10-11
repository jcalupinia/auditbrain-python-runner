# -*- coding: utf-8 -*-
"""RQ-004 — Lectura y clasificación de los mayores de nómina del cliente.
LM_GASTO: gasto de nómina por cuenta y centro de costo. LM_IESS: 5BS.21203 (columna REF del cliente).
LM_BS: 5BS.21204 (clasificación por concepto de la explicación). Signo: débito +, crédito −.

Refactor del script de referencia a ``cargar(rutas)``: antes leía rutas fijas en el
import; ahora el orquestador llama ``cargar(CTX)`` una vez y puebla los globales del
módulo, de modo que los generadores de referencia siguen usando ``MY.gasto_cta(...)``,
``MY.GKEY``, ``MY.ANEXO``, etc. sin cambiar su lógica."""
import pandas as pd

MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
GKEY = {'APO': 'Aporte Patronal', 'PAS': 'Aporte Patronal Pasantes', 'D13': 'Décimo Tercer Sueldo', 'D14': 'Décimo Cuarto Sueldo',
        'FR': 'Fondos de Reserva', 'VAC': 'Vacaciones', 'SUE': 'Sueldos', 'HE': 'Horas Extras', 'BON': 'Bono Desempeño',
        'COM': ('Comisiones', 'Comisiones a Empleado'), 'PRE': 'Premios', 'EST': 'Estipendio Pasantes', 'BFA': 'Bono Familiar'}
_norm = {'Decimo Tercer Sueldo': 'Décimo Tercer Sueldo', 'Decimo Cuarto Sueldo': 'Décimo Cuarto Sueldo'}

# globales que pueblan cargar() — los generadores los leen a través de este módulo
G = I = B = None
ANEXO: dict = {}


def _load(path):
    d = pd.read_excel(path)
    d['m'] = pd.to_datetime(d['Fecha L/M']).dt.month
    d['cta'] = d['Nºcuenta'].astype(str).str.strip()
    d['desc'] = d['Descripción'].astype(str).str.strip()
    return d


def _cat_bs(c):
    if c in ('DECIMO 13', 'DECIMO 14 S', 'VACACIONES'): return 'PROVISION'
    if c.startswith('LIQ') or c == 'VAC.FINIQUIT': return 'FINIQUITOS'
    if c == 'VAC TOMADAS': return 'GOCES'
    if c.startswith(('TRANSF', 'PGO', 'PAGO')): return 'PAGOS'
    return 'AJUSTES'


def cargar(rutas):
    """Carga los tres mayores y el anexo desde las rutas de la prueba y puebla los globales."""
    global G, I, B, ANEXO
    G = _load(rutas.lm_gasto)
    I = _load(rutas.lm_iess)
    B = _load(rutas.lm_bs)
    G['concepto'] = G['desc'].str.replace('MQLA ', '', regex=False).map(lambda x: _norm.get(x, x))
    G['mqla'] = G['desc'].str.startswith('MQLA')
    B['concepto'] = B['Explicación -observación-'].astype(str).str.split('/').str[0].str.strip()
    B['clase'] = B.concepto.map(_cat_bs)
    I['clase'] = I['REF'].astype(str).str.strip().str.upper()
    ANEXO = {}
    for r in pd.read_excel(rutas.anexo, header=None).iloc[3:].itertuples(index=False):
        if isinstance(r[0], str) and r[0][:1] == '5':
            ANEXO[r[0].strip()] = (float(r[2]) if pd.notna(r[2]) else 0.0, float(r[5]) if pd.notna(r[5]) else 0.0)
    return G, I, B, ANEXO


def gasto_mes(key, incl_mqla=True):
    c = GKEY[key]; c = c if isinstance(c, tuple) else (c,)
    s = G[G.concepto.isin(c) & (incl_mqla | ~G.mqla)].groupby('m').Importe.sum()
    return [round(float(s.get(m, 0)), 2) for m in range(1, 13)]


def gasto_cta(cta):
    return round(float(G[G.cta == cta].Importe.sum()), 2)


def pasivo_mes(df, cta, cat):
    s = df[(df.cta == cta) & (df.clase == cat)].groupby('m').Importe.sum()
    return [round(float(s.get(m, 0)), 2) for m in range(1, 13)]


def pasivo_tot(df, cta, cat):
    return round(float(df[(df.cta == cta) & (df.clase == cat)].Importe.sum()), 2)
