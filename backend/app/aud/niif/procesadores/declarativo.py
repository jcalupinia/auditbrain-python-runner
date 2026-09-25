"""Papel de trabajo de las pruebas DECLARATIVAS (catálogo y fichas sin procesador) con el
mismo diseño que las pruebas con procesador (``libro``): portada del Excel = panel del
HTML, HTML ejecutivo, Word (el HTML impreso) y PowerPoint (el HTML en pantalla).

El navegador envía las cédulas del exportador del sitio (``workbookSheets``) tal cual
(``cargaPapel`` en ``frontend/src/aud/niif/papelDeclarativo.js``). Aquí se pasan al modelo
de ``libro`` SIN mover una celda: la fila k de la cédula del sitio es la fila k del Excel
(fila 4 = encabezado, datos desde la 5, como en ``libro``), así cada fórmula del sitio
sigue apuntando a la misma celda. Además:

- la portada del sitio (``01_Caratula``) la reemplazan ``00_Inicio`` (el panel) y la
  carátula de ``libro``;
- el conteo de registros de «Controles» pasa a fórmula y el importe de cada excepción
  remite a la celda de la cédula donde se origina (sin cifras calculadas pegadas);
- el «Cuadro de períodos» de una serie se escribe con fórmulas (la misma recurrencia de
  ``runSeries`` del sitio) y las reglas que usan sus agregados (``clave_inicial``,
  ``_final``, ``_total``) lo leen: el exportador del sitio dejaba el cuadro como valores
  y el agregado apuntando a la columna A (Excel daba #¡VALOR! al recalcular);
- cada columna calculada lleva su explicación en lenguaje sencillo, generada de la
  definición (la misma fuente que produce la fórmula).
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from openpyxl.utils import get_column_letter

from backend.app.aud.niif.procesadores import libro, problemas

NOTAS = "CÓMO SE PREPARA Y CALCULA"
FIRMA = "AuditConsulting Auditores Cía. Ltda."
HOJAS = ("01_Caratula", "02_Programa", "03_Parametros", "04_Fuentes", "05_Data_Original", "06_Data_Procesada",
         "07_Calculos", "08_Pruebas", "09_Excepciones", "10_Sumaria", "11_Conclusion", "12_Control_Revision", "13_Cuadro")
# Sección del libro de cada cédula del sitio (libro.SECCIONES): 0 resultado, 1 cómo se calculó,
# 2 datos del cliente, 3 documentación. La portada del sitio no pasa al papel.
SECCION = {"02_Programa": 3, "03_Parametros": 1, "04_Fuentes": 3, "05_Data_Original": 2, "06_Data_Procesada": 1,
           "07_Calculos": 1, "08_Pruebas": 0, "09_Excepciones": 0, "10_Sumaria": 0, "11_Conclusion": 0,
           "12_Control_Revision": 3, "13_Cuadro": 1}
# Columnas de números enteros (filas, períodos, decimales): sin decimales.
ENTEROS = {"Fila", "Fila origen", "Período", "Períodos", "Versión", "Decimales"}
# Códigos del motor del sitio, en español para el papel.
CODIGOS = {"RESULT": "Resultado a evaluar", "REVERSAL": "Posible reversión", "NEGATIVE_NRV": "VNR negativo",
           "SERIES_NO_CIERRA": "El cuadro no cierra en cero"}
MAX_FILAS = 250_000
_SERIAL0 = date(1899, 12, 30)
FILA0 = libro.FILA_DATOS


class CargaInvalida(ValueError):
    """Lo que envió el navegador no es un papel declarativo que se pueda armar."""


def _col(j: int) -> str:
    return get_column_letter(j + 1)


def _numero(x):
    if isinstance(x, bool) or x in (None, ""):
        return None
    try:
        return float(str(x).strip())
    except ValueError:
        return None


def _decimales(x) -> int:
    t = str(x).strip()
    return len(t.split(".")[1].rstrip("0")) if "." in t and "e" not in t.lower() else 0


def _iso(serial) -> str:
    n = _numero(serial)
    return (_SERIAL0 + timedelta(days=round(n))).isoformat() if n is not None else ""


def _v(c):
    return c.get("v") if isinstance(c, dict) else c


def _convierte(c):
    """(valor para ``libro``, tipo «num»/«date»/«text» o None si está vacía, decimales)."""
    if c is None or c == "":
        return None, None, 0
    if isinstance(c, bool):
        return str(c), "text", 0
    if isinstance(c, (int, float)):
        return float(c), "num", _decimales(c)
    if isinstance(c, str):
        return c, "text", 0
    if isinstance(c, dict):
        if "f" in c:
            v, tipo = c.get("v"), c.get("type")
            if tipo == "date":
                iso = _iso(v)
                return {"f": str(c["f"]), "v": iso}, ("date" if iso else None), 0
            n = None if tipo == "text" else _numero(v)
            if n is not None:
                return {"f": str(c["f"]), "v": n}, "num", _decimales(v)
            t = "" if v is None else str(v)
            return {"f": str(c["f"]), "v": t}, ("text" if t else None), 0
        if "n" in c:
            if c.get("date"):
                return _iso(c["n"]) or None, "date", 0
            n = _numero(c["n"])
            return (n, "num", _decimales(c["n"])) if n is not None else (str(c["n"]), "text", 0)
    return str(c), "text", 0


def _formato(encabezado: str, tipos: set, decimales: int, enteros: bool) -> str:
    if tipos == {"date"}:
        return "d"
    if "date" in tipos or tipos == {"num", "text"}:
        return "x"                                 # mezcla (p. ej. «Resultado» de los controles)
    if "num" in tipos:
        if encabezado in ENTEROS and enteros:
            return "i"
        return "n" if decimales <= 2 else "g"
    return "t"


def _hoja(nombre: str, etiqueta: str, filas: list) -> dict:
    """Cédula del sitio → cédula de ``libro`` con las filas en la misma posición."""
    filas = [list(f) if isinstance(f, list) else [] for f in filas]
    i_notas = next((i for i, f in enumerate(filas) if f and f[0] == NOTAS), len(filas))
    cuerpo = filas[4:i_notas]
    while cuerpo and not any(x not in (None, "") for x in cuerpo[-1]):
        cuerpo.pop()
    encabezado = ["" if x is None else str(x) for x in (filas[3] if len(filas) > 3 else [])]
    ancho = max([len(encabezado), 1] + [len(f) for f in cuerpo])
    rows, tipos, decs, enteros = [], [set() for _ in range(ancho)], [0] * ancho, [True] * ancho
    for f in cuerpo:
        fila = []
        for j in range(ancho):
            v, t, d = _convierte(f[j] if j < len(f) else None)
            fila.append(v)
            if t:
                tipos[j].add(t)
            if t == "num":
                decs[j] = max(decs[j], d)
                enteros[j] = enteros[j] and float(_v(v)).is_integer()
        rows.append(fila)
    cols = [[encabezado[j] if j < len(encabezado) else "", _formato(encabezado[j] if j < len(encabezado) else "", tipos[j], decs[j], enteros[j])]
            for j in range(ancho)]
    nota = " ".join(str(f[0]) for f in filas[i_notas + 1:] if f and f[0] not in (None, ""))
    return {"name": nombre, "label": etiqueta, "cols": cols, "rows": rows, "total": None,
            "seccion": SECCION.get(nombre, 1), "nota": nota}


# --- Fórmulas: expresión de una operación (la misma tabla que el exportador del sitio) ---------

def _expresion(op: str, a: str, b: str, c: str = "", tabla=None) -> str:
    return {
        "add": f"{a}+{b}", "subtract": f"{a}-{b}", "multiply": f"{a}*{b}", "divide": f"{a}/{b}",
        "min": f"MIN({a},{b})", "max": f"MAX({a},{b})", "gt": f"IF({a}>{b},1,0)", "gte": f"IF({a}>={b},1,0)",
        "lt": f"IF({a}<{b},1,0)", "lte": f"IF({a}<={b},1,0)", "eq": f"IF({a}={b},1,0)", "if": f"IF({a}<>0,{b},{c})",
        "days": f"({b}-{a})",
        "band": ("LOOKUP(" + a + ",{" + ",".join(str(x["from"]) for x in tabla or []) + "},{"
                 + ",".join(str(x["value"]) for x in tabla or []) + "})") if op == "band" else "",
    }[op]


def _literal(t: str) -> str:
    n = _numero(t)
    if n is None:
        raise CargaInvalida(f"Constante inválida en la serie: {t}")
    return str(t).strip().lstrip("+")


# --- Cuadro de períodos con fórmulas ---------------------------------------------------------

def _orden_serie(d: dict) -> list[str]:
    return list((d.get("series") or {}).get("order") or ["backward", "forward"])


def _claves_serie(d: dict) -> list[str]:
    s = d.get("series") or {}
    return [x["key"] for p in _orden_serie(d) for x in (s.get(p) or [])]


def _bloques(h13: dict, h06: dict) -> list[dict]:
    """Contratos del cuadro: filas consecutivas con el mismo identificador, en el orden de la
    población (el exportador concatena los contratos en ese orden), con su fila en «Datos procesados»."""
    bloques = []
    for i, f in enumerate(h13["rows"]):
        ident = _v(f[0]) if f else None
        if ident in (None, ""):
            continue
        if bloques and bloques[-1]["id"] == ident and bloques[-1]["filas"][-1] == i - 1:
            bloques[-1]["filas"].append(i)
        else:
            bloques.append({"id": ident, "filas": [i]})
    ids = [_v(f[0]) if f else None for f in h06["rows"]]
    k = 0
    for b in bloques:
        while k < len(ids) and ids[k] != b["id"]:
            k += 1
        if k == len(ids):
            raise CargaInvalida(f"El cuadro de períodos tiene un contrato que no está en los datos: {b['id']}")
        b["dato"] = k
        k += 1
    return bloques


def _cuadro(d: dict, h13: dict, h06: dict, bloques: list[dict]) -> None:
    """Escribe cada celda calculada del cuadro como fórmula, con la recurrencia de ``runSeries``:
    ``backward`` recorre del último período al primero y ``forward`` del primero al último;
    ``@clave`` es el período anterior del pase (o su semilla), ``^clave`` el primer período y
    ``clave`` el mismo período o, si no es de la serie, el dato del contrato."""
    s = d["series"]
    orden = _orden_serie(d)
    listas = {p: list(s.get(p) or []) for p in ("backward", "forward")}
    claves = _claves_serie(d)
    col_de = {"periodo": "B", "periodos": "C", **{k: _col(3 + i) for i, k in enumerate(claves)}}
    campos = {f["key"]: _col(j) for j, f in enumerate(d["fields"])}
    j_de = {k: 3 + i for i, k in enumerate(claves)}
    for b in bloques:
        n = FILA0 + b["dato"]
        filas = b["filas"]
        hechos: set = {"periodo", "periodos"}          # claves ya calculadas en todas las filas
        for p in orden:
            lista = listas[p]
            semillas = {x["key"]: x.get("seed") for x in lista if x.get("seed") is not None}
            recorrido = list(reversed(range(len(filas)))) if p == "backward" else list(range(len(filas)))
            for paso, pos in enumerate(recorrido):
                i = filas[pos]
                anterior = filas[recorrido[paso - 1]] if paso > 0 else None
                listos = set()                             # claves ya calculadas en esta fila, en este pase
                primero_listo = paso > 0 and p == "forward"  # la fila 1 ya pasó en este pase (forward)

                def ref(x: str) -> str:
                    if x.startswith("#"):
                        return _literal(x[1:])
                    if x.startswith("@"):
                        k = x[1:]
                        if anterior is not None:
                            return f"{col_de[k]}{FILA0 + anterior}"
                        sd = semillas.get(k)
                        if sd is None:
                            return "0"
                        if str(sd).startswith("#"):
                            return _literal(sd[1:])
                        return ref(str(sd)) if (sd in hechos or sd in listos or sd in campos) else "0"
                    if x.startswith("^"):
                        k = x[1:]
                        en_primera = k in hechos or (k in listos and pos == 0) or (primero_listo and k in {y["key"] for y in lista})
                        if en_primera:
                            return f"${col_de[k]}${FILA0 + filas[0]}"
                        return f"{col_de[k]}{FILA0 + i}" if k in listos else "0"
                    if x in hechos or x in listos:
                        return f"{col_de[x]}{FILA0 + i}"
                    if x in campos:
                        return f"'06_Data_Procesada'!${campos[x]}${n}"
                    raise CargaInvalida(f"Operando no disponible en la serie: {x}")

                for regla in lista:
                    exp = _expresion(regla["op"], ref(regla["a"]), ref(regla["b"]))
                    j = j_de[regla["key"]]
                    fila = h13["rows"][i]
                    fila[j] = {"f": f"ROUND(ROUND({exp},6),{int(regla['precision'])})", "v": _v(fila[j])}
                    listos.add(regla["key"])
            hechos |= {x["key"] for x in lista}


def _reglas_con_agregados(d: dict, h07: dict, h03: dict, bloques: list[dict]) -> None:
    """Las reglas que usan un agregado de la serie leen el cuadro: ``_inicial`` el primer
    período, ``_final`` el último y ``_total`` la suma de los períodos del contrato. El resto de
    la fórmula es la del exportador del sitio (mismos controles de fila vacía o incompleta)."""
    claves = _claves_serie(d)
    col_k = {k: _col(3 + i) for i, k in enumerate(claves)}
    agregados = {k + suf for k in claves for suf in ("_inicial", "_final", "_total")}
    off = 3 if d.get("id") == "pce" else 1
    campos = [f["key"] for f in d["fields"]]
    reglas = d["rules"]
    fila_const = {str(f[0])[len("Constante "):]: FILA0 + i for i, f in enumerate(h03["rows"])
                  if f and isinstance(f[0], str) and f[0].startswith("Constante #")}
    por_dato = {b["dato"]: b for b in bloques}
    nf = len(campos)
    ultima = _col(nf - 1)
    for jr, r in enumerate(reglas):
        if not any(isinstance(r.get(x), str) and r[x] in agregados for x in ("a", "b", "c")):
            continue
        jc = off + jr
        for i, fila in enumerate(h07["rows"]):
            celda = fila[jc] if jc < len(fila) else None
            b = por_dato.get(i)
            if not isinstance(celda, dict) or b is None:
                continue
            n = FILA0 + i
            r0, r1 = FILA0 + b["filas"][0], FILA0 + b["filas"][-1]

            def ref(x: str) -> str:
                if x == "corte" and "corte" not in campos:
                    return "'03_Parametros'!$B$5"
                if x.startswith("#"):
                    if x not in fila_const:
                        raise CargaInvalida(f"La constante {x} no está en «Parámetros y reglas».")
                    return f"'03_Parametros'!$B${fila_const[x]}"
                if x == "rate" and d.get("id") == "pce":
                    return f"C{n}"
                if x in campos:
                    return f"'06_Data_Procesada'!{_col(campos.index(x))}{n}"
                if x in agregados:
                    k, suf = x.rsplit("_", 1)
                    L = col_k[k]
                    return {"inicial": f"'13_Cuadro'!${L}${r0}", "final": f"'13_Cuadro'!${L}${r1}",
                            "total": f"SUM('13_Cuadro'!${L}${r0}:${L}${r1})"}[suf]
                return f"{_col(off + [y['key'] for y in reglas].index(x))}{n}"

            a = ref(r["a"])
            bb = ref(r["b"]) if r.get("b") is not None else ""
            c = ref(r["c"]) if r.get("c") is not None else ""
            exp = _expresion(r["op"], a, bb, c, r.get("table"))
            vacia = f"COUNTA('05_Data_Original'!A{n}:{ultima}{n})"
            celda["f"] = f'IF({vacia}=0,"",IF({vacia}<{nf},NA(),ROUND(ROUND({exp},6),{int(r["precision"])})))'


# --- Sin cifras calculadas pegadas ------------------------------------------------------------

def _controles(h08: dict, h03: dict, n_datos: int) -> None:
    """«Controles y conciliación»: el conteo de registros pasa a fórmula, y la diferencia y el
    resultado muestran lo que calculan sus fórmulas (el HTML y el Word leen el valor; el Excel,
    la fórmula: deben decir lo mismo aunque la conciliación aún no se haya registrado)."""
    por = {f[0]: f for f in h08["rows"] if f and isinstance(f[0], str) and len(f) > 1}
    if "Registros" in por and not isinstance(por["Registros"][1], dict):
        por["Registros"][1] = {"f": f"COUNTIF('05_Data_Original'!A{FILA0}:A{FILA0 + max(n_datos, 1) - 1},\"<>\")",
                               "v": float(n_datos)}
    pob, saldo = (_numero(_v(por[k][1])) if k in por else None for k in ("Población", "Saldo contable"))
    tol = next((_numero(_v(f[1])) for f in h03["rows"] if f and f[0] == "Tolerancia" and len(f) > 1), None)
    dif = por.get("Diferencia")
    if pob is not None and saldo is not None and dif and isinstance(dif[1], dict):
        dif[1]["v"] = round(pob - saldo, 2)
        res = por.get("Resultado")
        if res and isinstance(res[1], dict) and tol is not None:
            res[1]["v"] = "CONFORME" if abs(pob - saldo) <= tol + 1e-9 else "REVISAR"


def _excepciones_enlazadas(h09: dict, mapa: dict, primaria: str | None) -> None:
    """El importe de cada excepción remite a la celda de la cédula que lo calcula (la de la misma
    partida en «Cálculos auditables» o, para la serie, en el «Cuadro de períodos») y solo si esa
    celda tiene el mismo importe: un enlace equivocado nunca cambia una cifra."""
    nombres = [c[0] for c in h09["cols"]]
    if not {"Identificador", "Código", "Importe"} <= set(nombres):
        return
    j_id, j_cod, j_imp = nombres.index("Identificador"), nombres.index("Código"), nombres.index("Importe")
    for f in h09["rows"]:
        if j_cod < len(f) and isinstance(f[j_cod], str):
            f[j_cod] = CODIGOS.get(f[j_cod], f[j_cod])
        imp = _numero(_v(f[j_imp])) if j_imp < len(f) else None
        if imp is None or isinstance(f[j_imp], dict):
            continue
        ident = _v(f[j_id])
        for nombre in ("07_Calculos", "13_Cuadro"):
            h = mapa.get(nombre)
            if not h:
                continue
            filas = [i for i, x in enumerate(h["rows"]) if x and _v(x[0]) == ident]
            if nombre == "13_Cuadro":
                filas = filas[::-1]                    # el cierre se juzga en el último período
            cols = list(range(1, len(h["cols"])))
            enc = [c[0] for c in h["cols"]]
            if primaria in enc:
                cols.sort(key=lambda j: j != enc.index(primaria))
            hit = next(((i, j) for i in filas for j in cols
                        if j < len(h["rows"][i]) and _numero(_v(h["rows"][i][j])) is not None
                        and abs(_numero(_v(h["rows"][i][j])) - imp) < problemas.TOL), None)
            if hit:
                f[j_imp] = {"f": f"'{nombre}'!{_col(hit[1])}{FILA0 + hit[0]}", "v": imp}
                break
    h09["problemas"] = True


# --- Explicaciones en lenguaje sencillo --------------------------------------------------------

_OPS = {
    "add": "Suma {a} y {b}", "subtract": "Resta {b} de {a}", "multiply": "Multiplica {a} por {b}",
    "divide": "Divide {a} entre {b}", "min": "Toma el menor entre {a} y {b}", "max": "Toma el mayor entre {a} y {b}",
    "gt": "Vale 1 si {a} es mayor que {b}; si no, 0", "gte": "Vale 1 si {a} es mayor o igual que {b}; si no, 0",
    "lt": "Vale 1 si {a} es menor que {b}; si no, 0", "lte": "Vale 1 si {a} es menor o igual que {b}; si no, 0",
    "eq": "Vale 1 si {a} es igual a {b}; si no, 0", "if": "Si {a} no es cero toma {b}; si no, {c}",
    "days": "Cuenta los días desde {a} hasta {b}", "band": "Busca el tramo en que cae {a} y toma su valor",
}


def _nombre_operando(x, d: dict, paso: str | None = None) -> str:
    if x is None:
        return ""
    x = str(x)
    etq = {f["key"]: f.get("label") or f["key"] for f in d["fields"]}
    etq.update({r["key"]: r.get("label") or r["key"] for r in d["rules"]})
    s = d.get("series") or {}
    etq.update({y["key"]: y.get("label") or y["key"] for p in ("backward", "forward") for y in s.get(p) or []})
    if x.startswith("#"):
        return f"la constante {x[1:].replace('.', ',')}"
    if x.startswith("@"):
        # El pase «backward» recorre del último período al primero: su «anterior» es el siguiente.
        return f"«{etq.get(x[1:], x[1:])}» del período {'siguiente' if paso == 'backward' else 'anterior'}"
    if x.startswith("^"):
        return f"«{etq.get(x[1:], x[1:])}» del primer período"
    if x == "corte":
        return "la fecha de corte"
    if x == "rate":
        return "la tasa del tramo"
    if x in ("periodo", "periodos"):
        return "el número del período" if x == "periodo" else "el número de períodos"
    for suf, txt in (("_inicial", "del primer período"), ("_final", "del último período"), ("_total", "sumada en todos los períodos")):
        if x.endswith(suf) and x[: -len(suf)] in etq:
            return f"«{etq[x[: -len(suf)]]}» {txt} (Cuadro de períodos)"
    return f"«{etq.get(x, x)}»"


def _explica_regla(r: dict, d: dict, paso: str | None = None) -> str:
    base = _OPS.get(r["op"], "Calcula {a} y {b}").format(
        a=_nombre_operando(r.get("a"), d, paso), b=_nombre_operando(r.get("b"), d, paso), c=_nombre_operando(r.get("c"), d, paso))
    if r["op"] == "band":
        base += " (" + ", ".join(f"desde {x['from']}: {x['value']}" for x in r.get("table") or []) + ")"
    return base + f" y redondea a {r['precision']} decimales."


def _explicaciones(d: dict, mapa: dict) -> None:
    norma = ((d.get("source") or {}).get("document") or "").strip()
    h = mapa.get("06_Data_Procesada")
    if h:
        h["explica"] = {c[0]: f"Trae «{c[0]}» de «Datos originales», de la misma fila; si está vacío, queda en blanco."
                        for c in h["cols"] if c[0]}
    h = mapa.get("07_Calculos")
    if h:
        exp = {"Identificador": "Trae el identificador de la partida desde «Datos procesados», de la misma fila."}
        if d.get("id") == "pce":
            exp["Días de mora"] = "Cuenta los días entre el vencimiento y la fecha de corte; nunca es negativo."
            exp["Tasa"] = "Toma la tasa del tramo de mora en que caen los días, según la tabla de «Parámetros y reglas»."
        vacia = " Si la partida está vacía queda en blanco; si le falta un dato, muestra #N/D."
        for r in d["rules"]:
            exp[r.get("label") or r["key"]] = _explica_regla(r, d) + vacia
        h["explica"] = exp
        h["norma"] = norma
    h = mapa.get("08_Pruebas")
    if h:
        h["explica"] = {"Resultado": (
            "Cada control tiene su fórmula: los registros cuentan las partidas de «Datos originales»; el saldo contable "
            "viene de «Parámetros y reglas»; la población suma la columna de conciliación; la diferencia es población "
            "menos saldo, y el resultado dice CONFORME si la diferencia no pasa la tolerancia aceptada.")}
    h = mapa.get("09_Excepciones")
    if h:
        h["explica"] = {"Importe": problemas.EXPLICA_IMPORTE}
        h["origen"] = {"Importe": "la cédula donde se origina cada excepción (la fórmula de cada fila indica la celda)"}
    h = mapa.get("10_Sumaria")
    if h:
        h["explica"] = {"Importe": "Suma, en «Cálculos auditables», la columna de ese resultado en todas las partidas."}
        h["norma"] = norma
    h = mapa.get("13_Cuadro")
    if h:
        s = d.get("series") or {}
        h["explica"] = {y.get("label") or y["key"]: f"{_explica_regla(y, d, p)[:-1]} en cada período"
                        + (" (se calcula del último período al primero)." if p == "backward" else ".")
                        for p in ("backward", "forward") for y in s.get(p) or []}
        h["norma"] = norma


# --- Panel (lo que en un procesador es su PANEL) -----------------------------------------------

def _panel(d: dict, mapa: dict) -> dict:
    """Tarjetas y gráficos del panel, derivados de la definición: la población es la columna de
    conciliación; «registrado vs recalculado» es el saldo del mayor frente a la población según
    los datos (la conciliación de la prueba); la composición es el resultado principal por
    partida y la distribución, la población por partida."""
    campos = {f["key"]: f.get("label") or f["key"] for f in d["fields"]}
    reglas = {r["key"]: r.get("label") or r["key"] for r in d["rules"]}
    control = d.get("control")
    if control in campos:
        hoja_ctl, col_ctl, etq_ctl = "06_Data_Procesada", campos[control], (mapa.get("06_Data_Procesada") or {"cols": [[""]]})["cols"][0][0]
    else:
        hoja_ctl, col_ctl, etq_ctl = "07_Calculos", reglas.get(control, control), "Identificador"
    prim = reglas.get(d.get("primary"), d.get("primary"))
    return {
        "poblacion": {"rotulo": f"Población · {col_ctl}", "hoja": hoja_ctl, "col": col_ctl},
        "recalculado": {"rotulo": "Población según los datos", "hoja": hoja_ctl, "col": col_ctl},
        "registrado": {"rotulo": "Saldo del mayor", "hoja": "03_Parametros", "col": "Valor",
                       "donde": {"Parámetro": ["Saldo contable"]}},
        "composicion": {"rotulo": f"{prim} por partida", "hoja": "07_Calculos", "etiqueta": "Identificador", "valor": prim},
        "distribucion": {"rotulo": f"{col_ctl} por partida", "hoja": hoja_ctl, "etiqueta": etq_ctl, "valor": col_ctl},
    }


# --- Entrada ----------------------------------------------------------------------------------

def _valida(carga) -> tuple[dict, list, list, list]:
    if not isinstance(carga, dict):
        raise CargaInvalida("El papel declarativo llegó vacío.")
    t, ced = carga.get("herramienta"), carga.get("cedulas")
    if not isinstance(t, dict) or not isinstance(ced, dict):
        raise CargaInvalida("Faltan la herramienta o sus cédulas.")
    d = t.get("definition")
    if not isinstance(d, dict) or not isinstance(d.get("fields"), list) or not d["fields"] or not isinstance(d.get("rules"), list):
        raise CargaInvalida("La definición de la prueba no es válida.")
    nombres, etiquetas, hojas = ced.get("nombres"), ced.get("etiquetas"), ced.get("hojas")
    if not (isinstance(nombres, list) and isinstance(etiquetas, list) and isinstance(hojas, list)) \
            or not len(nombres) == len(etiquetas) == len(hojas) or not nombres:
        raise CargaInvalida("Las cédulas del papel no están completas.")
    if any(n not in HOJAS for n in nombres) or len(set(nombres)) != len(nombres):
        raise CargaInvalida("Una cédula del papel no es del exportador del sitio.")
    if not {"03_Parametros", "05_Data_Original", "06_Data_Procesada", "07_Calculos"} <= set(nombres):
        raise CargaInvalida("Faltan cédulas del núcleo del papel (parámetros, datos o cálculos).")
    if sum(len(h) for h in hojas if isinstance(h, list)) > MAX_FILAS:
        raise CargaInvalida("El papel es demasiado grande para armarlo de una vez. Divida la población en lotes.")
    return t, nombres, etiquetas, hojas


def _firma(e: dict) -> str:
    f = str(e.get("firm") or "").strip()
    return FIRMA if not f or re.search(r"audit.*consult", f, re.I) else f


def armar(carga: dict) -> tuple:
    """(definición, registro, eventos, versión, estado) para ``libro`` a partir de lo que envió el
    navegador (``cargaPapel``)."""
    t, nombres, etiquetas, crudas = _valida(carga)
    d = t["definition"]
    hojas = [_hoja(n, e, f) for n, e, f in zip(nombres, etiquetas, crudas) if n != "01_Caratula"]
    mapa = {h["name"]: h for h in hojas}
    n_datos = len(mapa["05_Data_Original"]["rows"])
    if d.get("series") and "13_Cuadro" in mapa:
        bloques = _bloques(mapa["13_Cuadro"], mapa["06_Data_Procesada"])
        _cuadro(d, mapa["13_Cuadro"], mapa["06_Data_Procesada"], bloques)
        _reglas_con_agregados(d, mapa["07_Calculos"], mapa["03_Parametros"], bloques)
    if "08_Pruebas" in mapa:
        _controles(mapa["08_Pruebas"], mapa["03_Parametros"], n_datos)
    reglas = {r["key"]: r.get("label") or r["key"] for r in d["rules"]}
    if "09_Excepciones" in mapa:
        _excepciones_enlazadas(mapa["09_Excepciones"], mapa, reglas.get(d.get("primary")))
    _explicaciones(d, mapa)
    run_sitio = t.get("run") or {}
    etiquetas_run = {**{f["key"]: f.get("label") or f["key"] for f in d["fields"]}, **reglas}
    run = {"engine": f"Motor declarativo {run_sitio.get('engine') or ''}".strip(), "primary": d.get("primary"),
           "totals": dict(run_sitio.get("totals") or {}), "labels": etiquetas_run,
           "exceptions": list(run_sitio.get("exceptions") or []), "hojas": hojas}
    e = dict(t.get("engagement") or {})
    e["firm"] = _firma(e)
    definicion = {**d, "declarativa": True, "panel": _panel(d, mapa)}
    reg = {"engagement": e, "run": run, "approvedBy": t.get("approvedBy"), "approvedAt": t.get("approvedAt"),
           "reconciliation": t.get("reconciliation") or {}, "analysis": t.get("analysis") or "",
           "conclusion": t.get("conclusion") or "", "exceptionReview": t.get("exceptionReview") or ""}
    estado = "DEMOSTRACIÓN" if t.get("demo") else str(t.get("state") or "BORRADOR")
    return definicion, reg, [], int(t.get("version") or 1), estado


FORMATOS = {"xlsx": "xlsx", "html": "html", "docx": "docx", "pptx": "pptx", "pdf": "pdf"}


def archivo(carga: dict, formato: str) -> bytes:
    """El papel declarativo en ``formato`` (xlsx, html, docx, pptx o pdf), con el diseño de ``libro``."""
    if formato not in FORMATOS:
        raise CargaInvalida("Formato no disponible.")
    return getattr(libro, FORMATOS[formato])(*armar(carga))


def papel(carga: dict) -> dict[str, bytes]:
    """Los cuatro archivos del papel aprobado. El HTML ya trae dentro el Excel, el Word y el
    PowerPoint; se arman una vez y se reutilizan."""
    args = armar(carga)
    return {"xlsx": libro.xlsx(*args), "docx": libro.docx(*args), "pptx": libro.pptx(*args), "html": libro.html(*args)}
