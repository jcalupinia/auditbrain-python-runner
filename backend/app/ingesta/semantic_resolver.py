"""AI Semantic Resolver (Fase 6).

Último recurso de la escalera determinístico-primero: cuando un campo quedó en
la cola de revisión por **ambigüedad semántica** (texto no estructurado,
clasificación dudosa), la IA ayuda a desambiguarlo. Nunca antes: si Python,
los parsers, los regex o el OCR ya resolvieron el dato, la IA no interviene.

Reglas duras (del CLAUDE.md y del prompt maestro):

- **El LLM no calcula.** La IA NO fabrica cifras: los campos numéricos
  (moneda, decimal, entero, porcentaje) y las fechas NO se resuelven por IA —
  quedan para revisión humana. La IA solo desambigua TEXTO / DESCONOCIDO.
- **Separar extracción de conclusión.** El resolutor devuelve un dato
  desambiguado con su confianza; no emite conclusiones NIIF ni de auditoría.
- **No ocultar la incertidumbre.** La IA nunca sube la confianza a `HIGH`
  automáticamente (tope `MEDIUM`); si el modelo no está seguro, el campo sigue
  en `REVIEW_REQUIRED`.

Controles sobre la salida del modelo (eco de `ict/audit/interpreter.py`):
validación de esquema Pydantic, reintentos acotados, degradación graciosa,
confianza autorreportada y `requiere_revision_humana`. Todo es inyectable
(`chat_fn`) para probarlo sin red ni proveedor real.
"""
from __future__ import annotations

import json
from typing import Callable, Optional

from pydantic import BaseModel, Field, ValidationError

from backend.app.ingesta.confidence import NivelConfianza, requiere_revision
from backend.app.ingesta.contract import (
    CampoExtraido,
    DatasetNormalizado,
    MetodoExtraccion,
    TipoDato,
)

# Disclaimer para cuando una resolución de IA se muestre al auditor.
DISCLAIMER_IA = (
    "Dato desambiguado por IA. Debe ser validado por el auditor responsable "
    "antes de cualquier decisión."
)

# Tipos que la IA puede desambiguar (semánticos, no numéricos).
_RESOLUBLE_TIPOS = frozenset({TipoDato.TEXTO, TipoDato.DESCONOCIDO})

# Tope de confianza para una resolución de IA: nunca HIGH automático.
_MAP_CONFIANZA = {
    "alta": NivelConfianza.MEDIUM,
    "media": NivelConfianza.LOW,
    "baja": NivelConfianza.REVIEW_REQUIRED,
}

_SISTEMA = (
    "Eres un asistente de auditoría que SOLO desambigua texto. Devuelve "
    "exclusivamente un JSON válido. NO inventes cifras ni montos; NO concluyas "
    "nada contable ni tributario. Si no estás seguro, dilo con "
    "requiere_revision_humana=true y confianza baja."
)

ChatFn = Callable[..., object]  # firma compatible con chat.providers.chat_complete


class ResolucionSemantica(BaseModel):
    """Salida estricta del modelo para una desambiguación."""

    valor: Optional[str] = None
    tipo: Optional[str] = None
    confianza: str = Field(pattern="^(alta|media|baja)$")
    razonamiento: str = ""
    requiere_revision_humana: bool = True


def _parse_json(content: str) -> dict:
    s = (content or "").strip()
    if s.startswith("```"):
        # quita cercos ```json ... ```
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s.strip("`")
        if s.lstrip().lower().startswith("json"):
            s = s.lstrip()[4:]
    return json.loads(s)


def _nivel_desde(res: ResolucionSemantica) -> NivelConfianza:
    nivel = _MAP_CONFIANZA.get(res.confianza, NivelConfianza.REVIEW_REQUIRED)
    if res.requiere_revision_humana and not requiere_revision(nivel):
        return NivelConfianza.LOW
    return nivel


def resoluble(campo: CampoExtraido) -> bool:
    """¿Este campo es candidato a resolución por IA?

    Solo si está en revisión y es de tipo semántico (texto/desconocido). Los
    numéricos y fechas NO (el LLM no calcula).
    """
    return campo.review_required and campo.data_type in _RESOLUBLE_TIPOS


def resolver_campo(
    campo: CampoExtraido,
    *,
    chat_fn: Optional[ChatFn] = None,
    contexto: Optional[str] = None,
    max_reintentos: int = 2,
) -> CampoExtraido:
    """Intenta desambiguar un campo de texto dudoso con IA.

    No actúa si el campo no es resoluble (devuelve el campo intacto). Ante
    cualquier fallo del modelo o JSON inválido, degrada con gracia: deja el
    campo como estaba y agrega una advertencia (nunca lanza).
    """
    if not resoluble(campo):
        return campo
    if chat_fn is None:
        def chat_fn(messages, system=None, **kw):  # import perezoso
            from backend.app.chat.providers import chat_complete
            return chat_complete(messages, system=system)

    prompt = _construir_prompt(campo, contexto)
    ultimo_error = ""
    for _ in range(max_reintentos + 1):
        try:
            resp = chat_fn([{"role": "user", "content": prompt}], system=_SISTEMA)
            data = _parse_json(getattr(resp, "content", "") or "")
            res = ResolucionSemantica.model_validate(data)
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            ultimo_error = f"{type(e).__name__}: {e}"
            continue
        except Exception as e:  # proveedor caído, red, etc.
            campo.warnings.append(f"resolutor IA no disponible: {type(e).__name__}: {e}")
            return campo
        return _aplicar(campo, res, resp)

    campo.warnings.append(f"resolutor IA: salida inválida tras reintentos ({ultimo_error})")
    return campo


def _construir_prompt(campo: CampoExtraido, contexto: Optional[str]) -> str:
    return (
        "Desambigua el siguiente campo extraído de un documento de auditoría.\n"
        f"- Campo: {campo.field}\n"
        f"- Valor crudo: {campo.raw_value!r}\n"
        f"- Tipo tentativo: {campo.data_type.value}\n"
        + (f"- Contexto: {contexto}\n" if contexto else "")
        + "\nDevuelve SOLO este JSON:\n"
        '{"valor": <texto desambiguado o null>, "tipo": <tipo o null>, '
        '"confianza": "alta|media|baja", "razonamiento": <breve>, '
        '"requiere_revision_humana": <true|false>}'
    )


def _aplicar(
    campo: CampoExtraido, res: ResolucionSemantica, resp: object
) -> CampoExtraido:
    nivel = _nivel_desde(res)
    if res.valor is not None:
        campo.normalized_value = res.valor
        campo.raw_value = campo.raw_value if campo.raw_value is not None else res.valor
    campo.confidence = nivel
    campo.extraction_method = MetodoExtraccion.IA
    campo.review_required = requiere_revision(nivel)
    modelo = getattr(resp, "model", "?")
    campo.warnings.append(
        f"resuelto por IA (modelo={modelo}, confianza={res.confianza}): {res.razonamiento}"
    )
    return campo


def resolver_dataset(
    ds: DatasetNormalizado,
    *,
    chat_fn: Optional[ChatFn] = None,
    max_reintentos: int = 2,
) -> DatasetNormalizado:
    """Pasa el resolutor por los campos de texto dudosos del dataset.

    No cambia los campos numéricos ni los ya confiables. Recalcula
    ``review_required`` del dataset tras los intentos.
    """
    for campo in ds.campos:
        resolver_campo(campo, chat_fn=chat_fn, max_reintentos=max_reintentos)
    if any(c.review_required for c in ds.campos):
        ds.review_required = True
    return ds
