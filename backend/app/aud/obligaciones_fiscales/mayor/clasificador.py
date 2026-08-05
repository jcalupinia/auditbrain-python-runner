"""Combina las señales de una cuenta en una decisión explicable.

Dos pasadas: la primera clasifica con la evidencia propia de cada cuenta; la
segunda agrega las señales que dependen de cómo quedaron las demás
(contrapartidas y propagación por rama).
"""

from __future__ import annotations

from collections import defaultdict

from backend.app.aud.obligaciones_fiscales.mayor import senales as sig
from backend.app.aud.obligaciones_fiscales.mayor.tipos import (
    PerfilCuenta,
    ResultadoClasificacion,
    Senal,
)

UMBRAL_ALTA = 60
UMBRAL_MEDIA = 35
VENTAJA_MINIMA_ALTA = 25


def _acumular(senales: list[Senal]) -> dict[str, int]:
    puntajes: dict[str, int] = defaultdict(int)
    for s in senales:
        puntajes[s.categoria] += s.puntaje
    return dict(puntajes)


def _decidir(puntajes: dict[str, int]) -> tuple[str | None, str]:
    if not puntajes:
        return None, "baja"
    orden = sorted(puntajes.items(), key=lambda kv: kv[1], reverse=True)
    lider, punt_lider = orden[0]
    punt_segundo = orden[1][1] if len(orden) > 1 else 0
    if punt_lider <= 0:
        return None, "baja"
    if punt_lider >= sig.PESO_HISTORIAL:
        return lider, "alta"
    if punt_lider >= UMBRAL_ALTA and (punt_lider - punt_segundo) >= VENTAJA_MINIMA_ALTA:
        return lider, "alta"
    if punt_lider >= UMBRAL_MEDIA:
        return lider, "media"
    return lider, "baja"


def clasificar_cuenta(
    perfil: PerfilCuenta,
    *,
    historial: dict[str, str] | None = None,
    clasificadas: dict[str, str] | None = None,
) -> ResultadoClasificacion:
    """Clasifica una cuenta con toda la evidencia disponible."""
    historial = historial or {}
    clasificadas = clasificadas or {}

    senales: list[Senal] = []
    senales += sig.senal_historial(perfil, historial)
    senales += sig.senal_nombre(perfil)
    senales += sig.senal_codigo(perfil)
    senales += sig.senal_naturaleza(perfil)
    senales += sig.senal_movimientos(perfil)
    senales += sig.senal_contrapartidas(perfil, clasificadas)
    senales += sig.senal_rama(perfil, clasificadas)

    puntajes = _acumular(senales)
    categoria, confianza = _decidir(puntajes)
    origen = "historial" if perfil.codigo in historial else "reglas"

    return ResultadoClasificacion(
        codigo=perfil.codigo,
        nombre=perfil.nombre,
        categoria=categoria,
        confianza=confianza,
        origen=origen,
        tarifa=sig.extraer_tarifa(perfil.nombre),
        puntajes=puntajes,
        senales=[s for s in senales if s.puntaje > 0],
    )


def clasificar(
    perfiles: dict[str, PerfilCuenta],
    *,
    historial: dict[str, str] | None = None,
) -> list[ResultadoClasificacion]:
    """Clasifica todas las cuentas del mayor en dos pasadas."""
    historial = historial or {}

    primera = {
        codigo: clasificar_cuenta(p, historial=historial)
        for codigo, p in perfiles.items()
    }
    # Solo lo resuelto con confianza alta sirve de apoyo para las demás.
    apoyo = {
        codigo: r.categoria
        for codigo, r in primera.items()
        if r.categoria and r.confianza == "alta"
    }

    segunda = [
        clasificar_cuenta(p, historial=historial, clasificadas=apoyo)
        for p in perfiles.values()
    ]
    return sorted(segunda, key=lambda r: r.codigo)
