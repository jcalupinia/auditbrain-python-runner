"""Datos del cliente dentro del libro, para todas las herramientas (decisión del dueño, 2026-09-24/25).

El piloto (pérdidas incurridas) arma a mano sus hojas ``D1_…``–``D5_…``. Aquí se hace lo mismo
para cualquier procesador, a partir de su definición y de lo que el cliente entregó:

1. **Una hoja por documento entregado** (``D1_<anexo>``, ``D2_<anexo>``…): cada fila del archivo
   del cliente con los campos del requerimiento, la columna «Origen del dato» (archivo · hoja ·
   fila) y la guía «¿De dónde saco este dato?» (el documento y su contenido, del requerimiento).
2. **Las cédulas leen de ahí por fórmula:** cada dato del cliente que una cédula traía pegado
   (saldo, fecha, cantidad…) pasa a ser una fórmula a su celda en la hoja de datos. Solo se enlaza
   cuando la fila de la cédula es de la MISMA partida (su identificador está en la fila) y la celda
   tiene el MISMO valor, de preferencia en la columna del mismo nombre; si hay duda, el valor queda
   como estaba. Un enlace nunca cambia una cifra.

``con_datos(mod, run, datasets)`` devuelve las cédulas del procesador más las hojas de datos.
El piloto (``perdidas_incurridas_s11``) ya trae las suyas y no pasa por aquí.
"""
from __future__ import annotations

import re
import unicodedata

from openpyxl.utils import get_column_letter

from backend.app.aud.niif.procesadores.perdidas_incurridas_s11 import FILA0, a_fecha, a_num

TOL = 0.006
PROPIAS = {"perdidas_incurridas_s11"}          # herramientas que arman sus hojas de datos a mano
_FMT = {"number": "n", "date": "d"}


def _slug(t: str, largo: int = 24) -> str:
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_")
    return (t[:1].upper() + t[1:])[:largo] or "Anexo"


def _v(c):
    return c.get("v") if isinstance(c, dict) else c


def _num(v):
    if isinstance(v, bool) or v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _valor(campo: dict, crudo):
    """El dato como lo usa el libro: número, fecha ISO o texto (vacío → None)."""
    if crudo in (None, ""):
        return None
    if campo.get("type") == "number":
        x = a_num(crudo)
        return float(x) if x is not None else str(crudo)
    if campo.get("type") == "date":
        d = a_fecha(crudo)
        return d.isoformat() if d else str(crudo)
    return str(crudo).strip()


def _origen(f: dict) -> str:
    partes = [str(f.get("_file") or "").strip(), str(f.get("_sheet") or "").strip()]
    fila = f.get("_row")
    txt = " · ".join(p for p in partes if p)
    return (txt + (f" · fila {fila}" if fila not in (None, "") else "")).strip(" ·") or "Entregado por el cliente"


def _campos_de(mod, ds: str) -> list:
    campos = getattr(mod, "CAMPOS", {}) or {}
    tipo = mod.kind(ds) if hasattr(mod, "kind") else ds
    return list(campos.get(tipo) or campos.get(ds) or [])


def hojas_datos(mod, datasets: dict) -> list[dict]:
    """Las hojas «Datos del cliente», una por requerimiento con anexo entregado, en el orden de la definición."""
    d = mod.definicion()
    salida, usados = [], set()
    for r in d.get("requests") or []:
        ds = r.get("dataset")
        filas = (datasets or {}).get(ds) if ds else None
        if not filas:
            continue
        campos = _campos_de(mod, ds)
        if not campos:
            claves = [k for k in filas[0] if not str(k).startswith("_")]
            campos = [{"key": k, "label": k, "type": "text"} for k in claves]
        k = len(salida) + 1
        nombre = f"D{k}_{_slug(ds)}"[:31]
        while nombre in usados:
            nombre = nombre[:29] + f"_{k}"
        usados.add(nombre)
        doc = str(r.get("document") or ds).strip()
        guia = f"Documento {r.get('id', '')} · {doc}."
        if r.get("content"):
            guia += " " + str(r["content"]).strip()
        elif r.get("purpose"):
            guia += " Para qué: " + str(r["purpose"]).strip()
        rows = [[_valor(c, f.get(c["key"])) for c in campos] + [_origen(f)] for f in filas]
        salida.append({
            # Rótulo corto (pestaña del HTML y del Excel); el documento completo va en la guía.
            "name": nombre, "label": f"Datos del cliente · {ds.replace('_', ' ').capitalize()} ({r.get('id', '')})".replace(" ()", ""),
            "cols": [[c.get("label") or c["key"], _FMT.get(c.get("type"), "t")] for c in campos] + [["Origen del dato", "t"]],
            "rows": rows, "total": None, "explica": {}, "guia": guia, "dataset": ds,
        })
    return salida


# --- Enlace de las cédulas con los datos del cliente -----------------------------------------------

def _clave(v):
    """Identificador comparable: texto recortado o número entero como texto (años, números de lote)."""
    v = _v(v)
    if isinstance(v, str) and v.strip() and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
        return v.strip()
    if isinstance(v, (int, float)) and not isinstance(v, bool) and float(v).is_integer() and abs(v) >= 100:
        return str(int(v))
    return None


def _indice(datos: list[dict]) -> dict:
    """identificador de la partida (1.ª columna de la hoja de datos) → [(hoja, fila)]."""
    idx: dict = {}
    for h in datos:
        for i, f in enumerate(h["rows"]):
            k = _clave(f[0]) if f else None
            if k:
                idx.setdefault(k, []).append((h, i))
    return idx


def _norm(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _texto_numero(v) -> bool:
    """Un número que el cliente entregó en una columna de texto (el año de una pérdida: «2019»)."""
    return isinstance(v, str) and bool(re.fullmatch(r"-?[1-9]\d*", v.strip()))


def _igual(a, b) -> bool:
    na, nb = _num(a), _num(b)
    if na is not None and nb is None and _texto_numero(b):
        nb = float(b)
    if na is not None and nb is not None:
        return abs(na - nb) < TOL
    if isinstance(a, str) and isinstance(b, str):
        return a.strip() == b.strip() and bool(a.strip())
    return False


def _enlazable(v) -> bool:
    """Datos que se enlazan: números distintos de cero, fechas y textos (el identificador de la partida,
    que es la clave con que se busca la fila, queda como está: ver ``enlazar``)."""
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return abs(v) >= TOL
    return isinstance(v, str) and bool(v.strip())


_VACIAS = {"de", "del", "la", "las", "el", "los", "en", "y", "o", "a", "al", "por", "para", "con", "sin", "segun", "que",
           "si", "se", "un", "una", "es", "su", "sus", "lo"}


def _palabras(t) -> list:
    return [w for w in _norm(t).split() if w not in _VACIAS and len(w) > 1]


def _misma(a: str, b: str) -> bool:
    """Dos palabras del encabezado son la misma: iguales o con la misma raíz (amort ~ amortización,
    registrado ~ registrada, inicial ~ inicio)."""
    if a == b:
        return True
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n >= 4 and n >= min(len(a), len(b)) - 2


def _parecido(a: str, b: str) -> int:
    """Qué tanto se parecen dos encabezados: 100 si son iguales; si no, cuántas palabras de uno tienen
    su par en el otro (misma raíz). Una sigla («MOD») vale por las iniciales de las palabras del otro."""
    if _norm(a) == _norm(b):
        return 100
    pa, pb = _palabras(a), _palabras(b)
    n = sum(1 for x in pa if any(_misma(x, y) for y in pb))
    for x, otras in ((pa, pb), (pb, pa)):
        for w in x:
            if len(w) >= 2 and len(w) == len(otras) and w == "".join(y[0] for y in otras):
                n = max(n, len(otras))
    return n


def _filas_parejas(fila: list, candidatos: list) -> list:
    """De las filas de datos con el mismo identificador, las que más valores comparten con la fila de la
    cédula (una partida con varias filas —los flujos de un préstamo— se alinea fila con fila)."""
    if len(candidatos) <= 1:
        return candidatos
    vals = [c for c in fila if not isinstance(c, dict) and _enlazable(c)]
    puntaje = [(sum(1 for c in vals if any(_igual(c, d) for d in dh["rows"][i][:-1])), dh, i) for dh, i in candidatos]
    mejor = max(p[0] for p in puntaje)
    return [(dh, i) for p, dh, i in puntaje if p == mejor]


def enlazar(cedulas: list[dict], datos: list[dict]) -> tuple[list[dict], int]:
    """Cédulas con los datos del cliente como fórmula a su hoja de datos, y cuántas celdas se enlazaron.

    Por cada columna de la cédula se elige UNA columna de una hoja de datos (encabezado parecido) que
    tenga el mismo valor en las filas de la misma partida. Se enlaza solo si ninguna fila la contradice:
    si en alguna partida la hoja de datos tiene otro valor, la columna de la cédula es un cálculo que a
    veces coincide con el dato, y queda como estaba. Las filas donde el cliente dejó el dato en blanco
    (la herramienta usó un valor por defecto) conservan su valor."""
    idx = _indice(datos)
    if not idx:
        return cedulas, 0
    total = 0
    salida = []
    for h in cedulas:
        if re.match(r"D\d+_", h.get("name", "")) or not h.get("rows"):
            salida.append(h)
            continue
        enc = [c[0] for c in h.get("cols") or []]
        filas = [list(f) for f in h["rows"]]
        cand = []
        for fila in filas:
            cs = []
            for c in fila:
                k = _clave(c)
                if k and k in idx:
                    cs += [x for x in idx[k] if x not in cs]
            cand.append(_filas_parejas(fila, cs))
        explica, origen, hechos = dict(h.get("explica") or {}), dict(h.get("origen") or {}), {}
        for j in range(len(enc)):
            filas_j = [k for k, fila in enumerate(filas)
                       if cand[k] and j < len(fila) and not isinstance(fila[j], dict) and _enlazable(fila[j])
                       and not (isinstance(fila[j], str) and fila[j].strip() in idx)]
            if not filas_j:
                continue
            # Columnas de datos candidatas: (hoja, columna) con encabezado parecido y el valor en alguna fila.
            destinos = {}
            for k in filas_j:
                for dh, i in cand[k]:
                    for jj, dv in enumerate(dh["rows"][i][:-1]):
                        if _igual(filas[k][j], dv):
                            sc = _parecido(enc[j], dh["cols"][jj][0])
                            if sc:
                                destinos[(dh["name"], jj)] = (sc, dh)
            elegido, mejor = None, None
            for (nombre, jj), (sc, dh) in destinos.items():
                aciertos, contra = [], 0
                for k in filas_j:
                    filas_d = [(d, i) for d, i in cand[k] if d["name"] == nombre]
                    if not filas_d:
                        continue
                    ok = [(d, i) for d, i in filas_d if _igual(filas[k][j], d["rows"][i][jj])]
                    if ok:
                        aciertos.append((k, ok[0][1]))
                    elif any(d["rows"][i][jj] not in (None, "") for d, i in filas_d):
                        contra += 1
                if contra or not aciertos:
                    continue
                extra = len(_palabras(dh["cols"][jj][0])) - sc
                clave_orden = (sc, len(aciertos), -extra)
                if mejor is None or clave_orden > mejor:
                    elegido, mejor, empate = (dh, jj, aciertos), clave_orden, False
                elif clave_orden == mejor:
                    empate = True
            if not elegido or empate:
                continue
            dh, jj, aciertos = elegido
            hoja_d = dh["name"][:31]

            def ref(i, c, hoja_d=hoja_d):
                return f"'{hoja_d}'!{get_column_letter(c + 1)}{FILA0 + i}"

            # Filas donde el cliente dejó el dato en blanco: la herramienta usó otro dato de la misma fila
            # (fecha efectiva = acta o, si no hay acta, el registro) o un valor por defecto.
            con_acierto = {k for k, _ in aciertos}
            vacias = []
            for k in filas_j:
                if k in con_acierto:
                    continue
                filas_d = [i for d, i in cand[k] if d["name"] == dh["name"]]
                if filas_d and all(dh["rows"][i][jj] in (None, "") for i in filas_d):
                    vacias.append((k, filas_d[0]))
            alterna = defecto = None
            if vacias:
                otras = [{c for c, dv in enumerate(dh["rows"][i][:-1])
                          if c != jj and _igual(filas[k][j], dv) and _parecido(enc[j], dh["cols"][c][0])} for k, i in vacias]
                comunes = set.intersection(*otras)
                if len(comunes) == 1:
                    alterna = comunes.pop()
                elif all(_num(filas[k][j]) is not None and _num(filas[k][j]) == _num(filas[vacias[0][0]][j]) for k, _ in vacias):
                    defecto = filas[vacias[0][0]][j]
            # Ceros que el cliente escribió como cero en la columna elegida (no se usan para elegirla: un cero
            # coincide con cualquier columna vacía de importes).
            for k, fila in enumerate(filas):
                c = fila[j] if j < len(fila) else None
                if k in con_acierto or isinstance(c, (bool, dict)) or not isinstance(c, (int, float)) or c != 0:
                    continue
                fd = [i for d, i in cand[k] if d["name"] == dh["name"]]
                if len(fd) == 1 and isinstance(dh["rows"][fd[0]][jj], (int, float)) and dh["rows"][fd[0]][jj] == 0:
                    aciertos.append((k, fd[0]))
            texto = {k for k, i in aciertos if _texto_numero(dh["rows"][i][jj])}
            for k, i in aciertos + (vacias if alterna is not None or defecto is not None else []):
                r = ref(i, jj)
                if alterna is not None:
                    f = f'IF({r}="",{ref(i, alterna)},{r})'
                elif defecto is not None:
                    f = f'IF({r}="",{defecto:g},{r})'
                else:
                    f = f"VALUE({r})" if k in texto else r
                filas[k][j] = {"f": f, "v": filas[k][j]}
                total += 1
            nota = ""
            if alterna is not None:
                nota = f" Si el cliente lo dejó en blanco, se toma «{dh['cols'][alterna][0]}» de la misma fila."
            elif defecto is not None:
                nota = f" Si el cliente lo dejó en blanco, la herramienta usa {defecto:g}."
            hechos[enc[j]] = (dh["label"], dh["cols"][jj][0], nota)
        for col, (lbl, dcol, nota) in hechos.items():
            hoja_txt = f"«{lbl.replace('Datos del cliente · ', '')}»"
            if col not in explica:
                explica[col] = (f"Es el dato que entregó el cliente («{dcol}»): la fórmula lo trae de la hoja de datos {hoja_txt}, "
                                f"de la fila de la misma partida.{nota} Si el dato del cliente cambia, esta cédula cambia con él.")
            origen.setdefault(col, f"hoja «Datos del cliente» {hoja_txt}, columna «{dcol}»")
        salida.append({**h, "rows": filas, "explica": explica, "origen": origen} if hechos else h)
    return salida, total


def con_datos(mod, run: dict, datasets: dict) -> list[dict]:
    """Cédulas del procesador (``mod.hojas``) con los datos del cliente dentro del libro."""
    cedulas = mod.hojas(run)
    pid = getattr(mod, "__name__", "").rsplit(".", 1)[-1]
    if pid in PROPIAS or not datasets:
        return cedulas
    datos = hojas_datos(mod, datasets)
    cedulas, _ = enlazar(cedulas, datos)
    return cedulas + datos
