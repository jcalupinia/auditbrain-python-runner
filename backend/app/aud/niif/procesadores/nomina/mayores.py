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
import os
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
        v = str(v).strip()
        if v in ("", "nan", "NaN", "None", "-"):
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


# Plan de cuentas del encargo de referencia que ESPERAN los cálculos del motor. No es
# configurable por cliente todavía: los generadores clavan estas cuentas (ver módulos mk_*).
# Mientras no exista la calibración por cliente (Capa 2), si el Mayor cargado no trae estas
# cuentas, la herramienta AVISA en vez de entregar cédulas en cero como si estuvieran bien.
CUENTA_IESS_POR_PAGAR = "5BS.21203"
CUENTA_BENEFICIOS_POR_PAGAR = "5BS.21204"


def _tiene_cuenta(df, prefijo) -> bool:
    return df is not None and not df.empty and df["cta"].astype(str).str.startswith(prefijo).any()


def _plan_de_cuentas_coincide(iess, bs) -> bool:
    """¿Los mayores de pasivo traen las cuentas que el motor espera? Es el discriminador más
    fiable de que el Mayor es del encargo de referencia y no de otro cliente/plan de cuentas."""
    return _tiene_cuenta(iess, CUENTA_IESS_POR_PAGAR) and _tiene_cuenta(bs, CUENTA_BENEFICIOS_POR_PAGAR)


# Cuentas no reconocidas por el adaptador en el último `cargar` (para el reporte al auditor).
CUENTAS_NO_RECONOCIDAS: dict = {}


def _normalizar_rol(rutas, perfil_cuentas):
    """Asegura que ``rutas.rol`` tenga la hoja «normal» que lee el motor, en cualquiera de las dos
    ramas de ``cargar`` (el formato del rol no depende del plan de cuentas de los mayores).

    - Varios roles mensuales (``rutas.roles_mensuales`` con >1 archivo) → se combinan en uno (una
      fila por empleado y mes); el mes sale del nombre del archivo.
    - Un solo rol que YA trae «normal» (p. ej. el del encargo de referencia) → se deja intacto.
    - Un solo rol SIN «normal» (otra estructura del cliente) → se reescribe (mapea por sección +
      nombre, genérico). Vacaciones gozadas y finiquitos quedan en 0 (pendientes del socio, M23).
    Nunca lanza: si no se puede inspeccionar/reescribir, deja el rol como estaba y el motor avisará.
    """
    roles = list(getattr(rutas, "roles_mensuales", None) or [])
    if len(roles) > 1:
        items = [(ruta, perfil_cuentas.mes_de_nombre(nom)) for ruta, nom in roles]
        rutas.rol = perfil_cuentas.reescribir_roles(
            items, os.path.join(rutas.home, "rol_adaptado.xlsx"))
        return
    if rutas.rol and os.path.exists(rutas.rol):
        import openpyxl
        try:
            tiene_normal = "normal" in openpyxl.load_workbook(rutas.rol, read_only=True).sheetnames
        except Exception:
            # Si no se puede ni inspeccionar el archivo, se deja como estaba y el motor avisará.
            return
        if not tiene_normal:
            # Rol en otra estructura (sin hoja «normal»): se reescribe al layout del motor. Si NO se
            # puede reconocer (p. ej. faltan columnas de empleado/sueldo), se PROPAGA el motivo claro
            # ("No reconozco el rol…") en vez de tragarlo con un «except: pass» y dejar que el motor
            # reviente después con el críptico «Worksheet normal does not exist».
            mes = perfil_cuentas.mes_de_nombre(os.path.basename(rutas.rol))
            rutas.rol = perfil_cuentas.reescribir_rol(
                rutas.rol, os.path.join(rutas.home, "rol_adaptado.xlsx"), mes=mes)


def cargar(rutas):
    """Carga los tres mayores y el anexo desde las rutas de la prueba y puebla los globales.

    Dos caminos:
    - Plan de REFERENCIA: tres mayores (gasto, IESS, beneficios) ya en 5BS.*/5PYG.
    - OTRO CLIENTE: mayor de gasto + UN mayor de pasivo combinado (`lm_pasivo`); se adapta al
      plan del motor con ``perfil_cuentas`` (clasificando por nombre de cuenta)."""
    global G, I, B, ANEXO, CUENTAS_NO_RECONOCIDAS
    from backend.app.aud.niif.procesadores.nomina import perfil_cuentas
    CUENTAS_NO_RECONOCIDAS = {}

    if rutas.lm_pasivo and os.path.exists(rutas.lm_pasivo):
        # --- Cliente con pasivo combinado: adaptar al plan del motor -------------------
        if not rutas.lm_gasto or not os.path.exists(rutas.lm_gasto):
            raise ValueError("Falta el Mayor de gastos (RQ-004). Cargue el mayor de gastos junto "
                             "con el mayor de pasivo.")
        G = _load(rutas.lm_gasto)
        P = _load(rutas.lm_pasivo)
        G, I, B, CUENTAS_NO_RECONOCIDAS = perfil_cuentas.adaptar(G, P)
        if not _plan_de_cuentas_coincide(I, B):
            raise ValueError(
                "No pude mapear el plan de cuentas del Mayor de pasivo a las cuentas del motor "
                "(IESS por pagar / beneficios por pagar). Revise que el mayor traiga la columna "
                "con el NOMBRE de cada cuenta (Aportes por pagar, Décimo tercero por pagar, "
                "Vacaciones por pagar, etc.).")
        # Adapta el anexo (RQ-002) al layout/códigos de referencia que esperan los ~10 lectores
        # del motor (remapea solo los códigos de pasivo; los de gasto ya empiezan por «5»). Se
        # apunta rutas.anexo (== CTX.anexo) al archivo reescrito para que todas las cédulas lo lean.
        if rutas.anexo and os.path.exists(rutas.anexo):
            rutas.anexo = perfil_cuentas.reescribir_anexo(
                rutas.anexo, os.path.join(rutas.home, "anexo_adaptado.xlsx"))
        # Adapta el Consolidado IESS (RQ-003) al formato del motor (hoja detallePlanillaConsolidado,
        # campos corridos a col B) cuando el cliente trae el export estándar del IESS en una sola hoja.
        if rutas.consolidado and os.path.exists(rutas.consolidado):
            try:
                import openpyxl
                if "detallePlanillaConsolidado" not in openpyxl.load_workbook(
                        rutas.consolidado, read_only=True).sheetnames:
                    rutas.consolidado = perfil_cuentas.reescribir_consolidado(
                        rutas.consolidado, os.path.join(rutas.home, "consolidado_adaptado.xlsx"))
            except Exception:
                pass  # si no se puede inspeccionar, se deja como está (el motor avisará)
        # Cliente con plan de cuentas distinto: mayores + anexo + consolidado ya se adaptan al
        # formato del motor (el rol se normaliza más abajo, como paso común a las dos ramas). Las
        # cédulas se generan como PRELIMINARES, pendientes de validación del socio (M23);
        # vacaciones gozadas y finiquitos quedan en 0 (el cliente no los separa).
    else:
        # --- Plan de referencia: tres mayores -----------------------------------------
        _faltan = [n for n, p in (("gastos", rutas.lm_gasto), ("IESS por pagar", rutas.lm_iess),
                                  ("beneficios por pagar", rutas.lm_bs)) if not p or not os.path.exists(p)]
        if _faltan:
            raise ValueError(
                "Falta el Mayor de " + ", ".join(_faltan) + " (RQ-004). Cargue los mayores y "
                "asegúrese de que el nombre de cada archivo identifique cuál es "
                "(que contenga «GASTO», «IESS», «BENEFICIOS» o «PASIVO» para el pasivo combinado).")
        G = _load(rutas.lm_gasto)
        I = _load(rutas.lm_iess)
        B = _load(rutas.lm_bs)
        if not _plan_de_cuentas_coincide(I, B):
            raise ValueError(
                "Esta herramienta está calibrada para el plan de cuentas del encargo de referencia "
                f"(IESS por pagar {CUENTA_IESS_POR_PAGAR}.*, beneficios por pagar "
                f"{CUENTA_BENEFICIOS_POR_PAGAR}.*, gastos 5PYG/5D). El Mayor cargado no contiene esas "
                "cuentas: si es otro cliente con el pasivo en un solo mayor, nombre ese archivo con "
                "«PASIVO» para que se adapte automáticamente; si no, hay que calibrar su plan de "
                "cuentas (contacte a AuditConsulting).")
        G['concepto'] = G['desc'].str.replace('MQLA ', '', regex=False).map(lambda x: _norm.get(x, x))
        G['mqla'] = G['desc'].str.startswith('MQLA')
        B['concepto'] = B['Explicación -observación-'].astype(str).str.split('/').str[0].str.strip()
        B['clase'] = B.concepto.map(_cat_bs)
        I['clase'] = I['REF'].astype(str).str.strip().str.upper()
    # Normaliza el Rol (RQ-006) a la hoja «normal» de 67 columnas que leen el motor y los
    # generadores (motor.py, series.py, mk_do4/31/9, cedulas_nuevas). Es un paso COMÚN a las dos
    # ramas: el formato del rol es independiente del plan de cuentas de los mayores (un cliente con
    # mayores del plan de referencia puede traer el rol en otra estructura). Si el rol ya trae la
    # hoja «normal», no se toca; si no, se reescribe (mapea por sección + nombre, genérico), y varios
    # roles mensuales se combinan en uno. Sin este paso, un rol sin «normal» reventaba el motor con
    # «Worksheet normal does not exist» en la rama del plan de referencia.
    _normalizar_rol(rutas, perfil_cuentas)
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
