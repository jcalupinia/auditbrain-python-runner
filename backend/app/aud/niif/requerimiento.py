"""Requerimiento de información estructurado en ítems, y su cobertura.

Puerto a Python de `lib/requirement.mjs` del sitio AuditBrain. A diferencia
del motor de cálculo —que se vendoriza tal cual porque ya era Python— esta
lógica solo existía en JavaScript, así que aquí hay una segunda copia.

Para que las dos no diverjan, `tests/test_aud_niif_requerimiento.py` repite
**los mismos casos** que las comprobaciones ejecutables del final de
`lib/requirement.mjs` (`node lib/requirement.mjs`), con las mismas
aserciones. Si alguien cambia una de las dos reglas sin la otra, uno de los
dos lados se pone rojo.

La pieza que justifica todo el módulo son los **componentes**: un mayor
general entregado por mes son doce componentes de un mismo ítem. Sin
declararlos, doce archivos sueltos se ven igual que uno y nadie nota que
falta abril (Manual §08).
"""
from __future__ import annotations

import re

FORMATS = ("xlsx", "csv", "pdf", "txt", "md", "xml", "docx", "zip", "png", "jpg", "jpeg", "webp")

MAX_ITEMS = 40
MAX_COMPONENTS = 60
MAX_COLUMNS = 60


def _clean(value, max_len: int) -> str:
    text = re.sub(r"\s+", " ", str(value if value is not None else "").strip())
    if not text or len(text) > max_len:
        raise ValueError(f"Texto vacío o superior a {max_len} caracteres.")
    return text


def _dedupe(values):
    """Quita repetidos conservando el orden de llegada."""
    return list(dict.fromkeys(values))


def parse_items(raw) -> list[dict]:
    """Normaliza y valida la lista de ítems que llega del formulario."""
    if not isinstance(raw, list) or not raw or len(raw) > MAX_ITEMS:
        raise ValueError(f"Defina entre 1 y {MAX_ITEMS} ítems de requerimiento.")
    vistos: set[str] = set()
    items = []
    for indice, entrada in enumerate(raw):
        entrada = entrada or {}
        text = _clean(entrada.get("text"), 2000)
        if text.lower() in vistos:
            raise ValueError(f"Ítem repetido: {text}")
        vistos.add(text.lower())

        formats = _dedupe(str(f).lower().lstrip(".") for f in (entrada.get("formats") or []))
        if not formats:
            raise ValueError(f"Indique al menos un formato aceptado para: {text}")
        invalido = next((f for f in formats if f not in FORMATS), None)
        if invalido:
            raise ValueError(f"Formato no admitido ({invalido}) en: {text}")

        components = _dedupe(_clean(c, 120) for c in (entrada.get("components") or []))
        if len(components) > MAX_COMPONENTS:
            raise ValueError(f"Máximo {MAX_COMPONENTS} componentes en: {text}")

        columns = _dedupe(_clean(c, 120) for c in (entrada.get("columns") or []))
        if len(columns) > MAX_COLUMNS:
            raise ValueError(f"Máximo {MAX_COLUMNS} columnas en: {text}")

        items.append({
            "id": f"i{indice + 1}",
            "text": text,
            "formats": formats,
            # Obligatorio por defecto: solo un `required: False` explícito lo
            # vuelve opcional.
            "required": entrada.get("required") is not False,
            "components": components,
            "group": _clean(entrada["group"], 120) if entrada.get("group") else "",
            "columns": columns,
            "instructions": _clean(entrada["instructions"], 2000) if entrada.get("instructions") else "",
        })
    return items


def _coincidencias(docs, item_id: str, component=None) -> list:
    # Un documento rechazado por el auditor no cuenta como cobertura: sigue
    # guardado como evidencia de lo recibido, pero no tapa el hueco.
    return [
        d for d in docs
        if d.get("kind") == "source"
        and d.get("itemId") == item_id
        and d.get("state") != "rechazado"
        and (component is None or d.get("component") == component)
    ]


def coverage(items=(), docs=()) -> list[dict]:
    """Estado de cobertura por ítem.

    `pending` lista lo que falta: el ítem completo cuando no tiene
    componentes, o los componentes ausentes cuando sí los tiene.
    """
    estado = []
    for item in items:
        recibidos = len(_coincidencias(docs, item["id"]))
        if not item["components"]:
            estado.append({
                "id": item["id"], "text": item["text"], "required": item["required"],
                "received": recibidos, "expected": 1,
                "pending": [] if recibidos else [item["text"]],
                "complete": recibidos > 0,
            })
            continue
        faltantes = [c for c in item["components"] if not _coincidencias(docs, item["id"], c)]
        estado.append({
            "id": item["id"], "text": item["text"], "required": item["required"],
            "received": recibidos, "expected": len(item["components"]),
            "pending": faltantes, "complete": not faltantes,
        })
    return estado


def _describir(c: dict) -> str:
    # Un ítem sin componentes se nombra solo: repetir su texto como
    # "componente faltante" no informa de nada.
    if c["expected"] == 1:
        return c["text"]
    if len(c["pending"]) == c["expected"]:
        return f"{c['text']}: falta todo (0 de {c['expected']})"
    return f"{c['text']}: faltan {', '.join(c['pending'])}"


def gaps(items=(), docs=()) -> list[str]:
    """Qué impide avanzar.

    Los ítems opcionales nunca bloquean. Los que comparten `group` son fuentes
    alternativas: basta cubrir una para dar el grupo por satisfecho (por
    ejemplo, costos por ítem O estado de resultados con su base de asignación).
    """
    items = list(items)
    estado = [dict(c, group=items[i].get("group") or "") for i, c in enumerate(coverage(items, docs))]
    sueltos = [_describir(c) for c in estado if not c["group"] and c["required"] and not c["complete"]]

    grupos: dict[str, list[dict]] = {}
    for c in estado:
        if c["group"]:
            grupos.setdefault(c["group"], []).append(c)

    por_grupo = []
    for nombre, miembros in grupos.items():
        if any(m["complete"] for m in miembros):
            continue
        if not any(m["required"] for m in miembros):
            continue
        alternativas = " o ".join(m["text"] for m in miembros)
        por_grupo.append(f"{nombre}: entregue una de estas fuentes — {alternativas}")
    return sueltos + por_grupo


def template_csv(item) -> str | None:
    """Plantilla CSV con las columnas que el ítem espera.

    Se genera del propio ítem: no hay archivos que mantener ni que se
    desactualicen.
    """
    columnas = (item or {}).get("columns") or []
    if not columnas:
        return None
    cabecera = ",".join('"' + str(c).replace('"', '""') + '"' for c in columnas)
    instrucciones = (item or {}).get("instructions") or ""
    nota = "# " + " ".join(instrucciones.splitlines()) + "\n" if instrucciones else ""
    return nota + cabecera + "\n"


def check_upload(items, item_id: str, component, filename: str) -> dict:
    """Valida un archivo contra el ítem al que se lo vincula."""
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        raise ValueError("Vincule el archivo a un ítem del requerimiento.")
    ext = str(filename).rsplit(".", 1)[-1].lower() if "." in str(filename) else ""
    if ext not in item["formats"]:
        admitidos = ", ".join(item["formats"]).upper()
        raise ValueError(f'"{item["text"]}" admite {admitidos}. Recibido: {ext or "sin extensión"}.')
    if item["components"]:
        if not component:
            cuales = ", ".join(item["components"])
            raise ValueError(f'"{item["text"]}" se entrega por componentes. Indique cuál: {cuales}.')
        if component not in item["components"]:
            raise ValueError(f'Componente no declarado en "{item["text"]}": {component}.')
    elif component:
        raise ValueError(f'"{item["text"]}" no se entrega por componentes.')
    return item
