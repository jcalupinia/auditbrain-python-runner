"""Parser de BALANCES INTERNOS (estados financieros internos en Excel).

Lee un libro Excel (.xls / .xlsx) con el plan de cuentas de la Superintendencia
de Compañías del Ecuador (NIIF) y extrae los estados financieros a las claves
del modelo (ESF/ER) que alimentan el dashboard.

Características:
- **Separador-agnóstico**: códigos con puntos (1.1.01) o guiones (1-1-1) — se
  reconocen automáticamente; los segmentos de relleno (espacios) se ignoran.
- **Multi-bloque**: una sola hoja puede contener el Balance y el Estado de
  Resultados apilados, CADA UNO con su propio encabezado y sus propias fechas
  de corte (ej. ESF 31-12-2024 vs 30-09-2025; ER 30-09-2024 vs 30-09-2025).
- **Etiquetas independientes**: devuelve `labels_esf` y `labels_er` (fechas
  reales) para que el dashboard compare cada estado en su propio rango.

Pasivo y patrimonio vienen con signo negativo (saldo crédito): se toma valor
absoluto. Para GARANTIZAR la cuadratura A = Pasivo + Patrimonio se usan los
totales de las cuentas 1/2/3 y el residual no clasificado se asigna a una cuenta
"Otras" de cada sección. La utilidad neta = Ingresos − Egresos (resultado del
libro), que coincide con el resultado del ejercicio del patrimonio.
"""

from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime, date

import pandas as pd

INPUT_KEYS = [
    "efectivo", "inversiones", "cxc", "cxcRel", "impRec", "otrasCxc", "inventario",
    "ppe", "actImpDif", "cxcLP", "otrosActNoCorr", "anticiposProv",
    "cxp", "oblBanc", "impPagar", "benef", "anticipos", "provisiones", "otrasCxp",
    "cxpRelCorr", "benefPost", "cxpRel", "pasImpDif", "prestamosLP",
    "capital", "reservas", "ori", "resAcum",
    "ventas", "otrosIng", "otrosIngFin", "costo", "gAdmin", "gFin",
    "partTrab", "irCausado", "impDif",
]
_MESES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.upper().strip()


def _num(x) -> float:
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return 0.0
        return float(x)
    except (ValueError, TypeError):
        return 0.0


def _segs(code) -> list[str]:
    """Segmentos del código, agnóstico al separador (punto o guion)."""
    return [p.strip() for p in re.split(r"[-.]", str(code)) if p.strip() != ""]


def _read_excel(data: bytes) -> pd.ExcelFile:
    engine = "xlrd" if data[:4] == b"\xd0\xcf\x11\xe0" else "openpyxl"
    return pd.ExcelFile(io.BytesIO(data), engine=engine)


def _period_label(cell):
    """Devuelve (label, year) si la celda es una fecha o contiene un año, o None."""
    if isinstance(cell, (datetime, date, pd.Timestamp)):
        d = pd.Timestamp(cell)
        return (f"{d.day:02d}-{_MESES[d.month]}-{d.year}", d.year)
    s = str(cell)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)  # ISO yyyy-mm-dd
    if m:
        y, mo, da = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return (f"{da:02d}-{_MESES[mo]}-{y}", y)
    m = re.search(r"(\d{2})[/-](\d{2})[/-](\d{4})", s)  # dd-mm-yyyy
    if m:
        da, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return (f"{da:02d}-{_MESES[mo]}-{y}", y)
    m = re.search(r"\b(19|20)\d{2}\b", s)  # solo año
    if m:
        y = int(m.group(0))
        return (str(y), y)
    return None


def _detect_periods(row) -> list[tuple[int, str, int]]:
    out = []
    for i, v in enumerate(row.tolist()):
        lab = _period_label(v)
        if lab:
            out.append((i, lab[0], lab[1]))
    return out


# Palabras clave de los GRUPOS de cuentas (para reconocer por nombre, no solo
# por el código). Permite parsear planes de cuentas con numeración no estándar.
_BAL_KW = ("ACTIVO", "PASIVO", "PATRIMONIO")
_RES_KW = ("INGRESO", "VENTA", "COSTO", "GASTO", "EGRESO", "PERDIDA", "GANANCIA")


def _section_by_name(name: str) -> str | None:
    n = _norm(name)
    if any(k in n for k in _BAL_KW):
        return "bal"
    if any(k in n for k in _RES_KW):
        return "res"
    return None


def _first_account_section(df, start):
    """Sección del bloque que sigue a `start`. Devuelve (kind, coded) o (None, _).

    Prioriza el CÓDIGO (1/2/3 = balance, 4/5/6 = resultados; coded=True). Si en
    la ventana no hay cuentas codificadas, recurre al NOMBRE del grupo
    (ACTIVO/PASIVO/… o INGRESO/COSTO/GASTO; coded=False) para soportar planes de
    cuentas con numeración no estándar.
    """
    name_kind = None
    for j in range(start, min(start + 8, len(df))):
        segs = _segs(df.iloc[j, 0])
        if segs and segs[0] in ("1", "2", "3"):
            return "bal", True
        if segs and segs[0] in ("4", "5", "6"):
            return "res", True
        if name_kind is None:
            name_kind = _section_by_name(df.iloc[j, 1])
    return name_kind, False


def _find_blocks(df):
    """Encuentra bloques (encabezado + filas) en una hoja. Devuelve lista de
    dicts {hr, periods:[(col,label,year)], kind, end}."""
    blocks = []
    for i in range(len(df)):
        # Una fila es ENCABEZADO de bloque solo si su primera celda NO es un
        # código de cuenta (evita falsos positivos por valores tipo "2024" en
        # filas de datos). Los encabezados traen "codigo"/"CUENTA" o vacío.
        c0 = _segs(df.iloc[i, 0])
        if c0 and c0[0][:1].isdigit():
            continue
        periods = _detect_periods(df.iloc[i])
        if len(periods) >= 1:
            kind, coded = _first_account_section(df, i + 1)
            if kind:
                blocks.append({"hr": i, "periods": periods, "kind": kind, "coded": coded})
    # delimitar el fin de cada bloque (inicio del siguiente)
    for idx, b in enumerate(blocks):
        b["end"] = blocks[idx + 1]["hr"] if idx + 1 < len(blocks) else len(df)
    return blocks


def _route_balance(code: str, name: str, corriente: bool) -> str:
    n = _norm(name)
    sec = _segs(code)[0]
    if sec == "1":
        if "EFECTIVO" in n: return "efectivo"
        # NIC 2 — Inventarios: el plan puede llamarlo REALIZABLE o MERCADERIA.
        if "INVENTARIO" in n or "REALIZABLE" in n or "MERCADER" in n: return "inventario"
        if "PROPIEDAD" in n or "PLANTA" in n or "EQUIPO" in n or "ACTIVO FIJO" in n or "ACTIVOS FIJOS" in n: return "ppe"
        if "DIFERID" in n: return "actImpDif"
        if "FINANCIER" in n or "INVERSION" in n: return "inversiones"
        if "IMPUEST" in n: return "impRec"
        # Cartera comercial sólo si es corriente y de clientes/comercial.
        if corriente and ("COMERCIAL" in n or "CLIENTE" in n):
            return "cxc"
        if "RELACIONAD" in n: return "cxcRel"
        if corriente and ("COBRAR" in n or "EXIGIBLE" in n):
            return "cxc"
        # Cuentas por cobrar a largo plazo (no corrientes) = su propio rubro.
        if (not corriente) and ("COBRAR" in n or "CLIENTE" in n or "EXIGIBLE" in n):
            return "cxcLP"
        # Regla: no fusionar categorías distintas. Lo no corriente no reconocido
        # como PP&E, diferido o CxC L/P va a "otros activos no corrientes", nunca a PP&E.
        return "otrasCxc" if corriente else "otrosActNoCorr"
    if sec == "2":
        if "DIFERID" in n: return "pasImpDif"
        if "RELACIONAD" in n: return "cxpRel"
        if "ANTICIPO" in n: return "anticipos"
        if "IMPUEST" in n: return "impPagar"
        if any(k in n for k in ("BENEFICIO", "EMPLEADO", "JUBIL", "DESAHUCIO", "SOCIALES")):
            return "benef" if corriente else "benefPost"
        if "PROVISION" in n: return "provisiones" if corriente else "benefPost"
        if any(k in n for k in ("PAGAR", "PROVEEDOR", "COMERCIAL", "DOCUMENTOS", "PRESTAMO", "OBLIGACION")):
            return "cxp"
        return "otrasCxp" if corriente else "cxpRel"
    if "CAPITAL" in n: return "capital"
    if "RESERVA" in n: return "reservas"
    if "INTEGRAL" in n: return "ori"
    return "resAcum"


def _route_exigible(name: str) -> str:
    """Reparte el EXIGIBLE en sus rubros NIIF por nombre de cuenta/grupo:
    cartera comercial, anticipos a proveedores, CxC relacionadas, activos por
    impuestos y otras CxC. Materialidad: lo inmaterial queda en 'otrasCxc'."""
    n = _norm(name)
    if "ANTICIPO" in n: return "anticiposProv"   # anticipos a proveedores
    if "IMPUEST" in n: return "impRec"            # activos por impuestos corrientes
    if "NO RELACIONAD" in n: return "otrasCxc"    # otras CxC no relacionadas
    if "RELACIONAD" in n: return "cxcRel"         # CxC / préstamos relacionadas
    if "EMPLEADO" in n: return "otrasCxc"         # CxC empleados (inmaterial)
    if "COMERCIAL" in n or "CLIENTE" in n: return "cxc"
    if "OTRAS" in n or "OTRA" in n: return "otrasCxc"
    if "COBRAR" in n: return "cxc"
    return "otrasCxc"

def _es_generico(name: str) -> bool:
    n = _norm(name)
    return any(k in n for k in ("OTRAS", "OTROS", "VARIAS", "VARIOS", "DIVERS"))

def _es_contenedor(name: str) -> bool:
    """Nodo estructural sin rubro propio (se descompone en sus grupos hijos)."""
    n = _norm(name).strip()
    if "EXIGIBLE" in n or "CORTO PLAZO" in n or "LARGO PLAZO" in n:
        return True
    return n in ("PASIVO CORRIENTE", "PASIVO NO CORRIENTE",
                 "ACTIVO CORRIENTE", "ACTIVO NO CORRIENTE")

def _route_pasivo(name: str, corriente: bool) -> str:
    """Reparte el pasivo en sus rubros por nombre de cuenta/grupo (NIC 1)."""
    n = _norm(name)
    if "DIFERID" in n: return "pasImpDif"
    if "FINANCIER" in n or "BANCARI" in n or "BANCO" in n or "INSTITUCIONES FINAN" in n:
        return "oblBanc" if corriente else "prestamosLP"
    if "TRIBUTARI" in n or "IMPUEST" in n or "FISCO" in n or "RENTA" in n or "IVA" in n or "SRI" in n:
        return "impPagar"
    if any(k in n for k in ("EMPLEADO", "BENEFICIO", "JUBIL", "DESAHUCIO", "SOCIALES", "REMUNERAC", "NOMINA")):
        return "benef" if corriente else "benefPost"
    if "PROVISION" in n: return "provisiones" if corriente else "benefPost"
    if "NO RELACIONAD" in n: return "otrasCxp"
    if "RELACIONAD" in n or "ACCIONISTA" in n or "SOCIO" in n:
        return "cxpRelCorr" if corriente else "cxpRel"
    if "ANTICIPO" in n: return "anticipos"
    if "OTRAS" in n or "OTRA" in n or "OTROS" in n: return "otrasCxp"
    if "PRESTAMO" in n: return "oblBanc" if corriente else "prestamosLP"
    if any(k in n for k in ("PROVEEDOR", "COMERCIAL", "DOCUMENTOS", "PAGAR", "OBLIGACION")):
        return "cxp"
    return "otrasCxp" if corriente else "cxpRel"


def _parse_balance_block(df, b, data, ncols):
    rows = df.iloc[b["hr"] + 1:b["end"]]
    cols = b["periods"]  # [(col,label,year)]
    # Prefijos de 3 segmentos del grupo EXIGIBLE que tienen hijos de 4 segmentos:
    # en ellos descendemos al nivel de rubro (cartera comercial vs. anticipos,
    # impuestos, otras CxC) en vez de sumar todo el exigible como cartera.
    def _route_grupo(code, name, corriente):
        # Activo (sec 1) usa el ruteo de exigible; pasivo (sec 2) el de pasivo.
        return _route_pasivo(name, corriente) if _segs(code)[0] == "2" else _route_exigible(name)
    pref3_hijos, pref4_hijos, contenedores, filas4 = set(), set(), set(), set()
    for _, r in rows.iterrows():
        segs = _segs(r.iloc[0])
        if len(segs) >= 4:
            pref3_hijos.add(tuple(segs[:3]))
        if len(segs) >= 5:
            pref4_hijos.add(tuple(segs[:4]))
        if len(segs) == 4:
            filas4.add(tuple(segs))
        if len(segs) == 3 and _es_contenedor(str(r.iloc[1])):
            contenedores.add(tuple(segs))
    # Grupos (3 seg) estructurales a descender, y subgrupos genéricos (4 seg,
    # sólo en activo, p.ej. "OTRAS CxC") que se descomponen a 5 seg (relacionadas).
    descender3 = {p for p in contenedores if p in pref3_hijos}
    descender4 = set()
    for _, r in rows.iterrows():
        segs = _segs(r.iloc[0])
        if (len(segs) == 4 and segs[0] == "1" and tuple(segs[:3]) in descender3
                and _es_generico(str(r.iloc[1])) and tuple(segs[:4]) in pref4_hijos):
            descender4.add(tuple(segs[:4]))
    for yi, (col, _lab, _y) in enumerate(cols):
        if yi >= ncols:
            break
        total = {"1": 0.0, "2": 0.0, "3": 0.0}
        mapped = {"1": 0.0, "2": 0.0, "3": 0.0}
        for _, r in rows.iterrows():
            segs = _segs(r.iloc[0])
            if not segs or segs[0] not in ("1", "2", "3"):
                continue
            val = _num(r.iloc[col])
            if len(segs) == 1:
                total[segs[0]] = abs(val)
                continue
            if len(segs) == 3:
                if tuple(segs) in descender3:
                    continue  # se cubre con los grupos de 4 segmentos
                corriente = segs[1] == "1"
                key = _route_balance(str(r.iloc[0]), r.iloc[1], corriente)
                data[key][yi] += abs(val)
                mapped[segs[0]] += abs(val)
            elif len(segs) == 4 and tuple(segs[:3]) in descender3:
                if tuple(segs[:4]) in descender4:
                    continue  # se cubre con los sub-grupos de 5 segmentos
                key = _route_grupo(str(r.iloc[0]), r.iloc[1], segs[1] == "1")
                data[key][yi] += abs(val)
                mapped[segs[0]] += abs(val)
            elif len(segs) == 5 and tuple(segs[:4]) in descender4:
                key = _route_grupo(str(r.iloc[0]), r.iloc[1], segs[1] == "1")
                data[key][yi] += abs(val)
                mapped[segs[0]] += abs(val)
            elif (len(segs) == 5 and tuple(segs[:3]) in descender3
                  and tuple(segs[:4]) not in filas4):
                # Grupo "huérfano": existe a 5 seg sin fila de grupo a 4 seg.
                key = _route_grupo(str(r.iloc[0]), r.iloc[1], segs[1] == "1")
                data[key][yi] += abs(val)
                mapped[segs[0]] += abs(val)
        data["otrasCxc"][yi] += round(total["1"] - mapped["1"], 2)
        data["otrasCxp"][yi] += round(total["2"] - mapped["2"], 2)
        data["resAcum"][yi] += round(total["3"] - mapped["3"], 2)


def _classify_ing(names_joined: str) -> str:
    if any(k in names_joined for k in ("NO OPERAC", "NO OPERATIV", "FINANCIER", "RENDIMIENTO", "OTROS ING")):
        return "otrosIng"
    return "ventas"


def _classify_egr(names_joined: str) -> str:
    if "FINANCIER" in names_joined:
        return "gFin"
    if "DIFERID" in names_joined and "IMPUEST" in names_joined:
        return "impDif"
    if "COSTO" in names_joined:
        return "costo"
    return "gAdmin"


def _parse_resultados_block(df, b, data, ncols):
    """Suma las cuentas HOJA (sin hijos) del bloque y las clasifica por nombre.

    No confía en los subtotales del libro (que pueden ser inconsistentes; ej.
    un total "5 COSTOS Y GASTOS" que excluye los gastos). Las hojas particionan
    el estado, así que su suma es la cifra real por categoría.
    """
    rows = df.iloc[b["hr"] + 1:b["end"]]
    accts = []                 # [(segs_tuple, row)]
    name_by_code = {}          # segs_tuple -> nombre normalizado
    for _, r in rows.iterrows():
        s = tuple(_segs(r.iloc[0]))
        if not s or s[0] not in ("4", "5", "6"):
            continue
        accts.append((s, r))
        name_by_code[s] = _norm(r.iloc[1])
    codeset = {s for s, _ in accts}

    def is_leaf(c):
        if len(c) < 2:  # excluye totales/reclasificaciones de 1 segmento
            return False
        return not any(o != c and len(o) > len(c) and o[:len(c)] == c for o in codeset)

    def anc_names(c):
        # Excluye el nombre de SECCIÓN (nivel 1, ej. "COSTOS Y GASTOS") que
        # contaminaría la clasificación; usa nombres de nivel 2 en adelante.
        lo = 2 if len(c) >= 2 else 1
        return " ".join(name_by_code.get(c[:L], "") for L in range(lo, len(c) + 1))

    ing_keys = ("ventas", "otrosIng", "otrosIngFin")
    egr_keys = ("costo", "gAdmin", "gFin", "impDif")

    def sec_total(sec, col):
        best = 0.0
        for s, r in accts:
            if len(s) == 1 and s[0] == sec:
                v = abs(_num(r.iloc[col]))
                if v > best:
                    best = v
        return best

    for yi, (col, _lab, _y) in enumerate(b["periods"][:ncols]):
        # Acumular CON SIGNO por categoría: las cuentas contra (devoluciones,
        # descuentos) restan; luego valor absoluto por categoría.
        acc = {k: 0.0 for k in ing_keys + egr_keys}
        dna = 0.0  # depreciación + amortización (memo dentro de gastos/costos)
        for s, r in accts:
            if not is_leaf(s):
                continue
            val = _num(r.iloc[col])
            if val == 0:
                continue
            names = anc_names(s)
            if s[0] in ("5", "6") and ("DEPRECIA" in names or "AMORTIZA" in names):
                dna += abs(val)
            key = _classify_ing(names) if s[0] == "4" else _classify_egr(names)
            acc[key] += val
        bucket = {k: abs(acc[k]) for k in acc}
        ing_leaves = sum(bucket[k] for k in ing_keys)
        egr_leaves = sum(bucket[k] for k in egr_keys)
        # Reconciliar contra el total de sección: si el total declarado está
        # cerca (<=10%) de la suma de hojas, es la cifra autoritativa y se
        # escala el desglose para cuadrar; si el total excluye una categoría
        # entera (desfase grande, ej. gastos fuera del subtotal), se usan hojas.
        t_ing = sec_total("4", col)
        # Solo el total de la sección 5; un "6" suele ser reclasificación
        # duplicada. Las hojas de 6 (si las hay) ya entran por nombre en egr_leaves.
        t_egr = sec_total("5", col)
        ing_target = t_ing if (t_ing > 0 and ing_leaves <= t_ing * 1.10) else ing_leaves
        egr_target = t_egr if (t_egr > 0 and egr_leaves <= t_egr * 1.10) else egr_leaves
        fi = ing_target / ing_leaves if ing_leaves else 1.0
        fe = egr_target / egr_leaves if egr_leaves else 1.0
        for k in ing_keys:
            data[k][yi] = round(bucket[k] * fi, 2)
        for k in egr_keys:
            data[k][yi] = round(bucket[k] * fe, 2)
        data["dna"][yi] = round(dna * fe, 2)  # consistente con la escala de egresos
        data["partTrab"][yi] = 0.0
        data["irCausado"][yi] = 0.0


def extract_balance_interno(data_bytes: bytes) -> dict:
    xls = _read_excel(data_bytes)
    found = {"bal": [], "res": []}  # cada item: (block, df)
    for sh in xls.sheet_names:
        try:
            df = xls.parse(sh, header=None)
        except Exception:
            continue
        for b in _find_blocks(df):
            found[b["kind"]].append((b, df))

    def _pick(kind):
        items = found[kind]
        if not items:
            return None, None
        # preferir bloques con cuentas CODIFICADAS sobre los detectados por nombre
        coded = [it for it in items if it[0].get("coded")]
        return (coded[0] if coded else items[0])

    bal_block, bal_sheet = _pick("bal")
    res_block, res_sheet = _pick("res")

    if not bal_block and not res_block:
        raise ValueError(
            "No se encontró un balance (cuentas 1/2/3) ni un estado de resultados "
            "(cuentas 4/5) con columnas de fecha/año. Verifica el formato del archivo."
        )

    ncols = max(
        len(bal_block["periods"]) if bal_block else 0,
        len(res_block["periods"]) if res_block else 0,
    )
    data = {k: [0.0] * ncols for k in INPUT_KEYS}
    data["dna"] = [0.0] * ncols
    warnings: list[str] = []
    labels_esf: list[str] = []
    labels_er: list[str] = []

    if bal_block:
        labels_esf = [lab for _c, lab, _y in bal_block["periods"]][:ncols]
        _parse_balance_block(bal_sheet, bal_block, data, ncols)
    else:
        warnings.append("No se encontró Balance (ESF); solo se cargaron resultados.")
    if res_block:
        labels_er = [lab for _c, lab, _y in res_block["periods"]][:ncols]
        _parse_resultados_block(res_sheet, res_block, data, ncols)
    else:
        warnings.append("No se encontró Estado de Resultados (ER); solo se cargó el balance.")

    anios = [y for _c, _lab, y in (bal_block or res_block)["periods"]][:ncols]
    return {
        "data": data,
        "params": {},
        "warnings": warnings,
        "source": "interno",
        "anio_detectado": anios[-1] if anios else None,
        "anios_detectados": anios,
        "labels_esf": labels_esf,
        "labels_er": labels_er,
    }
