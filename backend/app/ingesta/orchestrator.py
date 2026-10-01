"""Orquestador de ingesta (Fase 2).

Coordina el flujo **clasificar → elegir extractor determinista → normalizar**
y devuelve un :class:`DatasetNormalizado`. Sin IA: solo reutiliza los parsers
deterministas que ya existen en la plataforma (los adaptadores delegan en
``backend/app/ict/parsers/*`` con import perezoso).

Diseño por registro de extractores: el orquestador no conoce los parsers; recibe
(o toma por defecto) un mapa ``TipoDocumento -> Extractor``. Así se puede probar
la orquestación con extractores falsos sin cargar dependencias pesadas
(pdfplumber/openpyxl), y las herramientas pueden registrar extractores nuevos
sin tocar esta capa.
"""
from __future__ import annotations

from typing import Callable, Optional

from backend.app.ingesta.classifier import ResultadoClasificacion, clasificar_documento
from backend.app.ingesta.confidence import NivelConfianza
from backend.app.ingesta.confidence_live import consolidar_confianza
from backend.app.ingesta.contract import (
    DatasetNormalizado,
    MetodoExtraccion,
    TipoDocumento,
)

# Un extractor recibe (contenido, filename) y devuelve un DatasetNormalizado.
Extractor = Callable[[bytes, str], DatasetNormalizado]

# Una función de recuperación por OCR: (tipo, contenido, filename) -> dataset|None.
RecuperadorOCR = Callable[[TipoDocumento, bytes, str], Optional[DatasetNormalizado]]


def extractores_por_defecto() -> dict[TipoDocumento, Extractor]:
    """Registro de extractores reales (import perezoso de los adaptadores).

    Se importa aquí dentro para que importar el orquestador NO arrastre
    pdfplumber/openpyxl. Si falta una dependencia al ejecutar, el adaptador
    lo reporta como excepción del dataset (no rompe la ingesta).
    """
    from backend.app.ingesta import adapters as a

    return {
        TipoDocumento.F101: a.extraer_f101,
        TipoDocumento.F103: a.extraer_f103,
        TipoDocumento.F104: a.extraer_f104,
        TipoDocumento.ATS: a.extraer_ats,
        TipoDocumento.BALANCE: a.extraer_balance,
        TipoDocumento.MAYOR: a.extraer_mayor,
        TipoDocumento.KARDEX: a.extraer_kardex,
        TipoDocumento.FACTURACION: a.extraer_facturacion,
    }


def ingerir(
    filename: str,
    contenido: bytes,
    *,
    tipo_declarado: Optional[str] = None,
    extractores: Optional[dict[TipoDocumento, Extractor]] = None,
    dataset_id: Optional[str] = None,
    sellar: bool = True,
    ocr: bool = True,
    recuperar_ocr: Optional[RecuperadorOCR] = None,
    consolidar: bool = True,
) -> DatasetNormalizado:
    """Ingiere un documento y devuelve el dataset normalizado.

    Nunca lanza por un documento problemático: si no hay extractor, o el
    extractor falla, devuelve un dataset marcado ``review_required`` con la
    excepción registrada (determinístico primero; la incertidumbre no se oculta).

    Si ``ocr`` está activo y el extractor determinista no recuperó datos de un
    PDF de casilleros (p. ej. escaneado), intenta recuperarlos por OCR
    reutilizando los parsers por texto existentes.
    """
    clasificacion = clasificar_documento(
        filename, contenido=contenido, tipo_declarado=tipo_declarado
    )
    registro = extractores if extractores is not None else extractores_por_defecto()
    did = dataset_id or filename

    extractor = registro.get(clasificacion.tipo)
    if extractor is None:
        ds = _dataset_sin_extractor(did, filename, clasificacion)
        ds = _quizas_ocr(ds, clasificacion, contenido, filename, ocr, recuperar_ocr)
        return _finalizar(ds, sellar, consolidar)

    try:
        ds = extractor(contenido, filename)
    except Exception as e:  # el extractor no debe tumbar la ingesta
        ds = DatasetNormalizado(
            dataset_id=did,
            source_file=filename,
            document_type=clasificacion.tipo,
            quality_score=0.0,
            exceptions=[f"extractor falló: {type(e).__name__}: {e}"],
            warnings=[_razon(clasificacion)],
            review_required=True,
        )
        ds = _quizas_ocr(ds, clasificacion, contenido, filename, ocr, recuperar_ocr)
        return _finalizar(ds, sellar, consolidar)

    # Completa metadatos de clasificación si el adaptador no los fijó.
    if ds.document_type is TipoDocumento.DESCONOCIDO:
        ds.document_type = clasificacion.tipo
    if not ds.dataset_id:
        ds.dataset_id = did
    ds = _quizas_ocr(ds, clasificacion, contenido, filename, ocr, recuperar_ocr)
    ds.warnings.append(_razon(clasificacion))
    # Una clasificación dudosa contagia revisión al dataset.
    if clasificacion.confidence in (NivelConfianza.LOW, NivelConfianza.REVIEW_REQUIRED):
        ds.review_required = True
    return _finalizar(ds, sellar, consolidar)


def _finalizar(ds: DatasetNormalizado, sellar: bool, consolidar: bool) -> DatasetNormalizado:
    """Consolida la confianza (en vivo) y, si corresponde, sella el dataset."""
    if consolidar:
        consolidar_confianza(ds)
    return ds.sellar() if sellar else ds


def _quizas_ocr(
    ds: DatasetNormalizado,
    clasificacion: ResultadoClasificacion,
    contenido: bytes,
    filename: str,
    ocr: bool,
    recuperar_ocr: Optional[RecuperadorOCR],
) -> DatasetNormalizado:
    """Si el extractor no recuperó datos, intenta OCR (determinístico primero).

    Solo actúa cuando el dataset quedó sin campos ni filas. Preserva el
    ``dataset_id`` original y acarrea las excepciones previas como advertencia.
    """
    if not ocr or ds.campos or ds.rows:
        return ds
    if recuperar_ocr is None:
        def recuperar_ocr(tipo, cont, name):  # import perezoso
            from backend.app.ingesta.ocr_support import recuperar_por_ocr
            return recuperar_por_ocr(tipo, cont, name)
    try:
        recuperado = recuperar_ocr(clasificacion.tipo, contenido, filename)
    except Exception:
        recuperado = None
    if recuperado is None or not recuperado.campos:
        ds.warnings.append("OCR no recuperó datos")
        return ds
    recuperado.dataset_id = ds.dataset_id or filename
    if ds.exceptions:
        recuperado.warnings.append(
            "intento determinista previo sin datos: " + "; ".join(ds.exceptions)
        )
    return recuperado


def _dataset_sin_extractor(
    dataset_id: str, filename: str, clasificacion: ResultadoClasificacion
) -> DatasetNormalizado:
    return DatasetNormalizado(
        dataset_id=dataset_id,
        source_file=filename,
        document_type=clasificacion.tipo,
        quality_score=0.0,
        warnings=[
            _razon(clasificacion),
            f"no hay extractor registrado para {clasificacion.tipo.value}",
        ],
        extraction_method=MetodoExtraccion.NATIVO,
        review_required=True,
    )


def _razon(clasificacion: ResultadoClasificacion) -> str:
    return (
        f"clasificación={clasificacion.tipo.value} "
        f"({clasificacion.confidence.value}; {'; '.join(clasificacion.razones)})"
    )
