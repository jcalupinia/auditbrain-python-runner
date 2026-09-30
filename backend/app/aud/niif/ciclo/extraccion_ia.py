"""Extracción por IA de documentos narrativos (PDF/Word) a las filas que un
procesador de planificación espera.

Caso de uso: la **carta de control interno** (RQ-004) y el **informe de auditoría
del año anterior** (RQ-005) llegan como documentos firmados (PDF o Word), no como
una tabla transcrita en Excel. Este módulo lee el texto del documento y, con la
Messages API de Anthropic (tool-use con esquema forzado que se deriva de los
``campos`` del procesador), devuelve **las mismas filas** que hoy se transcriben a
mano (una fila por hallazgo / por asunto del informe, con sus columnas).

Reglas que este módulo respeta:

- **La IA solo transcribe lo que el documento dice.** No inventa calificaciones ni
  cifras: si un dato no está en el documento, la celda queda vacía (regla M22 del
  proyecto: sin dato no hay cifra). El auditor revisa y confirma la tabla extraída
  ANTES de que alimente la herramienta (la IA no decide sola).
- **Degradación elegante.** Si ``ANTHROPIC_API_KEY`` no está configurada, la
  extracción está apagada (``NIIF_EXTRACCION_ENABLED=false``) o la llamada falla
  tras los reintentos, se levanta :class:`ExtraccionNoDisponible` con un mensaje
  claro para que el auditor caiga al respaldo (subir la tabla en Excel/CSV).

El motor es **genérico**: recibe la lista de ``campos`` (del procesador) y no conoce
la semántica de la planificación. La normalización y validación finas (p. ej. el
tipo del informe contra ``TIPOS_INFORME``) las hace el consumidor con
``proc.validar_filas``.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

# Modelo por defecto: el mismo que el intérprete del ICT (Sonnet 4.5 verificado en
# producción). Se sobreescribe por env var cuando Anthropic publique uno nuevo, sin
# tocar el código (misma política que ICT_LLM_MODEL).
DEFAULT_MODEL = os.getenv("NIIF_LLM_MODEL", os.getenv("ICT_LLM_MODEL", "claude-sonnet-4-5-20250929"))
DEFAULT_TIMEOUT = float(os.getenv("NIIF_LLM_TIMEOUT", "40.0"))
DEFAULT_MAX_RETRIES = int(os.getenv("NIIF_LLM_MAX_RETRIES", "2"))
MAX_TOKENS = int(os.getenv("NIIF_LLM_MAX_TOKENS", "4096"))
# Recorte del texto que se manda al modelo (los documentos del año anterior son
# cortos; este tope evita costos si alguien sube un PDF gigante por error).
MAX_CHARS = int(os.getenv("NIIF_EXTRACCION_MAX_CHARS", "60000"))
EXTRACCION_ENABLED = os.getenv("NIIF_EXTRACCION_ENABLED", "true").lower() in ("true", "1", "yes")


class ExtraccionError(Exception):
    """La extracción no se pudo completar (texto ilegible, respuesta inválida...)."""


class ExtraccionNoDisponible(ExtraccionError):
    """La IA de extracción no está disponible (sin API key, apagada o sin red)."""


# --------------------------------------------------------------------------- #
#  1 · Texto del documento (PDF / Word / texto plano)                          #
# --------------------------------------------------------------------------- #
def _extension(nombre: str) -> str:
    return (os.path.splitext(str(nombre or ""))[1] or "").lower().lstrip(".")


def texto_de_documento(nombre: str, datos: bytes) -> str:
    """Devuelve el texto plano de un PDF, Word (.docx) o archivo de texto.

    Levanta :class:`ExtraccionError` si el formato no se soporta o si no se pudo
    extraer texto (p. ej. un PDF escaneado sin capa de texto).
    """
    ext = _extension(nombre)
    if ext == "pdf":
        texto = _texto_pdf(datos)
    elif ext == "docx":
        texto = _texto_docx(datos)
    elif ext == "doc":
        raise ExtraccionError(
            "El formato .doc antiguo no se puede leer automáticamente; guárdelo como .docx o .pdf y vuelva a subirlo."
        )
    elif ext in ("txt", "md"):
        texto = datos.decode("utf-8", errors="replace")
    else:
        raise ExtraccionError(f"Formato no soportado para extracción por IA: «.{ext}». Use PDF o Word (.docx).")
    texto = (texto or "").strip()
    if not texto:
        raise ExtraccionError(
            "No se pudo extraer texto del documento. Si es un PDF escaneado (imagen), súbalo con capa de texto "
            "o transcriba los datos en la plantilla Excel."
        )
    return texto


def _texto_pdf(datos: bytes) -> str:
    import io

    partes: list[str] = []
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(datos)) as pdf:
            for pagina in pdf.pages:
                partes.append(pagina.extract_text() or "")
        if any(p.strip() for p in partes):
            return "\n".join(partes)
    except Exception as e:  # pragma: no cover - depende de pdfplumber en runtime
        log.warning("pdfplumber no pudo leer el PDF (%s); intento pypdf", e)
    # Respaldo: pypdf.
    try:
        from pypdf import PdfReader

        lector = PdfReader(io.BytesIO(datos))
        return "\n".join((p.extract_text() or "") for p in lector.pages)
    except Exception as e:  # pragma: no cover
        raise ExtraccionError(f"No se pudo leer el PDF: {e}") from e


def _texto_docx(datos: bytes) -> str:
    import io

    try:
        from docx import Document
    except Exception as e:  # pragma: no cover
        raise ExtraccionError("Falta la librería python-docx para leer archivos Word.") from e
    doc = Document(io.BytesIO(datos))
    lineas: list[str] = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    # Las cartas de control interno suelen traer los hallazgos en tablas: se vuelcan
    # fila por fila (celdas separadas por « | ») para que el modelo las vea.
    for tabla in doc.tables:
        for fila in tabla.rows:
            celdas = [c.text.strip() for c in fila.cells]
            if any(celdas):
                lineas.append(" | ".join(celdas))
    return "\n".join(lineas)


# --------------------------------------------------------------------------- #
#  2 · Esquema de herramienta (tool-use) derivado de los campos del procesador #
# --------------------------------------------------------------------------- #
def _propiedad(campo: dict, enums: dict) -> dict:
    """Propiedad JSON-schema de un campo, con descripción a partir de su etiqueta."""
    desc = str(campo.get("label") or campo["key"])
    if campo.get("example") is not None:
        desc += f" (ej.: {campo['example']})"
    prop: dict[str, Any]
    if campo.get("type") == "number":
        prop = {"type": ["number", "null"], "description": desc}
    else:
        prop = {"type": ["string", "null"], "description": desc}
    if campo["key"] in enums:
        prop["enum"] = list(enums[campo["key"]]) + [None]
    return prop


def _esquema(campos: list, enums: dict) -> dict:
    return {
        "type": "object",
        "properties": {
            "filas": {
                "type": "array",
                "description": "Una entrada por cada fila detectada en el documento.",
                "items": {
                    "type": "object",
                    "properties": {c["key"]: _propiedad(c, enums) for c in campos},
                    "required": [c["key"] for c in campos],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["filas"],
    }


def _prompt(campos: list, instrucciones: str, contexto: str, texto: str) -> str:
    cols = "\n".join(
        f"- {c['key']}: {c.get('label') or c['key']}"
        + (" (número)" if c.get("type") == "number" else "")
        + ("" if c.get("required", True) else " [opcional]")
        + (f" — ej.: {c['example']}" if c.get("example") is not None else "")
        for c in campos
    )
    partes = [
        "Eres un asistente de auditoría que TRANSCRIBE datos de un documento a una tabla estructurada.",
        "Reglas estrictas:",
        "1. Transcribe SOLO lo que el documento dice de forma explícita. NO inventes, deduzcas ni completes datos.",
        "2. Si un dato no aparece en el documento, deja ese campo en null (no pongas 0 ni un valor inventado).",
        "3. Una entrada de la lista por cada fila/ítem real del documento; no agregues filas de total ni de resumen.",
        "4. Respeta los valores permitidos de cada campo cuando se indiquen.",
        "",
        "Columnas a extraer:",
        cols,
    ]
    if instrucciones:
        partes += ["", instrucciones]
    if contexto:
        partes += ["", f"Contexto del encargo: {contexto}"]
    partes += ["", "Documento:", '"""', texto, '"""']
    return "\n".join(partes)


# --------------------------------------------------------------------------- #
#  3 · Cliente Anthropic (inyectable para pruebas)                             #
# --------------------------------------------------------------------------- #
def _cliente_por_defecto():
    if not EXTRACCION_ENABLED:
        raise ExtraccionNoDisponible(
            "La extracción por IA está deshabilitada (NIIF_EXTRACCION_ENABLED=false). "
            "Suba la tabla en Excel/CSV con la plantilla del requerimiento."
        )
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ExtraccionNoDisponible(
            "No hay ANTHROPIC_API_KEY configurada: la extracción por IA no está disponible en este entorno. "
            "Suba la tabla en Excel/CSV con la plantilla del requerimiento."
        )
    try:
        import anthropic
    except Exception as e:  # pragma: no cover
        raise ExtraccionNoDisponible("Falta el SDK de Anthropic en el entorno.") from e
    return anthropic.Anthropic(timeout=DEFAULT_TIMEOUT)


def _tool_use_input(respuesta: Any) -> dict:
    """Extrae el bloque tool_use de una respuesta de la Messages API."""
    for bloque in getattr(respuesta, "content", None) or []:
        if getattr(bloque, "type", None) == "tool_use":
            entrada = getattr(bloque, "input", None)
            if isinstance(entrada, dict):
                return entrada
            if isinstance(entrada, str):
                return json.loads(entrada)
    raise ExtraccionError("La IA no devolvió datos estructurados.")


# --------------------------------------------------------------------------- #
#  4 · API pública                                                            #
# --------------------------------------------------------------------------- #
def extraer_filas(
    campos: list,
    texto: str,
    *,
    instrucciones: str = "",
    enums: Optional[dict] = None,
    contexto: str = "",
    cliente: Any = None,
    modelo: str = "",
) -> dict:
    """Extrae filas estructuradas del ``texto`` según los ``campos`` del procesador.

    Devuelve ``{"rows": [...], "modelo": str, "n": int}``. Cada fila es un dict con
    las mismas claves que produciría la transcripción en Excel (más ``_row``,
    el número de fila 1-based que usa la validación). Levanta
    :class:`ExtraccionNoDisponible` si la IA no está disponible, o
    :class:`ExtraccionError` si la respuesta es inválida.
    """
    enums = enums or {}
    modelo = modelo or DEFAULT_MODEL
    cli = cliente or _cliente_por_defecto()
    texto = texto[:MAX_CHARS]
    esquema = _esquema(campos, enums)
    prompt = _prompt(campos, instrucciones, contexto, texto)
    claves = {c["key"] for c in campos}
    numericos = {c["key"] for c in campos if c.get("type") == "number"}

    error: Optional[Exception] = None
    for intento in range(DEFAULT_MAX_RETRIES):
        try:
            respuesta = cli.messages.create(
                model=modelo,
                max_tokens=MAX_TOKENS,
                tools=[{"name": "registrar_filas", "description": "Registra las filas extraídas del documento.",
                        "input_schema": esquema}],
                tool_choice={"type": "tool", "name": "registrar_filas"},
                messages=[{"role": "user", "content": prompt}],
            )
            entrada = _tool_use_input(respuesta)
            filas = entrada.get("filas")
            if not isinstance(filas, list):
                raise ExtraccionError("La IA no devolvió una lista de filas.")
            rows = [_normalizar_fila(f, claves, numericos, i) for i, f in enumerate(filas, start=1)
                    if isinstance(f, dict)]
            return {"rows": rows, "modelo": modelo, "n": len(rows)}
        except ExtraccionNoDisponible:
            raise
        except Exception as e:  # reintento con backoff exponencial 1s/2s/...
            error = e
            log.warning("Extracción IA falló (intento %d/%d): %s", intento + 1, DEFAULT_MAX_RETRIES, e)
            if intento < DEFAULT_MAX_RETRIES - 1:
                time.sleep(2 ** intento)
    raise ExtraccionError(f"No se pudo extraer la información con la IA: {error}")


def _normalizar_fila(fila: dict, claves: set, numericos: set, n: int) -> dict:
    """Se queda con las claves conocidas, vacía los null y numera la fila."""
    out: dict[str, Any] = {"_row": n}
    for k in claves:
        v = fila.get(k)
        if v is None:
            out[k] = ""
        elif k in numericos and isinstance(v, float) and v.is_integer():
            out[k] = int(v)
        else:
            out[k] = v
    return out
