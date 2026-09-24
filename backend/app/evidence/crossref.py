"""Matriz de evidencia: dato → fuente(s) → cita, con validación humana.

Capacidad: DOC-010 (matriz de referencias cruzadas dato↔fuente↔cita, con el
estado de validación del auditor).

Es el registro central que amarra todo el paquete:

    dato (valor + confianza)  ──►  1..N SourceReference (cita: página/celda/bbox)

Un mismo dato puede sostenerse en varias fuentes (la factura aparece en el
auxiliar, en el XML SRI y en el comprobante de pago); cada una es una
``SourceReference`` y su conjunto es la "evidencia" del dato. El auditor
revisa esa evidencia y marca cada entrada como validada / rechazada /
observada — nada se da por bueno automáticamente (principio de aprobación
humana de la arquitectura, y control 2/6 del CLAUDE.md).

Salida natural: una hoja EXCEL del papel de trabajo (una fila por entrada,
con hipervínculo lógico a página/celda). NO viaja al archivo SRI (regla de
separación SRI vs papel de trabajo del CLAUDE.md): la matriz es papel de
trabajo del auditor.
"""

from __future__ import annotations

import datetime
import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:  # los tipos viven en otros módulos del paquete
    from backend.app.evidence.citation import SourceReference
    from backend.app.evidence.confidence import ConfianzaCampo


class EstadoValidacion(enum.Enum):
    """Estado de la revisión humana de una pieza de evidencia."""

    PENDIENTE = "pendiente"      # aún no revisada (estado inicial)
    VALIDADO = "validado"        # el auditor confirma dato y cita
    RECHAZADO = "rechazado"      # el auditor rechaza (dato/cita incorrecta)
    OBSERVADO = "observado"      # necesita aclaración / evidencia adicional


@dataclass
class EntradaEvidencia:
    """Una fila de la matriz: un dato con sus fuentes y su estado."""

    dato_id: str                              # id lógico del dato (p.ej. "F101.cas550")
    etiqueta: str                             # nombre legible ("Total ingresos")
    valor: Any                                # valor normalizado del dato
    source_refs: list["SourceReference"] = field(default_factory=list)
    confianza: "ConfianzaCampo | None" = None
    estado_validacion: EstadoValidacion = EstadoValidacion.PENDIENTE
    validado_por: str | None = None
    validado_en: datetime.datetime | None = None
    nota: str = ""

    @property
    def num_fuentes(self) -> int:
        return len(self.source_refs)

    @property
    def es_corroborado(self) -> bool:
        """True si el dato tiene ≥2 fuentes independientes que lo sostienen."""
        return self.num_fuentes >= 2

    def marcar(
        self,
        estado: EstadoValidacion,
        *,
        por: str,
        cuando: datetime.datetime | None = None,
        nota: str = "",
    ) -> None:
        """Registra la decisión del auditor (con quién y cuándo, para el trail)."""
        self.estado_validacion = estado
        self.validado_por = por
        self.validado_en = cuando or datetime.datetime.utcnow()
        if nota:
            self.nota = nota


@dataclass
class MatrizEvidencia:
    """Colección de entradas con operaciones de consulta y export."""

    entradas: list[EntradaEvidencia] = field(default_factory=list)

    def agregar(
        self,
        dato_id: str,
        etiqueta: str,
        valor: Any,
        source_refs: Iterable["SourceReference"],
        *,
        confianza: "ConfianzaCampo | None" = None,
    ) -> EntradaEvidencia:
        """Crea y registra una entrada. Estado inicial = PENDIENTE.

        Si ``dato_id`` ya existe, agrega las nuevas ``source_refs`` a la entrada
        existente (un dato puede ir sumando fuentes a medida que se cargan los
        archivos), sin duplicar por ``source_id``.
        """
        existente = self.obtener(dato_id)
        if existente is None:
            existente = EntradaEvidencia(
                dato_id=dato_id, etiqueta=etiqueta, valor=valor,
                source_refs=[], confianza=confianza,
            )
            self.entradas.append(existente)
        vistos = {r.source_id for r in existente.source_refs}
        for ref in source_refs:
            if ref.source_id not in vistos:
                existente.source_refs.append(ref)
                vistos.add(ref.source_id)
        if confianza is not None:
            existente.confianza = confianza
        return existente

    def obtener(self, dato_id: str) -> EntradaEvidencia | None:
        """Devuelve la entrada por id, o None."""
        for e in self.entradas:
            if e.dato_id == dato_id:
                return e
        return None

    def por_estado(self, estado: EstadoValidacion) -> list[EntradaEvidencia]:
        """Entradas en un estado dado (p.ej. todas las PENDIENTE)."""
        return [e for e in self.entradas if e.estado_validacion is estado]

    def pendientes_de_revision(self) -> list[EntradaEvidencia]:
        """Entradas que exigen ojo humano, ordenadas por confianza asc."""
        def _requiere(e: EntradaEvidencia) -> bool:
            if e.estado_validacion in (EstadoValidacion.PENDIENTE, EstadoValidacion.OBSERVADO):
                return True
            return bool(e.confianza is not None and e.confianza.requiere_revision_humana)

        def _clave(e: EntradaEvidencia) -> float:
            # Ordena por confianza ascendente (lo más dudoso primero). Las
            # entradas sin confianza calculada van al final (no se pueden
            # comparar por score; están pendientes por otra razón).
            return e.confianza.confianza_global if e.confianza is not None else float("inf")

        return sorted((e for e in self.entradas if _requiere(e)), key=_clave)

    def sin_evidencia(self) -> list[EntradaEvidencia]:
        """Datos declarados que NO tienen ninguna ``SourceReference`` (DQ-006)."""
        return [e for e in self.entradas if not e.source_refs]

    def resumen(self) -> dict[str, int]:
        """Conteo por estado + totales, para el encabezado de la hoja."""
        conteo = {est.value: 0 for est in EstadoValidacion}
        for e in self.entradas:
            conteo[e.estado_validacion.value] += 1
        conteo["total"] = len(self.entradas)
        conteo["sin_evidencia"] = len(self.sin_evidencia())
        return conteo

    def a_filas(self) -> list[dict[str, Any]]:
        """Aplana la matriz a filas planas para volcar a Excel/JSON.

        Una fila por (dato × source_ref); un dato sin fuentes emite una fila con
        los campos de origen en None (para que igual se vea en el papel).
        """
        filas: list[dict[str, Any]] = []
        for e in self.entradas:
            ce = e.confianza.confianza_extraccion if e.confianza else None
            ci = e.confianza.confianza_interpretacion if e.confianza else None
            refs = e.source_refs or [None]
            for ref in refs:
                bbox = getattr(ref, "bounding_box", None) if ref else None
                filas.append({
                    "dato_id": e.dato_id,
                    "etiqueta": e.etiqueta,
                    "valor": e.valor,
                    "filename": getattr(ref, "filename", None) if ref else None,
                    "source_id": getattr(ref, "source_id", None) if ref else None,
                    "pagina": getattr(ref, "page", None) if ref else None,
                    "celda": (
                        f"{ref.sheet_or_table}!{ref.row_id}:{ref.column}"
                        if ref and ref.sheet_or_table else None
                    ),
                    "bbox": (
                        [bbox.x0, bbox.y0, bbox.x1, bbox.y1, bbox.unidad] if bbox else None
                    ),
                    "confianza_extraccion": ce,
                    "confianza_interpretacion": ci,
                    "estado": e.estado_validacion.value,
                    "validado_por": e.validado_por,
                    "validado_en": e.validado_en.isoformat() if e.validado_en else None,
                    "nota": e.nota,
                })
        return filas
