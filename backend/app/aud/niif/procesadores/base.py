"""Piezas comunes de los procesadores de pruebas NIIF (contrato en docs/niif/CONTRATO_PROCESADOR.md).

Todo procesador nuevo importa de aquí: lectura de números y fechas en formato local, mapeo de
filas, validación por campos, celdas con fórmula para el Excel y ayudas de redondeo. Así las 18
herramientas del catálogo leen, validan y escriben igual.
"""
from __future__ import annotations

import re
from datetime import date

from backend.app.aud.niif.procesadores.perdidas_incurridas_s11 import (  # noqa: F401  (se re-exportan)
    FILA0, _fx as fx, _m as m, _n as n2, a_fecha, a_num, filas_mapeadas, fin_mes, norm, r2,
)

MARCO_COMPLETAS = "NIIF completas"
MARCO_PYMES = "NIIF para las PYMES"


def campo(key, label, tipo="text", requerido=True, alias=(), ejemplo=None) -> dict:
    """Definición de una columna de un anexo (el modelo Excel y el mapeo salen de aquí)."""
    c = {"key": key, "label": label, "type": tipo, "required": requerido, "aliases": list(alias)}
    if ejemplo is not None:
        c["example"] = ejemplo
    return c


def validar_campos(campos: list, filas: list, unico: str | None = "id") -> dict:
    """Faltantes, números y fechas ilegibles, filas de total y claves repetidas (aviso)."""
    errores, avisos, vistos = [], [], {}
    for f in filas:
        fila = f.get("_row")
        for c in campos:
            v = str(f.get(c["key"], "") or "").strip()
            if c.get("required") and not v:
                errores.append({"row": fila, "field": c["key"], "message": f"Falta {c['label']}."})
            elif v and c["type"] == "number" and a_num(v) is None:
                errores.append({"row": fila, "field": c["key"], "message": f"{c['label']}: número inválido."})
            elif v and c["type"] == "date" and a_fecha(v) is None:
                errores.append({"row": fila, "field": c["key"], "message": f"{c['label']}: fecha inválida."})
        if re.match(r"^(total|subtotal)\b", str(f.get("id", "")), re.I):
            errores.append({"row": fila, "message": "Fila de total o subtotal: prepare un anexo de detalle."})
        if unico:
            k = str(f.get(unico, "")).strip().lower()
            if k:
                if k in vistos:
                    avisos.append({"row": fila, "message": f"Identificador repetido: {f.get(unico)} (también en la fila {vistos[k]})."})
                vistos.setdefault(k, fila)
    return {"records": len(filas), "errors": errores, "warnings": avisos, "ok": not errores}


def num(v, defecto=0.0) -> float:
    """Número de una celda; vacío → defecto. Para importes obligatorios validar antes."""
    x = a_num(v)
    return defecto if x is None else float(x)


def fecha(v):
    return a_fecha(v)


def es_pymes(parametros: dict) -> bool:
    return MARCO_PYMES.lower() in str((parametros or {}).get("_marco") or "").lower()


def edicion_pymes(parametros: dict) -> str:
    """«2025» o «2015» según la ficha del encargo (por defecto 2015 hasta 2026)."""
    e = str((parametros or {}).get("_edicion") or "")
    return "2025" if "2025" in e else "2015"


def problema(code: str, mensaje: str, importe=0) -> dict:
    # El auditor ve «pendiente de verificar vigencia», no la marca interna «VERIFICAR».
    mensaje = mensaje.replace("VERIFICAR", "pendiente de verificar vigencia")
    return {"code": code, "message": mensaje, "amount": r2(importe or 0)}


def hoja(name: str, label: str, cols: list, rows: list, total=None, explica: dict | None = None,
         guia: str | None = None, ocultas: list | None = None, origen: dict | None = None,
         estilos: list | None = None, colores: list | None = None) -> dict:
    """Cédula: cols = [[título, formato]] con formato t/n/p/i/d/x; celdas calculadas con fx().

    ``explica`` = {título de columna calculada: explicación en lenguaje sencillo}.
    Es la explicación HUMANA que muestra el bloque «Cómo se calcula esta hoja»
    (Excel, Word, HTML y PDF): qué hace la columna, con qué datos y de qué hoja,
    como se lo contaría el auditor a un cliente. Toda columna con fórmula debe
    tenerla (lo exigen ``tests/test_aud_html_premium.py`` y
    ``scripts/verificar_explicaciones.py``).

    ``guia`` = «¿De dónde saco este dato?»: qué documento, reporte, cuenta y fecha
    alimenta la hoja (va en la fila 3 del Excel). Obligatoria en las hojas de datos
    del cliente (``D1_…``).
    ``ocultas`` = columnas técnicas (claves de cruce) que el Excel agrupa y oculta.
    ``origen`` = {columna: texto} para reemplazar el «De dónde viene el dato» que se
    deduce de la fórmula (cuando cada fila remite a una hoja distinta).
    ``estilos`` = una entrada por fila (o None): {"tipo": "titulo" | "total" | "control",
    "sangria": n, "col": nombre de la columna que lleva la sangría, "grupo": n (nivel de agrupación de la fila
    en el Excel, para elegir el detalle con los botones de esquema)}. Da a una hoja el aspecto
    de cédula sumaria (rubro en negrita, subcuentas con sangría, total y cuadre) en Excel,
    HTML, Word y PowerPoint.
    ``colores`` = columnas cuyo valor es un nivel, severidad, semáforo o estado (Alto, Medio, Bajo,
    Significativo, Rojo, Crítico, Conforme…): cada celda se pinta según ``NIVEL_COLOR`` en el Excel
    (formato condicional, sigue a la fórmula), el HTML, el Word y el PowerPoint."""
    h = {"name": name, "label": label, "cols": cols, "rows": rows, "total": total, "explica": dict(explica or {})}
    if guia:
        h["guia"] = guia
    if ocultas:
        h["ocultas"] = list(ocultas)
    if origen:
        h["origen"] = dict(origen)
    if estilos:
        h["estilos"] = list(estilos)
    if colores:
        h["colores"] = [c for c in colores if c in [x[0] for x in cols]]
    return h


# Rol de color de cada nivel. Se compara el texto completo o su primera palabra seguida de espacio
# («Rojo · No significativo…», «Pendiente de calificación»).
NIVEL_COLOR = {
    "Significativo": "sig",
    "Alto": "alta", "Alta": "alta", "Crítico": "alta", "Rojo": "alta",
    "Medio": "media", "Media": "media", "Revisar": "media", "Amarillo": "media",
    "Bajo": "baja", "Baja": "baja", "Conforme": "baja", "Verde": "baja",
    "Pendiente": "info", "No evaluado": "info", "No significativo": "info",
    "Empeora": "alta", "Mejora": "baja",
}
# Rol → (relleno, texto) en hexadecimal sin «#». Tonos de estado (no se usan en los gráficos).
ROL_COLOR = {
    "sig": ("991B1B", "FFFFFF"),
    "alta": ("FDE2E2", "991B1B"),
    "media": ("FEF3C7", "92400E"),
    "baja": ("DCFCE7", "166534"),
    "info": ("E5E7EB", "374151"),
}


def rol_color(h: dict, columna: str, valor) -> str | None:
    """Rol de color de la celda (``None`` si la columna no se pinta o el valor no es un nivel)."""
    if columna not in (h.get("colores") or []):
        return None
    v = valor.get("v") if isinstance(valor, dict) else valor
    if not isinstance(v, str):
        return None
    v = v.strip()
    for clave, rol in NIVEL_COLOR.items():
        if v == clave or v.startswith(clave + " "):
            return rol
    return None


def estilo_fila(h: dict, i: int) -> dict:
    """Estilo de la fila i de datos de la cédula ({} si no tiene)."""
    e = h.get("estilos") or []
    return (e[i] if i < len(e) else None) or {}


def suma(col: str, fin_fila: int, valor) -> dict:
    return fx(f"SUM({col}{FILA0}:{col}{max(fin_fila, FILA0)})", n2(valor))


def ref(hoja_nombre: str) -> str:
    """Prefijo de referencia a otra hoja: '05_Detalle'!"""
    return f"'{hoja_nombre}'!"


def dias(a: date | None, b: date | None):
    return None if a is None or b is None else (a - b).days


def req(id, doc, ds, proc, purpose, required=True, formats=("xlsx", "csv"), use="calculo", content=""):
    """Requerimiento al cliente; `ds` = anexo de cálculo (None si es soporte)."""
    r = {"id": id, "document": doc, "formats": list(formats), "purpose": purpose, "procedure": proc,
         "required": required, "use": use}
    if ds:
        r["dataset"] = ds
    if content:
        r["content"] = content
    return r


def validar_definicion_generica(d: dict, datasets: tuple, principal: str) -> dict:
    ds = [r.get("dataset") for r in d.get("requests") or [] if r.get("dataset")]
    if principal not in ds or len(ds) != len(set(ds)) or any(x not in datasets for x in ds):
        raise ValueError(f"La definición necesita un requerimiento por anexo y el principal ({principal}).")
    if not str(d.get("name") or "").strip() or not str(d.get("area") or "").strip():
        raise ValueError("Indique nombre y rubro de la herramienta.")
    return d
