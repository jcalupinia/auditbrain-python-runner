"""Soporte de OCR para la ingesta (Fase 4).

Cablea el OCR a los documentos SRI **sin tocar los parsers existentes**: hoy,
ante un PDF escaneado, los parsers del ICT devuelven el error "PDF sin texto
extraíble (¿escaneado? Aplica OCR e intenta de nuevo)". Esta capa, cuando un
parser no recupera datos de un PDF de casilleros, extrae el texto por OCR
(determinístico primero: pdfplumber y, solo si no alcanza, Google Vision, vía
`utils/ocr.extract_text_smart`) y **reutiliza las funciones de extracción por
texto que ya existen** (`f103_pdf._extract_casilleros/_extract_periodo`,
`f101_pdf` + `find_casillero_value`) para reconstruir los casilleros. No se
reescribe ningún regex.

Todo es inyectable (`smart`, `extraer`, `casilleros_fn`) para poder probarlo sin
pdfplumber ni Vision. El dato recuperado por OCR se marca con
`extraction_method=OCR`, confianza `MEDIUM` y el dataset queda `review_required`
(no se oculta la incertidumbre del escaneo).
"""
from __future__ import annotations

import os
import tempfile
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from backend.app.ingesta.confidence import NivelConfianza
from backend.app.ingesta.contract import (
    CampoExtraido,
    DatasetNormalizado,
    Evidencia,
    MetodoExtraccion,
    TipoDato,
    TipoDocumento,
)

# Tipos de documento para los que hay recuperación por OCR (PDFs de casilleros
# con función de extracción por texto reutilizable).
RECUPERABLES_OCR = frozenset({TipoDocumento.F101, TipoDocumento.F103})


class TextoDocumento(BaseModel):
    """Texto extraído de un documento + cómo se obtuvo."""

    texto: str = ""
    metodo: MetodoExtraccion = MetodoExtraccion.NATIVO
    paginas: int = Field(default=0, ge=0)
    ocr_units: int = Field(default=0, ge=0)
    disponible: bool = True
    nota: Optional[str] = None


# Mapea el "method" de utils.ocr.extract_text_smart a nuestro MetodoExtraccion.
_METODO = {
    "pdfplumber": MetodoExtraccion.NATIVO,
    "ocr": MetodoExtraccion.OCR,
    "ocr_failed_fallback": MetodoExtraccion.OCR,
}


def extraer_texto(
    contenido: bytes,
    filename: str = "documento.pdf",
    *,
    smart: Optional[Callable[[str], dict]] = None,
) -> TextoDocumento:
    """Extrae texto de un PDF (pdfplumber → OCR Vision). Nunca lanza.

    ``smart`` es inyectable (por defecto, perezosamente,
    ``utils.ocr.extract_text_smart``), que recibe una RUTA. Como la ingesta
    trabaja con bytes, se escribe un archivo temporal y se borra siempre.
    """
    if smart is None:
        def smart(path: str) -> dict:  # import perezoso: evita grpcio/vision al importar
            from backend.app.utils.ocr import extract_text_smart
            return extract_text_smart(path)

    sufijo = os.path.splitext(filename)[1] or ".pdf"
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=sufijo, delete=False) as tmp:
            tmp.write(contenido)
            tmp_path = tmp.name
        res = smart(tmp_path) or {}
        metodo = _METODO.get(str(res.get("method", "")), MetodoExtraccion.OCR)
        disponible = res.get("method") != "ocr_failed_fallback"
        return TextoDocumento(
            texto=res.get("text") or "",
            metodo=metodo,
            paginas=int(res.get("pages") or 0),
            ocr_units=int(res.get("ocr_units_used") or 0),
            disponible=disponible,
            nota=None if disponible else "OCR no disponible (falta Google Vision)",
        )
    except Exception as e:  # el OCR no debe tumbar la ingesta
        return TextoDocumento(
            texto="", metodo=MetodoExtraccion.OCR, disponible=False,
            nota=f"extracción de texto falló: {type(e).__name__}: {e}",
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _casilleros_f103(texto: str) -> dict[str, Any]:
    from backend.app.ict.parsers.f103_pdf import _extract_casilleros, _extract_periodo
    cas = _extract_casilleros(texto) or {}
    return {"periodo": _extract_periodo(texto), "casilleros": cas}


def _casilleros_f101(texto: str) -> dict[str, Any]:
    from backend.app.ict.parsers.f101_pdf import ALL_F101_CASILLEROS, find_casillero_value
    from backend.app.aud.obligaciones_fiscales.cedulas.base import find_periodo
    cas: dict[str, Any] = {}
    for num in ALL_F101_CASILLEROS:
        v = find_casillero_value(texto, num)
        if v is not None:
            cas[num] = v
    return {"periodo": find_periodo(texto), "casilleros": cas}


_CASILLEROS_POR_TIPO: dict[TipoDocumento, Callable[[str], dict]] = {
    TipoDocumento.F103: _casilleros_f103,
    TipoDocumento.F101: _casilleros_f101,
}


def _dec(v: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None


def recuperar_por_ocr(
    tipo: TipoDocumento,
    contenido: bytes,
    filename: str,
    *,
    extraer: Optional[Callable[..., TextoDocumento]] = None,
    casilleros_fn: Optional[Callable[[str], dict]] = None,
) -> Optional[DatasetNormalizado]:
    """Intenta reconstruir los casilleros de un PDF escaneado vía OCR.

    Devuelve un :class:`DatasetNormalizado` si recuperó datos; ``None`` si el
    tipo no es recuperable, no hay texto, o no se encontraron casilleros.
    """
    if tipo not in RECUPERABLES_OCR:
        return None
    extraer = extraer or extraer_texto
    casilleros_fn = casilleros_fn or _CASILLEROS_POR_TIPO.get(tipo)
    if casilleros_fn is None:
        return None

    td = extraer(contenido, filename)
    if not td.texto:
        return None
    try:
        parsed = casilleros_fn(td.texto) or {}
    except Exception:
        return None
    casilleros = parsed.get("casilleros") or {}
    if not casilleros:
        return None

    periodo = parsed.get("periodo")
    campos = [
        CampoExtraido(
            document_id=filename,
            document_type=tipo,
            entity=str(periodo) if periodo else None,
            field=f"cas_{num}",
            raw_value=str(valor),
            normalized_value=_dec(valor),
            data_type=TipoDato.MONEDA,
            currency="USD",
            confidence=NivelConfianza.MEDIUM,   # OCR: menos certero que nativo
            confidence_score=0.75,
            extraction_method=MetodoExtraccion.OCR,
            evidence=Evidencia(source_file=filename, texto_soporte="recuperado por OCR"),
        )
        for num, valor in casilleros.items()
    ]
    return DatasetNormalizado(
        dataset_id=filename,
        source_file=filename,
        document_type=tipo,
        schema_detected=[f"cas_{n}" for n in casilleros],
        schema_normalized=[f"cas_{n}" for n in casilleros],
        campos=campos,
        quality_score=0.75,
        extraction_method=MetodoExtraccion.OCR,
        warnings=[
            f"datos recuperados por OCR ({td.metodo.value}); revisar contra el PDF",
        ],
        review_required=True,  # el escaneo siempre se revisa
    )
