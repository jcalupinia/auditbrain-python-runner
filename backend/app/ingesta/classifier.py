"""Clasificador determinista de tipo de documento (Fase 2).

Decide el :class:`TipoDocumento` de un archivo **sin IA**, siguiendo la
escalera determinístico-primero del prompt §13:

1. Tipo declarado por el usuario (el *slot* de subida) — manda y es ``HIGH``.
2. Firma de contenido (raíz XML, texto "FORMULARIO 104", …) — ``HIGH``/``MEDIUM``.
3. Palabra clave en el nombre del archivo + extensión — ``MEDIUM``.
4. Solo extensión (ambigua) — ``LOW``.
5. Nada reconocible — ``DESCONOCIDO`` + ``REVIEW_REQUIRED``.

La IA (fase posterior) solo intervendría cuando esto deja el documento en
revisión. El clasificador nunca lanza: ante la duda, degrada a revisión.
"""
from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, Field

from backend.app.ingesta.confidence import NivelConfianza, clasificar_confianza
from backend.app.ingesta.contract import MetodoExtraccion, TipoDocumento

# Nombre de *slot* (el que ya usa ict/router.py::SLOT_PARSERS) → TipoDocumento.
SLOT_A_TIPO: dict[str, TipoDocumento] = {
    "f101": TipoDocumento.F101,
    "f103": TipoDocumento.F103,
    "f104": TipoDocumento.F104,
    "ats": TipoDocumento.ATS,
    "balance_mapeado": TipoDocumento.BALANCE,
    "balance": TipoDocumento.BALANCE,
    "kardex": TipoDocumento.KARDEX,
    "facturacion": TipoDocumento.FACTURACION,
    "mayor_exentos": TipoDocumento.MAYOR,
    "mayor_no_deducibles": TipoDocumento.MAYOR,
    "mayor": TipoDocumento.MAYOR,
    "comprobante_sri": TipoDocumento.COMPROBANTE_SRI,
    "estado_financiero": TipoDocumento.ESTADO_FINANCIERO,
    "carta_control_interno": TipoDocumento.CARTA_CONTROL_INTERNO,
    "informe_auditoria": TipoDocumento.INFORME_AUDITORIA,
    "notas_eeff": TipoDocumento.NOTAS_EEFF,
    "contrato": TipoDocumento.CONTRATO,
}

# Palabras clave en el nombre del archivo → TipoDocumento (orden: específico primero).
_NOMBRE_SIGNOS: list[tuple[tuple[str, ...], TipoDocumento]] = [
    (("f101", "formulario101", "renta_sociedades", "renta sociedades"), TipoDocumento.F101),
    (("f103", "formulario103", "retencion", "retenciones"), TipoDocumento.F103),
    (("f104", "formulario104",), TipoDocumento.F104),
    (("ats", "anexo_transaccional", "anexo transaccional"), TipoDocumento.ATS),
    (("balance_mapeado", "balance mapeado", "balance"), TipoDocumento.BALANCE),
    (("kardex", "inventario", "inventarios"), TipoDocumento.KARDEX),
    (("facturacion", "facturación", "ventas_sri"), TipoDocumento.FACTURACION),
    (("mayor", "libro_mayor", "libro mayor", "diario"), TipoDocumento.MAYOR),
    (("carta_control", "control_interno", "control interno"), TipoDocumento.CARTA_CONTROL_INTERNO),
    (("informe_auditoria", "informe de auditoria", "dictamen"), TipoDocumento.INFORME_AUDITORIA),
    (("notas", "revelaciones"), TipoDocumento.NOTAS_EEFF),
    (("contrato", "arrendamiento", "lease", "convenio"), TipoDocumento.CONTRATO),
    (("estado_financiero", "estados_financieros", "eeff", "situacion financiera"),
     TipoDocumento.ESTADO_FINANCIERO),
]


class ResultadoClasificacion(BaseModel):
    """Resultado de clasificar un documento."""

    tipo: TipoDocumento = TipoDocumento.DESCONOCIDO
    confidence: NivelConfianza = NivelConfianza.REVIEW_REQUIRED
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    metodo: MetodoExtraccion = MetodoExtraccion.REGLA
    razones: list[str] = Field(default_factory=list)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _firma_contenido(contenido: bytes) -> tuple[Optional[TipoDocumento], str]:
    """Detecta el tipo por firma del contenido. Best-effort, nunca lanza."""
    if not contenido:
        return None, ""
    cabeza = contenido[:4096]
    try:
        texto = cabeza.decode("utf-8", errors="ignore").lower()
    except Exception:
        return None, ""
    # XML del SRI.
    if texto.lstrip().startswith("<?xml") or texto.lstrip().startswith("<"):
        if "detallecompras" in texto or "<iva" in texto or "numestabrucemisor" in texto:
            return TipoDocumento.ATS, "firma XML ATS"
        if "<factura" in texto or "comprobanteretencion" in texto or "<autorizacion" in texto \
                or "notacredito" in texto:
            return TipoDocumento.COMPROBANTE_SRI, "firma XML comprobante SRI"
    # Texto de formularios (cuando se pasa texto plano extraído del PDF).
    if "formulario 104" in texto or ("104" in texto and "impuesto al valor agregado" in texto):
        return TipoDocumento.F104, "texto 'FORMULARIO 104'"
    if "formulario 103" in texto or "retenciones en la fuente" in texto:
        return TipoDocumento.F103, "texto 'retenciones en la fuente'"
    if "formulario 101" in texto or "renta sociedades" in texto:
        return TipoDocumento.F101, "texto 'renta sociedades'"
    return None, ""


def clasificar_documento(
    filename: str,
    *,
    contenido: Optional[bytes] = None,
    tipo_declarado: Optional[str] = None,
) -> ResultadoClasificacion:
    """Clasifica un documento de forma determinista.

    - ``tipo_declarado``: nombre de *slot* o valor de :class:`TipoDocumento`
      indicado por el usuario (manda, confianza ``HIGH``).
    - ``contenido``: bytes del archivo (opcional); habilita firma de contenido.
    """
    razones: list[str] = []

    # 1) Tipo declarado por el usuario — manda.
    if tipo_declarado:
        clave = _norm(tipo_declarado)
        tipo = SLOT_A_TIPO.get(clave)
        if tipo is None:
            try:
                tipo = TipoDocumento(clave)
            except ValueError:
                tipo = None
        if tipo is not None:
            return ResultadoClasificacion(
                tipo=tipo,
                confidence=NivelConfianza.HIGH,
                confidence_score=0.99,
                razones=[f"tipo declarado por el usuario: {tipo_declarado!r}"],
            )
        razones.append(f"tipo declarado no reconocido: {tipo_declarado!r}")

    # 2) Firma de contenido.
    if contenido is not None:
        tipo_c, razon = _firma_contenido(contenido)
        if tipo_c is not None:
            return ResultadoClasificacion(
                tipo=tipo_c,
                confidence=NivelConfianza.HIGH,
                confidence_score=0.92,
                razones=[razon],
            )

    nombre = _norm(filename)
    ext = os.path.splitext(nombre)[1].lstrip(".")

    # 3) Palabra clave en el nombre.
    for claves, tipo in _NOMBRE_SIGNOS:
        if any(c in nombre for c in claves):
            # XML con nombre "ats"/"comprobante" sube la confianza por coherencia extensión.
            score = 0.80 if ext in {"pdf", "xml", "xlsx", "xls", "csv"} else 0.72
            return ResultadoClasificacion(
                tipo=tipo,
                confidence=clasificar_confianza(score),
                confidence_score=score,
                razones=razones + [f"palabra clave en el nombre ({tipo.value})", f"extensión .{ext}"],
            )

    # 4) Solo extensión — ambiguo, baja confianza.
    if ext == "xml":
        return ResultadoClasificacion(
            tipo=TipoDocumento.COMPROBANTE_SRI,
            confidence=NivelConfianza.LOW,
            confidence_score=0.55,
            razones=razones + ["solo extensión .xml (ambiguo)"],
        )

    # 5) Nada reconocible — a revisión.
    return ResultadoClasificacion(
        tipo=TipoDocumento.DESCONOCIDO,
        confidence=NivelConfianza.REVIEW_REQUIRED,
        confidence_score=0.0,
        razones=razones + [f"sin firma ni palabra clave (extensión .{ext or '?'})"],
    )
