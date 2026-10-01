"""Adaptadores de extractores (Fase 2).

Cada adaptador delega en un parser determinista que YA existe en la plataforma
(`backend/app/ict/parsers/*`) y traduce su salida al contrato común
(:class:`DatasetNormalizado`). Los parsers se importan **dentro** de cada
función para que importar este módulo (o el orquestador) no arrastre
pdfplumber/openpyxl.

Regla: estos adaptadores NO recalculan nada; solo presentan lo que el parser
entrega, con su evidencia (archivo + periodo) y confianza. Si el parser no pudo
leer el documento, el dataset queda marcado para revisión.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from backend.app.ingesta.confidence import NivelConfianza
from backend.app.ingesta.contract import (
    CampoExtraido,
    DatasetNormalizado,
    Evidencia,
    MetodoExtraccion,
    TipoDato,
    TipoDocumento,
)


def _dec(v: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _dataset_casilleros(
    parsed: Optional[dict],
    *,
    filename: str,
    tipo: TipoDocumento,
) -> DatasetNormalizado:
    """Construye un dataset a partir de un parser de casilleros SRI
    ({'periodo', 'casilleros': {num: float}, 'errores': [...]})."""
    if not parsed:
        return DatasetNormalizado(
            dataset_id=filename, source_file=filename, document_type=tipo,
            quality_score=0.0, exceptions=["el parser no devolvió datos"],
            extraction_method=MetodoExtraccion.PARSER, review_required=True,
        )
    periodo = parsed.get("periodo")
    casilleros = parsed.get("casilleros") or {}
    errores = list(parsed.get("errores") or [])
    campos: list[CampoExtraido] = []
    for num, valor in casilleros.items():
        campos.append(
            CampoExtraido(
                document_id=filename,
                document_type=tipo,
                entity=str(periodo) if periodo else None,
                field=f"cas_{num}",
                raw_value=str(valor),
                normalized_value=_dec(valor),
                data_type=TipoDato.MONEDA,
                currency="USD",
                confidence=NivelConfianza.HIGH,
                confidence_score=0.95,
                extraction_method=MetodoExtraccion.PARSER,
                evidence=Evidencia(source_file=filename),
            )
        )
    quality = 1.0 if (campos and not errores) else (0.5 if campos else 0.0)
    return DatasetNormalizado(
        dataset_id=filename,
        source_file=filename,
        document_type=tipo,
        schema_detected=[f"cas_{n}" for n in casilleros],
        schema_normalized=[f"cas_{n}" for n in casilleros],
        campos=campos,
        quality_score=quality,
        exceptions=errores,
        extraction_method=MetodoExtraccion.PARSER,
    )


def _dataset_filas(
    filas: list[dict],
    *,
    filename: str,
    tipo: TipoDocumento,
    errores: Optional[list[str]] = None,
) -> DatasetNormalizado:
    filas = filas or []
    errores = list(errores or [])
    schema = list(filas[0].keys()) if filas else []
    quality = 1.0 if (filas and not errores) else (0.5 if filas else 0.0)
    return DatasetNormalizado(
        dataset_id=filename,
        source_file=filename,
        document_type=tipo,
        schema_detected=schema,
        schema_normalized=schema,
        rows=[dict(f) for f in filas],
        row_count=len(filas),
        quality_score=quality,
        exceptions=errores,
        extraction_method=MetodoExtraccion.PARSER,
    )


# --------------------------------------------------------------------------- #
#  Adaptadores por tipo (delegan en los parsers existentes)                    #
# --------------------------------------------------------------------------- #
def extraer_f101(contenido: bytes, filename: str) -> DatasetNormalizado:
    from backend.app.ict.parsers.f101_pdf import parse_f101
    return _dataset_casilleros(parse_f101(contenido), filename=filename, tipo=TipoDocumento.F101)


def extraer_f103(contenido: bytes, filename: str) -> DatasetNormalizado:
    from backend.app.ict.parsers.f103_pdf import parse_f103
    return _dataset_casilleros(parse_f103(contenido), filename=filename, tipo=TipoDocumento.F103)


def extraer_f104(contenido: bytes, filename: str) -> DatasetNormalizado:
    from backend.app.ict.parsers.f104_pdf import parse_f104
    return _dataset_casilleros(parse_f104(contenido), filename=filename, tipo=TipoDocumento.F104)


def extraer_mayor(contenido: bytes, filename: str) -> DatasetNormalizado:
    from backend.app.ict.parsers.mayor_excel import parse_mayor
    r = parse_mayor(contenido) or {}
    return _dataset_filas(
        r.get("movimientos") or [], filename=filename, tipo=TipoDocumento.MAYOR,
        errores=r.get("errores"),
    )


def extraer_kardex(contenido: bytes, filename: str) -> DatasetNormalizado:
    from backend.app.ict.parsers.kardex_excel import parse_kardex
    r = parse_kardex(contenido) or {}
    return _dataset_filas(
        r.get("items") or [], filename=filename, tipo=TipoDocumento.KARDEX,
        errores=r.get("errores"),
    )


def extraer_ats(contenido: bytes, filename: str) -> DatasetNormalizado:
    from backend.app.ict.parsers.ats_xml import parse_ats
    r = parse_ats(contenido) or {}
    ds = _dataset_filas(
        r.get("compras") or [], filename=filename, tipo=TipoDocumento.ATS,
        errores=r.get("errores"),
    )
    # Metadato de cabecera del ATS como campo (RUC informante / periodo).
    if r.get("ruc_informante"):
        ds.campos.append(
            CampoExtraido(
                document_id=filename, document_type=TipoDocumento.ATS,
                entity=r.get("razon_social"), field="ruc_informante",
                raw_value=str(r.get("ruc_informante")),
                normalized_value=str(r.get("ruc_informante")),
                data_type=TipoDato.RUC, confidence=NivelConfianza.HIGH,
                confidence_score=0.95, extraction_method=MetodoExtraccion.PARSER,
                evidence=Evidencia(source_file=filename),
            )
        )
    return ds


def extraer_balance(contenido: bytes, filename: str) -> DatasetNormalizado:
    from backend.app.ict.parsers.balance_mapeado_excel import parse_balance_mapeado
    r = parse_balance_mapeado(contenido) or {}
    casilleros = r.get("casilleros")
    if isinstance(casilleros, dict):
        return _dataset_casilleros(
            {"periodo": r.get("periodo"), "casilleros": casilleros,
             "errores": r.get("errores") or []},
            filename=filename, tipo=TipoDocumento.BALANCE,
        )
    filas = r.get("cuentas") or r.get("filas") or []
    return _dataset_filas(
        filas, filename=filename, tipo=TipoDocumento.BALANCE, errores=r.get("errores"),
    )


def extraer_facturacion(contenido: bytes, filename: str) -> DatasetNormalizado:
    from backend.app.ict.parsers.facturacion_sri import parse_facturacion
    r = parse_facturacion(contenido) or {}
    filas = r.get("meses") or r.get("filas") or r.get("rows") or []
    return _dataset_filas(
        filas, filename=filename, tipo=TipoDocumento.FACTURACION, errores=r.get("errores"),
    )
