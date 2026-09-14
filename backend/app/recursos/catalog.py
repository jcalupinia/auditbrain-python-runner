"""Recursos gratuitos que requieren registro (lista blanca)."""

from __future__ import annotations

from dataclasses import dataclass

# Contacto de la firma para el correo y para ejercer derechos LOPDP
# (coincide con public/politica-datos/ del mini-sitio).
CONTACTO = "jcalupinia@auditconsulting.ec"


@dataclass(frozen=True)
class Recurso:
    slug: str
    titulo: str
    url: str


_RECURSOS = {
    r.slug: r
    for r in (
        Recurso(
            slug="ir-personas-naturales-2026",
            titulo="Calculadora de Impuesto a la Renta de Personas Naturales 2026",
            url="https://recursos.audit-ia.ec/ir-personas-naturales-2026/",
        ),
    )
}


def get_recurso(slug: str) -> Recurso | None:
    return _RECURSOS.get(slug)
