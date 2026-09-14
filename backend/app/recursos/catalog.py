"""Recursos gratuitos con acceso por cuenta (lista blanca)."""

from __future__ import annotations

from dataclasses import dataclass

# Contacto de la firma para el correo y para ejercer derechos LOPDP
# (coincide con public/politica-datos/ del mini-sitio).
CONTACTO = "jcalupinia@auditconsulting.ec"

# Home del mini-sitio: el correo de acceso lleva aquí (no a rec.url) para que
# el usuario abra el login sobre la página de recursos, no directo a la calculadora.
RECURSOS_HOME = "https://recursos.audit-ia.ec/"


def enlace_acceso(slug: str) -> str:
    return f"{RECURSOS_HOME}#ingresar-{slug}"


@dataclass(frozen=True)
class Recurso:
    slug: str
    titulo: str
    url: str
    # True: cualquiera se registra y obtiene acceso. False: solo por otorgamiento del admin.
    registro_abierto: bool


_RECURSOS = {
    r.slug: r
    for r in (
        Recurso(
            slug="ir-personas-naturales-2026",
            titulo="Calculadora de Impuesto a la Renta de Personas Naturales 2026",
            url="https://recursos.audit-ia.ec/ir-personas-naturales-2026/",
            registro_abierto=True,
        ),
        Recurso(
            slug="anticipo-ir-2026",
            titulo="Calculadora del Anticipo IR sobre Utilidades No Distribuidas 2026",
            url="https://recursos.audit-ia.ec/anticipo-ir-2026/",
            registro_abierto=False,
        ),
    )
}


def get_recurso(slug: str) -> Recurso | None:
    return _RECURSOS.get(slug)


def recursos() -> list[Recurso]:
    return list(_RECURSOS.values())
