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

def _indice(datos: list[dict]) -> dict:
    """identificador (texto de la 1.ª columna) → [(hoja, fila)]."""
    idx: dict = {}
    for h in datos:
        for i, f in enumerate(h["rows"]):
            ident = f[0] if f else None
            if isinstance(ident, str) and ident.strip():
                idx.setdefault(ident.strip(), []).append((h, i))
    return idx


def _norm(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _igual(a, b) -> bool:
    na, nb = _num(a), _num(b)
    if na is not None and nb is not None:
        return abs(na - nb) < TOL
    if isinstance(a, str) and isinstance(b, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", a):
        return a == b
    return False


def _enlazable(v) -> bool:
    """Datos que se enlazan: números distintos de cero y fechas (los textos quedan como están)."""
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return abs(v) >= TOL
    return isinstance(v, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v))


_VACIAS = {"de", "del", "la", "las", "el", "los", "en", "y", "o", "a", "al", "por", "para", "con", "sin", "segun", "que",
           "si", "se", "un", "una", "es", "su", "sus", "lo"}


def _palabras(t) -> set:
    return {w[:-1] if len(w) > 4 and w.endswith("s") else w for w in _norm(t).split() if w not in _VACIAS and len(w) > 1}


def _parecido(a: str, b: str) -> int:
    """Qué tanto se parecen dos encabezados: 100 si son iguales; si no, las palabras que comparten."""
    if _norm(a) == _norm(b):
        return 100
    return len(_palabras(a) & _palabras(b))


def _eleccion(c, enc_j, candidatos):
    """(hoja, fila, columna) de la hoja de datos con ese mismo valor y el encabezado más parecido, o None."""
    hit = []
    for dh, i in candidatos:
        for jj, dc in enumerate(dh["rows"][i][:-1]):
            if _igual(c, dc):
                hit.append((_parecido(enc_j, dh["cols"][jj][0]), dh, i, jj))
    if not hit:
        return None
    mejor = max(h[0] for h in hit)
    top = [h for h in hit if h[0] == mejor]
    if mejor == 0 or len({(h[1]["name"], h[3]) for h in top}) != 1 or len(top) != 1:
        return None
    return top[0][1:]


def enlazar(cedulas: list[dict], datos: list[dict]) -> tuple[list[dict], int]:
    """Cédulas con los datos del cliente como fórmula a su hoja de datos, y cuántas celdas se enlazaron.

    Una columna de la cédula se enlaza solo si TODAS sus celdas con dato (en filas de una partida del
    cliente) encuentran su celda en la MISMA columna de la misma hoja de datos, con encabezados
    parecidos. Si alguna no coincide, la columna es un cálculo que a veces da igual al dato, y queda
    como estaba."""
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
                t = _v(c)
                if isinstance(t, str) and t.strip() in idx:
                    cs += idx[t.strip()]
            cand.append(cs)
        explica, origen, hechos = dict(h.get("explica") or {}), dict(h.get("origen") or {}), {}
        for j in range(len(enc)):
            elecciones, destinos = [], set()
            for k, fila in enumerate(filas):
                c = fila[j] if j < len(fila) else None
                if not cand[k] or isinstance(c, dict) or not _enlazable(c):
                    continue
                e = _eleccion(c, enc[j], cand[k])
                if e is None:
                    elecciones = None
                    break
                elecciones.append((k, e))
                destinos.add((e[0]["name"], e[2]))
            if not elecciones or len(destinos) != 1:
                continue
            for k, (dh, i, jj) in elecciones:
                filas[k][j] = {"f": f"'{dh['name'][:31]}'!{get_column_letter(jj + 1)}{FILA0 + i}", "v": filas[k][j]}
                total += 1
            hechos[enc[j]] = (dh["label"], dh["cols"][jj][0])
        for col, (lbl, dcol) in hechos.items():
            hoja_txt = f"«{lbl.replace('Datos del cliente · ', '')}»"
            if col not in explica:
                explica[col] = (f"Es el dato que entregó el cliente («{dcol}»): la fórmula lo trae de la hoja de datos {hoja_txt}, "
                                "de la fila de la misma partida. Si el dato del cliente cambia, esta cédula cambia con él.")
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
