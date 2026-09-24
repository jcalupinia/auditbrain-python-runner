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
        raise NotImplementedError("P1-E: implementar en el servidor")

    def marcar(
        self,
        estado: EstadoValidacion,
        *,
        por: str,
        cuando: datetime.datetime | None = None,
        nota: str = "",
    ) -> None:
        """Registra la decisión del auditor (con quién y cuándo, para el trail)."""
        raise NotImplementedError("P1-E: implementar en el servidor")


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
        raise NotImplementedError("P1-E: implementar en el servidor")

    def obtener(self, dato_id: str) -> EntradaEvidencia | None:
        """Devuelve la entrada por id, o None."""
        raise NotImplementedError("P1-E: implementar en el servidor")

    def por_estado(self, estado: EstadoValidacion) -> list[EntradaEvidencia]:
        """Entradas en un estado dado (p.ej. todas las PENDIENTE)."""
        raise NotImplementedError("P1-E: implementar en el servidor")

    def pendientes_de_revision(self) -> list[EntradaEvidencia]:
        """Entradas que exigen ojo humano: PENDIENTE/OBSERVADO, o cuya
        ``confianza.requiere_revision_humana`` sea True.

        Ordenadas por confianza global ascendente (lo más dudoso primero).
        """
        raise NotImplementedError("P1-E: implementar en el servidor")

    def sin_evidencia(self) -> list[EntradaEvidencia]:
        """Datos declarados que NO tienen ninguna ``SourceReference`` (DQ-006):
        el peor caso, un dato afirmado sin fuente que lo respalde."""
        raise NotImplementedError("P1-E: implementar en el servidor")

    def resumen(self) -> dict[str, int]:
        """Conteo por estado + totales, para el encabezado de la hoja.

        Ej.: ``{"total": 141, "validado": 120, "pendiente": 18,
        "observado": 2, "rechazado": 1, "sin_evidencia": 0}``.
        """
        raise NotImplementedError("P1-E: implementar en el servidor")

    def a_filas(self) -> list[dict[str, Any]]:
        """Aplana la matriz a filas planas para volcar a Excel/JSON.

        Una fila por (dato × source_ref): dato_id, etiqueta, valor, filename,
        página/celda, bbox (si hay), confianza_extraccion, confianza_interpretacion,
        estado, validado_por, validado_en, nota. Es la representación que
        consume el filler del papel de trabajo (Agente F).
        """
        raise NotImplementedError("P1-E: implementar en el servidor")
