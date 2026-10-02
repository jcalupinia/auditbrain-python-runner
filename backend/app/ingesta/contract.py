"""Contrato de datos común del Motor de Ingesta y Normalización.

Es el esquema único de salida que todo extractor (parsers SRI, ingesta de
mayores, OCR, analítica del motor forense, extracción por IA) debe producir
para que las herramientas de auditoría, NIIF y tributación consuman un
**dataset normalizado** en lugar de volver a leer el documento.

Dos niveles:

- :class:`CampoExtraido` — un dato puntual (un casillero, un saldo, una fecha
  de un contrato) con su valor crudo, su valor normalizado, su confianza, su
  método de extracción y su **evidencia hasta el origen** (archivo · página ·
  fila · celda).
- :class:`DatasetNormalizado` — un documento/tabla ya homologado: esquema
  detectado vs normalizado, mapeo de columnas, resultados de validación,
  puntaje de calidad, filas y excepciones.

Trazabilidad: :func:`huella` sella el contenido con SHA-256 para que el dato
sea reproducible y auditable (equivalente al sello REP-013 del motor forense).

Separación extracción↔conclusión (regla crítica del prompt §15): este
contrato SOLO transporta datos extraídos con su confianza; NO emite
conclusiones NIIF ni de auditoría — eso es trabajo de los motores
consumidores.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from backend.app.ingesta.confidence import (
    NivelConfianza,
    clasificar_confianza,
    requiere_revision,
)

CONTRATO_VERSION = "1.0.0"


class MetodoExtraccion(str, Enum):
    """Cómo se obtuvo el dato (escalera determinístico-primero del prompt §13).

    El orden de preferencia es NATIVO → PARSER → REGLA → REGEX → TABLA → OCR,
    y IA solo como último recurso ante ambigüedad semántica.
    """

    NATIVO = "nativo"        # extracción de texto/celda nativa (pdfplumber, openpyxl)
    PARSER = "parser"        # parser especializado (F-101/103/104, XML SRI)
    REGLA = "regla"          # regla determinística
    REGEX = "regex"          # patrón / expresión regular
    TABLA = "tabla"          # extracción de tabla/estructura
    OCR = "ocr"              # reconocimiento óptico (PDF escaneado)
    IA = "ia"                # resolución semántica por LLM (último recurso)
    MANUAL = "manual"        # ingresado/corregido por el auditor


class TipoDato(str, Enum):
    """Tipo normalizado del valor."""

    TEXTO = "texto"
    ENTERO = "entero"
    DECIMAL = "decimal"
    MONEDA = "moneda"
    FECHA = "fecha"
    BOOLEANO = "booleano"
    PORCENTAJE = "porcentaje"
    RUC = "ruc"
    DESCONOCIDO = "desconocido"


class TipoDocumento(str, Enum):
    """Tipo de documento de origen (extensible).

    Los valores cubren hoy el dominio SRI/NIIF del Command Center; se amplían
    conforme el Document Engine clasifique nuevos documentos (contratos,
    actas, confirmaciones).
    """

    F101 = "f101"
    F103 = "f103"
    F104 = "f104"
    ATS = "ats"
    BALANCE = "balance"
    MAYOR = "mayor"
    KARDEX = "kardex"
    FACTURACION = "facturacion"
    COMPROBANTE_SRI = "comprobante_sri"
    ESTADO_FINANCIERO = "estado_financiero"
    CARTA_CONTROL_INTERNO = "carta_control_interno"
    INFORME_AUDITORIA = "informe_auditoria"
    NOTAS_EEFF = "notas_eeff"
    CONTRATO = "contrato"
    DESCONOCIDO = "desconocido"


class Evidencia(BaseModel):
    """Ubicación exacta del dato en el documento original (trazabilidad)."""

    source_file: str = Field(min_length=1)
    source_page: Optional[int] = Field(default=None, ge=1)
    source_sheet: Optional[str] = None
    source_row: Optional[int] = Field(default=None, ge=0)
    source_cell: Optional[str] = None
    texto_soporte: Optional[str] = None


class CampoExtraido(BaseModel):
    """Un dato puntual extraído, con confianza, método y evidencia.

    Invariante: si la confianza es ``LOW`` o ``REVIEW_REQUIRED``, entonces
    ``review_required`` es ``True`` (el validador lo fuerza). Nunca se oculta
    la incertidumbre.
    """

    document_id: str = Field(min_length=1)
    document_type: TipoDocumento = TipoDocumento.DESCONOCIDO
    entity: Optional[str] = None            # RUC / razón social / tercero
    field: str = Field(min_length=1)        # nombre del campo/casillero
    raw_value: Optional[str] = None         # valor tal cual aparece en el origen
    normalized_value: Optional[Any] = None  # valor normalizado (Decimal, date, str…)
    data_type: TipoDato = TipoDato.DESCONOCIDO
    currency: Optional[str] = None          # p. ej. "USD"
    confidence: NivelConfianza = NivelConfianza.REVIEW_REQUIRED
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    extraction_method: MetodoExtraccion = MetodoExtraccion.NATIVO
    evidence: Optional[Evidencia] = None
    warnings: list[str] = Field(default_factory=list)
    review_required: bool = False

    @model_validator(mode="after")
    def _coherencia_revision(self) -> "CampoExtraido":
        # Si vino un puntaje y no un nivel explícito coherente, derivar el nivel.
        if self.confidence_score is not None:
            derivado = clasificar_confianza(self.confidence_score)
            # Toma el nivel MÁS conservador (mayor severidad) entre el explícito
            # y el derivado del puntaje: nunca sube la confianza por encima de lo
            # que el puntaje sostiene, ni la baja de un nivel ya conservador.
            if _orden(derivado) > _orden(self.confidence):
                self.confidence = derivado
        # La incertidumbre nunca se oculta.
        if requiere_revision(self.confidence):
            self.review_required = True
        return self

    @classmethod
    def desde_score(
        cls,
        *,
        document_id: str,
        field: str,
        score: float,
        **kwargs: Any,
    ) -> "CampoExtraido":
        """Construye un campo derivando el nivel de confianza desde el puntaje."""
        nivel = clasificar_confianza(score)
        return cls(
            document_id=document_id,
            field=field,
            confidence=nivel,
            confidence_score=max(0.0, min(1.0, float(score))) if score == score else 0.0,
            **kwargs,
        )


class ResultadoValidacion(BaseModel):
    """Resultado de una regla de validación sobre el dataset."""

    regla: str = Field(min_length=1)
    ok: bool
    detalle: Optional[str] = None


class Sello(BaseModel):
    """Sello de trazabilidad del dataset (reproducible, auditable)."""

    contrato_version: str = CONTRATO_VERSION
    generado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sha256: str = Field(min_length=64, max_length=64)


class DatasetNormalizado(BaseModel):
    """Un documento/tabla ya homologado y listo para consumo.

    ``quality_score`` (0..1) resume la calidad; si cae por debajo del umbral
    de confianza, ``review_required`` queda en ``True``. El dataset nunca
    afirma "sin excepciones" por falta de datos: eso se refleja en
    ``validation_results`` y ``warnings``.
    """

    dataset_id: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    document_type: TipoDocumento = TipoDocumento.DESCONOCIDO
    schema_detected: list[str] = Field(default_factory=list)
    schema_normalized: list[str] = Field(default_factory=list)
    mapping: dict[str, str] = Field(default_factory=dict)
    validation_results: list[ResultadoValidacion] = Field(default_factory=list)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    row_count: int = Field(default=0, ge=0)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    campos: list[CampoExtraido] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    extraction_method: MetodoExtraccion = MetodoExtraccion.NATIVO
    review_required: bool = False
    sello: Optional[Sello] = None

    @model_validator(mode="after")
    def _coherencia(self) -> "DatasetNormalizado":
        # row_count coherente con las filas presentes (si se cargaron).
        if self.rows and self.row_count == 0:
            self.row_count = len(self.rows)
        # Calidad baja o algún campo dudoso ⇒ revisión.
        if clasificar_confianza(self.quality_score) in (
            NivelConfianza.LOW,
            NivelConfianza.REVIEW_REQUIRED,
        ):
            self.review_required = True
        if any(c.review_required for c in self.campos):
            self.review_required = True
        return self

    def sellar(self) -> "DatasetNormalizado":
        """Calcula y adjunta el sello SHA-256 del contenido del dataset."""
        contenido = self.model_dump(mode="json", exclude={"sello"})
        self.sello = Sello(sha256=huella(contenido))
        return self


# Orden de severidad de los niveles (mayor = exige más revisión).
_ORDEN = {
    NivelConfianza.HIGH: 0,
    NivelConfianza.MEDIUM: 1,
    NivelConfianza.LOW: 2,
    NivelConfianza.REVIEW_REQUIRED: 3,
}


def _orden(nivel: NivelConfianza) -> int:
    return _ORDEN[nivel]


def huella(contenido: Any) -> str:
    """SHA-256 estable de un contenido serializable a JSON.

    Ordena las claves para que la huella sea reproducible ante el mismo dato,
    sin importar el orden de inserción.
    """
    payload = json.dumps(
        contenido, ensure_ascii=False, sort_keys=True, default=_json_default
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_default(obj: Any) -> str:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)
