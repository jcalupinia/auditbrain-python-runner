# -*- coding: utf-8 -*-
"""RQ-004 — Lectura y clasificación de los mayores de nómina del cliente.
LM_GASTO: gasto de nómina por cuenta y centro de costo. LM_IESS: 5BS.21203 (columna REF del cliente).
LM_BS: 5BS.21204 (clasificación por concepto de la explicación). Signo: débito +, crédito −.

Refactor del script de referencia a ``cargar(rutas)``: antes leía rutas fijas en el
import; ahora el orquestador llama ``cargar(CTX)`` una vez y puebla los globales del
módulo, de modo que los generadores de referencia siguen usando ``MY.gasto_cta(...)``,
``MY.GKEY``, ``MY.ANEXO``, etc. sin cambiar su lógica.

LECTOR TOLERANTE AL FORMATO (2026-10-27): los mayores de distintos clientes/sistemas
no traen los mismos encabezados. ``_read_tabla`` detecta la fila de encabezados aunque
haya títulos/logos arriba y mapea por SINÓNIMOS las columnas a los nombres canónicos
que usa el resto del motor (``Fecha L/M``, ``Nºcuenta``, ``Descripción``, ``Importe``,
``Explicación -observación-``, ``REF``). Si el Mayor trae ``Debe``/``Haber`` en vez de un
``Importe`` con signo, calcula ``Importe = Debe − Haber``. Si no trae ``Explicación`` o
``REF`` (columnas de clasificación que no todos los mayores tienen), usa la ``Descripción``
como respaldo. Si falta una columna esencial (fecha, cuenta, descripción o importe), lanza
un mensaje CLARO en español en vez del ``KeyError: 'Fecha L/M'`` que confundía al usuario.

OJO — esto resuelve la LECTURA, no el PLAN DE CUENTAS: los cálculos siguen cableados a las
cuentas del encargo de referencia (``5BS.21203.*`` IESS por pagar, ``5BS.21204.*`` beneficios,
``5PYG``/``5D`` gastos). Un Mayor de otra empresa con otro plan de cuentas se LEERÁ bien, pero
los importes no cuadrarán hasta mapear también su plan de cuentas (trabajo aparte)."""
import re
import unicodedata

import pandas as pd

MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
GKEY = {'APO': 'Aporte Patronal', 'PAS': 'Aporte Patronal Pasantes', 'D13': 'Décimo Tercer Sueldo', 'D14': 'Décimo Cuarto Sueldo',
        'FR': 'Fondos de Reserva', 'VAC': 'Vacaciones', 'SUE': 'Sueldos', 'HE': 'Horas Extras', 'BON': 'Bono Desempeño',
        'COM': ('Comisiones', 'Comisiones a Empleado'), 'PRE': 'Premios', 'EST': 'Estipendio Pasantes', 'BFA': 'Bono Familiar'}
_norm = {'Decimo Tercer Sueldo': 'Décimo Tercer Sueldo', 'Decimo Cuarto Sueldo': 'Décimo Cuarto Sueldo'}

# globales que pueblan cargar() — los generadores los leen a través de este módulo
G = I = B = None
ANEXO: dict = {}


def _ncol(s) -> str:
    """Normaliza un nombre de columna para comparar: sin acentos, minúsculas, solo
    alfanumérico separado por espacios simples ('Nºcuenta' → 'n cuenta', 'Fecha L/M' → 'fecha l m')."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


# Sinónimos por campo canónico, en orden de prioridad (forma ya normalizada con _ncol).
# NB: 'saldo' NO es importe (es el saldo acumulado del mayor), por eso no está en 'importe'.
_SINONIMOS = {
    "fecha":   ["fecha l m", "fecha lm", "fecha asiento", "fecha del asiento", "fecha mayor",
                "fecha mov", "fecha movimiento", "fecha contable", "fecha"],
    "cuenta":  ["n cuenta", "no cuenta", "nro cuenta", "num cuenta", "numero de cuenta",
                "numero cuenta", "codigo de cuenta", "codigo cuenta", "cod cuenta", "codigo",
                "cuenta contable", "cuenta"],
    "desc":    ["descripcion", "descripcion del movimiento", "descripcion movimiento",
                "detalle", "concepto", "glosa"],
    "importe": ["importe", "importe movimiento", "valor", "monto", "valor movimiento"],
    "debe":    ["debe", "debito", "cargo"],
    "haber":   ["haber", "credito", "abono"],
    "ref":     ["ref", "referencia"],
    "expl":    ["explicacion observacion", "explicacion", "observacion", "nombre alfa explicacion"],
}


def _buscar(cols_norm, claves):
    """Índice de la primera columna que calce con alguna clave: primero por igualdad
    (en orden de prioridad), luego por 'contiene'. None si no hay."""
    for k in claves:
        for i, c in enumerate(cols_norm):
            if c == k:
                return i
    for k in claves:
        for i, c in enumerate(cols_norm):
            if k in c:
                return i
    return None


def _detectar_encabezado(crudo: pd.DataFrame) -> int:
    """Fila (0-based) que parece el encabezado: la primera (en las primeras 20) que tenga
    al menos fecha + cuenta + (descripción o importe/debe/haber). 0 si ninguna destaca."""
    for i in range(min(20, len(crudo))):
        cn = [_ncol(x) for x in crudo.iloc[i].tolist()]
        tiene_fecha = _buscar(cn, _SINONIMOS["fecha"]) is not None
        tiene_cta = _buscar(cn, _SINONIMOS["cuenta"]) is not None
        tiene_val = any(_buscar(cn, _SINONIMOS[k]) is not None for k in ("importe", "debe", "haber", "desc"))
        if tiene_fecha and tiene_cta and tiene_val:
            return i
    return 0


def _num(s: pd.Series) -> pd.Series:
    """Serie a número, tolerante a separadores regionales (1.234,56 ó 1,234.56)."""
    x = pd.to_numeric(s, errors="coerce")
    if x.notna().mean() >= 0.5:
        return x.fillna(0.0)
    t = s.astype(str).str.strip().str.replace(r"[^\d,.\-]", "", regex=True)
    # si tiene ambos separadores, el decimal es el último que aparece
    def _conv(v):
        if not v:
            return 0.0
        ult = max(v.rfind("."), v.rfind(","))
        if "." in v and "," in v:
            dec = v[ult]
            mil = "," if dec == "." else "."
            v = v.replace(mil, "").replace(dec, ".")
        elif "," in v:
            v = v.replace(",", ".") if len(v) - v.rfind(",") <= 3 else v.replace(",", "")
        try:
            return float(v)
        except ValueError:
            return 0.0
    return t.map(_conv).fillna(0.0)


def _read_tabla(path) -> pd.DataFrame:
    """Lee un Mayor de cualquier formato y devuelve un DataFrame con las columnas canónicas
    que espera el motor. Lanza ValueError con mensaje claro si falta una columna esencial."""
    crudo = pd.read_excel(path, header=None)
    h = _detectar_encabezado(crudo)
    df = crudo.iloc[h + 1:].copy()
    df.columns = list(crudo.iloc[h])
    cols_norm = [_ncol(c) for c in df.columns]

    i_fecha = _buscar(cols_norm, _SINONIMOS["fecha"])
    i_cta = _buscar(cols_norm, _SINONIMOS["cuenta"])
    i_desc = _buscar(cols_norm, _SINONIMOS["desc"])
    i_imp = _buscar(cols_norm, _SINONIMOS["importe"])
    i_debe = _buscar(cols_norm, _SINONIMOS["debe"])
    i_haber = _buscar(cols_norm, _SINONIMOS["haber"])
    i_ref = _buscar(cols_norm, _SINONIMOS["ref"])
    i_expl = _buscar(cols_norm, _SINONIMOS["expl"])

    faltan = []
    if i_fecha is None:
        faltan.append("fecha del asiento")
    if i_cta is None:
        faltan.append("número/código de cuenta")
    if i_desc is None:
        faltan.append("descripción")
    if i_imp is None and i_debe is None and i_haber is None:
        faltan.append("importe (o Debe/Haber)")
    if faltan:
        vistas = ", ".join(str(c) for c in df.columns if str(c) != "nan") or "(ninguna)"
        raise ValueError(
            "No reconozco las columnas del Mayor. Faltan: " + "; ".join(faltan) + ". "
            "Columnas encontradas: " + vistas + ". "
            "Verifique que el archivo sea un Mayor y que incluya su fila de encabezados."
        )

    # Se CONSERVAN todas las columnas originales (algún generador lee columnas extra como
    # 'Nombre alfa explicación') y solo se AGREGAN/renombran las canónicas que faltan.
    fecha = df.iloc[:, i_fecha].values
    cuenta = df.iloc[:, i_cta].values
    desc = df.iloc[:, i_desc].values
    if i_imp is not None:
        importe = _num(df.iloc[:, i_imp]).values
    else:  # Debe/Haber → Importe con signo (débito +, crédito −)
        debe = _num(df.iloc[:, i_debe]) if i_debe is not None else 0.0
        haber = _num(df.iloc[:, i_haber]) if i_haber is not None else 0.0
        importe = (debe - haber).values
    # Columnas de clasificación: opcionales. Si no están, la descripción hace de respaldo.
    expl = df.iloc[:, i_expl].values if i_expl is not None else desc
    ref = df.iloc[:, i_ref].astype(str).values if i_ref is not None else pd.Series(desc).astype(str).values
    df["Fecha L/M"] = fecha
    df["Nºcuenta"] = cuenta
    df["Descripción"] = desc
    df["Importe"] = importe
    df["Explicación -observación-"] = expl
    df["REF"] = ref
    # Descarta filas sin cuenta (totales/pies de página).
    df = df[df["Nºcuenta"].notna() & (df["Nºcuenta"].astype(str).str.strip() != "")]
    return df.reset_index(drop=True)


def _load(path):
    d = _read_tabla(path)
    d['m'] = pd.to_datetime(d['Fecha L/M'], errors='coerce', dayfirst=True).dt.month
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


def cuentas_por_concepto(key):
    """Cuentas de gasto de un concepto (reemplaza la lista que antes se leía del
    papel del equipo): [(cuenta, nombre, total)] ordenadas por código. El nombre
    sale del propio mayor y el total de ``gasto_cta``."""
    c = GKEY[key]; c = c if isinstance(c, tuple) else (c,)
    sub = G[G.concepto.isin(c)]
    out = []
    for cta in sorted(sub.cta.unique()):
        nombre = str(sub[sub.cta == cta].desc.iloc[0]).replace('MQLA ', '')
        out.append((cta, nombre, gasto_cta(cta)))
    return out
