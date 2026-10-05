"""Ruteo de dos niveles del agente AUDIT-IA (asistente 24/7 para clientes).

El agente de la landing no debe pagar un modelo caro para una pregunta simple ni
quedarse corto en una consulta de juicio contable. Por eso enruta cada mensaje a
uno de dos niveles:

  - ``consulta``     → modelo barato y rápido (por defecto DeepSeek ``deepseek-flash``).
                       Cubre FAQ, lookups sobre fuentes (RAG), fechas de vencimiento,
                       "¿qué cuenta uso para…?", saludos, etc. Es el 80–90 % del tráfico.
  - ``razonamiento`` → modelo fuerte (por defecto DeepSeek ``deepseek-v4-pro``).
                       Juicio contable/tributario complejo, casos ambiguos de NIIF/SRI,
                       varios pasos de análisis, comparaciones y recomendaciones.

El clasificador es **heurístico y determinista** (sin llamada LLM extra: cuesta 0 y
no añade latencia). Ante la duda, escala a ``razonamiento`` — es preferible pagar un
poco más que dar un criterio flojo a un cliente.

Todo es configurable por env var (lo controla el dueño desde Render) sin tocar código:

    AGENTE_PROVEEDOR_CONSULTA        (default "deepseek")
    AGENTE_MODELO_CONSULTA           (default "deepseek-flash")
    AGENTE_PROVEEDOR_RAZONAMIENTO    (default "deepseek")
    AGENTE_MODELO_RAZONAMIENTO       (default "deepseek-v4-pro")

El modelo forzado aplica solo al proveedor elegido; si ese proveedor estuviera caído,
``chat_complete`` sigue cayendo por la cadena de respaldo habitual (nunca se queda
mudo). Así el ruteo optimiza costo/calidad sin sacrificar la resiliencia M16.
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass

from backend.app.chat.providers import LLMResponse, chat_complete

CONSULTA = "consulta"
RAZONAMIENTO = "razonamiento"


# --- Señales de que la pregunta pide razonamiento, no una consulta simple -----
# Verbos/expresiones de análisis, juicio o cálculo encadenado. Si aparece alguna,
# el mensaje se escala al modelo fuerte.
_SENALES_RAZONAMIENTO = (
    "analiza", "analizar", "analice", "analisis",
    "evalua", "evaluar", "evalue", "evaluacion",
    "compara", "comparar", "compare", "comparacion",
    "recomienda", "recomendar", "recomendacion", "recomiendas",
    "por que", "porque", "explica por", "explicame por",
    "justifica", "justificar", "argumenta", "sustenta", "fundamenta",
    "conviene", "deberia", "debo", "me conviene", "cual es mejor",
    "ventajas y desventajas", "pros y contras",
    "como registro", "como contabilizo", "como declaro", "como trato",
    "tratamiento contable", "tratamiento tributario", "asiento contable",
    "interpreta", "interpretar", "implicacion", "implicaciones", "impacto",
    "calcula", "calcular", "determina el", "proyecta", "estima",
    "diagnostica", "diagnostico", "estrategia", "planifica",
    "que pasa si", "que sucede si", "escenario", "simula",
    "diferencia entre", "en que se diferencia",
    "optimiza", "minimiza", "maximiza",
)

# Marcadores de pregunta simple/consulta. Solo bajan el nivel cuando NO hay ninguna
# señal de razonamiento (el razonamiento manda).
_SENALES_CONSULTA = (
    "cuando", "que dia", "que fecha", "hasta cuando", "plazo", "vencimiento",
    "cual es el codigo", "que casillero", "donde queda", "donde encuentro",
    "que significa", "que es", "definicion de",
    "hola", "buenas", "buenos dias", "buenas tardes", "gracias", "ok",
)

# Umbral de longitud: una pregunta muy larga suele traer contexto para razonar.
_MAX_PALABRAS_CONSULTA = 60


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar señales sin depender de acentos."""
    texto = texto.lower()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return texto


def clasificar(texto: str) -> str:
    """Devuelve ``CONSULTA`` o ``RAZONAMIENTO`` para un mensaje del usuario.

    Determinista y barato (sin LLM). Regla: si hay señal de análisis/juicio, o el
    texto es largo, es ``razonamiento``; si hay señal clara de consulta simple y
    ninguna de razonamiento, es ``consulta``. Ante la duda, ``razonamiento`` (más
    vale pasarse de cuidadoso con un cliente que quedarse corto).
    """
    norm = _normalizar(texto or "")
    if not norm.strip():
        return CONSULTA  # vacío/saludo: no gastes el modelo fuerte

    tiene_razonamiento = any(s in norm for s in _SENALES_RAZONAMIENTO)
    if tiene_razonamiento:
        return RAZONAMIENTO

    # Texto largo = probablemente trae contexto a analizar.
    if len(norm.split()) > _MAX_PALABRAS_CONSULTA:
        return RAZONAMIENTO

    tiene_consulta = any(s in norm for s in _SENALES_CONSULTA)
    if tiene_consulta:
        return CONSULTA

    # Una sola pregunta corta sin señales de análisis: tratarla como consulta.
    if norm.count("?") <= 1:
        return CONSULTA

    # Varias preguntas encadenadas sin marcador simple: mejor razonar.
    return RAZONAMIENTO


def _ult_mensaje_usuario(messages: list[dict]) -> str:
    for m in reversed(messages or []):
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


def _proveedor_y_modelo(nivel: str) -> tuple[str, str]:
    if nivel == RAZONAMIENTO:
        prov = os.getenv("AGENTE_PROVEEDOR_RAZONAMIENTO", "deepseek").strip().lower()
        modelo = os.getenv("AGENTE_MODELO_RAZONAMIENTO", "deepseek-v4-pro").strip()
    else:
        prov = os.getenv("AGENTE_PROVEEDOR_CONSULTA", "deepseek").strip().lower()
        modelo = os.getenv("AGENTE_MODELO_CONSULTA", "deepseek-flash").strip()
    return prov, modelo


@dataclass
class RespuestaAgente:
    """Respuesta del agente con la traza del ruteo (para auditar costo/calidad)."""
    contenido: str
    nivel: str          # "consulta" | "razonamiento"
    proveedor: str      # proveedor que se intentó primero
    modelo_pedido: str  # modelo que se forzó al proveedor preferido
    modelo_usado: str   # modelo que respondió de verdad (puede diferir si hubo respaldo)


def nivel_de(messages: list[dict]) -> str:
    """Nivel que tomaría el ruteo para esta conversación (último turno del usuario)."""
    return clasificar(_ult_mensaje_usuario(messages))


def responder_agente(
    messages: list[dict],
    system: str | None = None,
    *,
    temperature: float | None = None,
    forzar_nivel: str | None = None,
) -> RespuestaAgente:
    """Punto de entrada del agente: clasifica el último turno y responde con el
    modelo del nivel correspondiente, con failover a la cadena habitual.

    ``forzar_nivel`` permite saltarse el clasificador (p. ej. la UI marca un chat
    como "modo análisis"). Si no, se deduce del mensaje.
    """
    nivel = forzar_nivel if forzar_nivel in (CONSULTA, RAZONAMIENTO) else nivel_de(messages)
    proveedor, modelo = _proveedor_y_modelo(nivel)
    resp: LLMResponse = chat_complete(
        messages,
        system,
        temperature=temperature,
        preferir=proveedor,
        modelo=modelo,
    )
    return RespuestaAgente(
        contenido=resp.content,
        nivel=nivel,
        proveedor=proveedor,
        modelo_pedido=modelo,
        modelo_usado=resp.model,
    )
