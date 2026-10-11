"""Extractor de documentos narrativos (Fase 9 — herramienta nueva).

Los documentos narrativos de auditoría (contratos, cartas de control interno,
informes, notas a los EEFF) no tienen parser de casilleros: hoy el motor los
clasifica y los deja en revisión sin datos. Esta capa, **aditiva y sin tocar
ninguna herramienta probada**, extrae de su texto los datos puntuales con
trazabilidad al origen (línea + fragmento), respetando la escalera
determinístico-primero:

- **Determinista (núcleo, sin IA):** fechas, montos (con moneda), RUCs y
  porcentajes por regex + el normalizador canónico del motor. Cada dato lleva su
  evidencia y su confianza. **El LLM no participa en esta capa.**
- **IA (último recurso, opcional):** enumera obligaciones, partes y cláusulas
  —solo TEXTO explícito, nunca cifras— con esquema estricto, tope de confianza
  MEDIUM, disclaimer y degradación graciosa. Usa el proveedor compartido
  (`chat.providers`, local-first), inyectable para pruebas.

Separación extracción↔conclusión: devuelve datos con su confianza; no concluye
nada NIIF ni de auditoría. La incertidumbre nunca se oculta: el dataset narrativo
siempre queda ``review_required`` (extracción best-effort, se verifica contra el
documento).
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable, Optional

from pydantic import BaseModel, Field, ValidationError

from backend.app.ingesta.classifier import clasificar_documento
from backend.app.ingesta.confidence import NivelConfianza, requiere_revision
from backend.app.ingesta.confidence_live import consolidar_confianza
from backend.app.ingesta.contract import (
    CampoExtraido,
    DatasetNormalizado,
    Evidencia,
    MetodoExtraccion,
    TipoDato,
    TipoDocumento,
)
from backend.app.ingesta.normalizer import normalizar_fecha, normalizar_monto
from backend.app.ingesta.semantic_resolver import DISCLAIMER_IA

ChatFn = Callable[..., object]  # compatible con chat.providers.chat_complete

# Extensiones que se leen como texto plano (no PDF): se decodifican directo.
_TEXT_EXT = (".txt", ".md", ".csv", ".json", ".xml", ".htm", ".html", ".text")

# Tope de datos puntuales emitidos (evita payloads enormes en documentos largos).
_MAX_CAMPOS = 200
# Largo del fragmento de evidencia por línea.
_MAX_SOPORTE = 200

# --- Regex deterministas (prioridad de reclamo de spans: RUC > fecha > % > monto) ---
_RE_RUC = re.compile(r"\b\d{13}\b")
_RE_FECHA = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{4}"
    r"|\d{4}[/-]\d{1,2}[/-]\d{1,2}"
    r"|\d{1,2}\s+de\s+[a-záéíóúñ]+\s+de\s+\d{4})\b",
    re.IGNORECASE,
)
# Número que SIEMPRE termina en dígito (no se traga el punto final de la oración).
_NUM = r"-?\d(?:[\d.,]*\d)?"
_RE_PORC = re.compile(rf"{_NUM}\s?%")
_RE_MONTO = re.compile(
    rf"(?:USD|US\$|\$)\s?{_NUM}"                  # símbolo/código delante
    rf"|{_NUM}\s?(?:USD|d[óo]lares)"             # código detrás
    r"|-?\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?"   # con separador de miles
    r"|-?\d+[.,]\d{2}(?![\d.,])",                 # decimal de 2 dígitos
    re.IGNORECASE,
)
_RE_MARCA_USD = re.compile(r"US\$|USD|\$|d[óo]lares", re.IGNORECASE)


def _soporte(linea: str) -> str:
    s = linea.strip()
    return s if len(s) <= _MAX_SOPORTE else s[: _MAX_SOPORTE - 1] + "…"


def _solapa(ini: int, fin: int, claimed: list[tuple[int, int]]) -> bool:
    return any(not (fin <= a or ini >= b) for a, b in claimed)


def extraer_campos_narrativos(texto: str, *, source_file: str) -> list[CampoExtraido]:
    """Extrae datos puntuales (fechas, montos, RUCs, porcentajes) del texto.

    Función pura y determinista: no toca red, PDF ni IA. Cada dato lleva la línea
    y el fragmento donde apareció. Deduplica por (campo, valor, línea) y respeta
    prioridad de spans para no contar una fecha o un RUC como monto.
    """
    campos: list[CampoExtraido] = []
    vistos: set[tuple] = set()

    def emitir(field, raw, valor, tipo, score, metodo, linea_no, linea, *, currency=None):
        clave = (field, str(valor), linea_no)
        if valor is None or clave in vistos:
            return
        vistos.add(clave)
        campos.append(
            CampoExtraido.desde_score(
                document_id=source_file,
                field=field,
                score=score,
                raw_value=raw,
                normalized_value=valor,
                data_type=tipo,
                currency=currency,
                extraction_method=metodo,
                evidence=Evidencia(
                    source_file=source_file, source_row=linea_no, texto_soporte=_soporte(linea)
                ),
            )
        )

    for i, linea in enumerate(texto.splitlines(), start=1):
        if len(campos) >= _MAX_CAMPOS:
            break
        claimed: list[tuple[int, int]] = []

        for m in _RE_RUC.finditer(linea):
            claimed.append(m.span())
            emitir("ruc", m.group(), m.group(), TipoDato.RUC, 0.92,
                   MetodoExtraccion.REGEX, i, linea)

        for m in _RE_FECHA.finditer(linea):
            if _solapa(*m.span(), claimed):
                continue
            f = normalizar_fecha(m.group())
            if f is None:
                continue
            claimed.append(m.span())
            emitir("fecha", m.group(), f.isoformat(), TipoDato.FECHA, 0.90,
                   MetodoExtraccion.REGEX, i, linea)

        for m in _RE_PORC.finditer(linea):
            if _solapa(*m.span(), claimed):
                continue
            v = normalizar_monto(m.group().rstrip("% ").strip())
            if v is None:
                continue
            claimed.append(m.span())
            emitir("porcentaje", m.group(), v, TipoDato.PORCENTAJE, 0.85,
                   MetodoExtraccion.REGEX, i, linea)

        for m in _RE_MONTO.finditer(linea):
            if _solapa(*m.span(), claimed):
                continue
            tok = re.sub(r"(US\$|USD|\$|d[óo]lares)", "", m.group(), flags=re.IGNORECASE).strip()
            v = normalizar_monto(tok)
            if v is None:
                continue
            claimed.append(m.span())
            currency = "USD" if _RE_MARCA_USD.search(m.group()) else None
            emitir("monto", m.group().strip(), v, TipoDato.MONEDA, 0.70,
                   MetodoExtraccion.REGEX, i, linea, currency=currency)

    return campos[:_MAX_CAMPOS]


# --------------------------------------------------------------------------- #
#  Capa IA opcional: enumera obligaciones / partes / cláusulas (solo texto)    #
# --------------------------------------------------------------------------- #
_IA_SISTEMA = (
    "Eres un asistente de auditoría que extrae SOLO lo explícito de un documento. "
    "Devuelve exclusivamente JSON válido. Enumera obligaciones, partes (con su rol) "
    "y cláusulas clave tal como están escritas. NO inventes ni calcules cifras, "
    "montos, fechas ni porcentajes (esos se extraen aparte de forma determinista). "
    "NO concluyas nada contable ni tributario. Si no estás seguro, usa confianza baja."
)

_IA_TIPOS = {"obligacion", "parte", "clausula", "otro"}
_IA_MAP_CONFIANZA = {  # tope MEDIUM: la IA nunca sube a HIGH automático
    "alta": NivelConfianza.MEDIUM,
    "media": NivelConfianza.LOW,
    "baja": NivelConfianza.REVIEW_REQUIRED,
}
_IA_MAX_ITEMS = 60


class _ItemNarrativoIA(BaseModel):
    tipo: str = "otro"
    texto: str = Field(min_length=1)
    rol: Optional[str] = None


class _SalidaNarrativaIA(BaseModel):
    items: list[_ItemNarrativoIA] = Field(default_factory=list)
    confianza: str = Field(default="baja", pattern="^(alta|media|baja)$")


def _ia_parse_json(content: str) -> dict:
    s = (content or "").strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s.strip("`")
        if s.lstrip().lower().startswith("json"):
            s = s.lstrip()[4:]
    return json.loads(s)


def _ia_prompt(texto: str) -> str:
    recorte = texto if len(texto) <= 12000 else texto[:12000] + "\n…[texto truncado]"
    return (
        "Extrae de este documento de auditoría las obligaciones, las partes "
        "(con su rol) y las cláusulas clave, SOLO como están escritas.\n\n"
        f"DOCUMENTO:\n{recorte}\n\n"
        'Devuelve SOLO este JSON:\n'
        '{"items": [{"tipo": "obligacion|parte|clausula|otro", "texto": <texto literal>, '
        '"rol": <rol o null>}], "confianza": "alta|media|baja"}'
    )


def enriquecer_con_ia(
    texto: str,
    source_file: str,
    *,
    chat_fn: Optional[ChatFn] = None,
    max_reintentos: int = 2,
) -> tuple[list[CampoExtraido], Optional[str]]:
    """Enumera obligaciones/partes/cláusulas por IA (solo texto explícito).

    Devuelve ``(campos, advertencia)``. Nunca lanza: ante proveedor caído o JSON
    inválido tras reintentos, devuelve ``([], mensaje)`` para que el dataset lo
    registre como advertencia (degradación graciosa). Los campos salen con
    método IA, tope de confianza MEDIUM y disclaimer; nunca numéricos.
    """
    if not (texto or "").strip():
        return [], None
    if chat_fn is None:
        def chat_fn(messages, system=None, **kw):  # import perezoso
            from backend.app.chat.providers import chat_complete
            return chat_complete(messages, system=system)

    prompt = _ia_prompt(texto)
    ultimo = ""
    for _ in range(max_reintentos + 1):
        try:
            resp = chat_fn([{"role": "user", "content": prompt}], system=_IA_SISTEMA)
            data = _ia_parse_json(getattr(resp, "content", "") or "")
            salida = _SalidaNarrativaIA.model_validate(data)
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            ultimo = f"{type(e).__name__}: {e}"
            continue
        except Exception as e:  # proveedor caído, red, etc.
            return [], f"enriquecimiento IA no disponible: {type(e).__name__}: {e}"
        nivel = _IA_MAP_CONFIANZA.get(salida.confianza, NivelConfianza.REVIEW_REQUIRED)
        modelo = getattr(resp, "model", "?")
        campos: list[CampoExtraido] = []
        for it in salida.items[:_IA_MAX_ITEMS]:
            tipo = it.tipo if it.tipo in _IA_TIPOS else "otro"
            texto_item = it.texto.strip()
            if not texto_item:
                continue
            campos.append(
                CampoExtraido(
                    document_id=source_file,
                    field=tipo,
                    raw_value=texto_item,
                    normalized_value=(f"{it.rol}: {texto_item}" if it.rol else texto_item),
                    data_type=TipoDato.TEXTO,  # el LLM no calcula: siempre texto
                    confidence=nivel,
                    extraction_method=MetodoExtraccion.IA,
                    review_required=requiere_revision(nivel),
                    evidence=Evidencia(
                        source_file=source_file,
                        texto_soporte="(IA) " + _soporte(texto_item),
                    ),
                    warnings=[DISCLAIMER_IA, f"enumerado por IA (modelo={modelo}, confianza={salida.confianza})"],
                )
            )
        return campos, None

    return [], f"enriquecimiento IA: salida inválida tras reintentos ({ultimo})"


# --------------------------------------------------------------------------- #
#  Orquestación del extractor narrativo                                        #
# --------------------------------------------------------------------------- #
def _texto_de(contenido: bytes, filename: str, extraer_texto_fn) -> tuple[str, MetodoExtraccion, Optional[str]]:
    ext = os.path.splitext(filename)[1].lower()
    if ext in _TEXT_EXT:
        return contenido.decode("utf-8", "ignore"), MetodoExtraccion.NATIVO, None
    if extraer_texto_fn is None:
        from backend.app.ingesta.ocr_support import extraer_texto as extraer_texto_fn
    td = extraer_texto_fn(contenido, filename)
    nota = None if getattr(td, "disponible", True) else getattr(td, "nota", None)
    return getattr(td, "texto", "") or "", getattr(td, "metodo", MetodoExtraccion.NATIVO), nota


def extraer_narrativo(
    filename: str,
    contenido: bytes,
    *,
    tipo_declarado: Optional[str] = None,
    usar_ia: bool = False,
    chat_fn: Optional[ChatFn] = None,
    extraer_texto_fn=None,
    texto: Optional[str] = None,
    sellar: bool = True,
) -> DatasetNormalizado:
    """Ingiere un documento narrativo y devuelve el dataset de datos puntuales.

    Nunca lanza. Determinístico primero: la IA (``usar_ia``) solo se suma sobre
    el TEXTO para enumerar obligaciones/partes/cláusulas; los numéricos salen
    siempre de la capa determinista.
    """
    clasificacion = clasificar_documento(filename, contenido=contenido, tipo_declarado=tipo_declarado)
    metodo_texto = MetodoExtraccion.NATIVO
    nota_texto: Optional[str] = None
    if texto is None:
        texto, metodo_texto, nota_texto = _texto_de(contenido, filename, extraer_texto_fn)

    campos = extraer_campos_narrativos(texto or "", source_file=filename)
    warnings: list[str] = [
        f"clasificación={clasificacion.tipo.value} ({clasificacion.confidence.value})",
        "extracción narrativa best-effort: verificar los datos contra el documento",
    ]
    if nota_texto:
        warnings.append(nota_texto)
    if not (texto or "").strip():
        warnings.append("no se obtuvo texto del documento (¿escaneado sin OCR disponible?)")

    if usar_ia:
        campos_ia, aviso = enriquecer_con_ia(texto or "", filename, chat_fn=chat_fn)
        campos.extend(campos_ia)
        if aviso:
            warnings.append(aviso)

    schema = sorted({c.field for c in campos})
    quality = 0.0 if not campos else 0.6
    ds = DatasetNormalizado(
        dataset_id=filename,
        source_file=filename,
        document_type=clasificacion.tipo,
        schema_detected=schema,
        schema_normalized=schema,
        campos=campos,
        quality_score=quality,
        extraction_method=metodo_texto,
        warnings=warnings,
        review_required=True,  # narrativo: siempre se verifica contra el documento
    )
    consolidar_confianza(ds)
    return ds.sellar() if sellar else ds
