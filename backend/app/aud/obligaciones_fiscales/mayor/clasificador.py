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

# 'tarifa' es la columna "tarifa de retención" del papel de trabajo: solo
# tiene sentido para las categorías de retención (defecto 8a).
CATEGORIAS_CON_TARIFA = frozenset({"RET_RENTA", "RET_IVA"})


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
    declaradas: dict[str, str] | None = None,
) -> ResultadoClasificacion:
    """Clasifica una cuenta con toda la evidencia disponible.

    ``declaradas`` ({codigo: categoria}) son las cuentas que vienen de un Mayor
    específico: el auditor declaró su categoría al subir el archivo, así que esa
    categoría MANDA (confianza alta, origen 'declarada'), sin pasar por las
    señales. Un archivo específico puede traer varias cuentas, todas con la
    misma categoría declarada.
    """
    historial = historial or {}
    clasificadas = clasificadas or {}
    declaradas = declaradas or {}

    if perfil.codigo in declaradas:
        categoria = declaradas[perfil.codigo]
        tarifa = (
            sig.extraer_tarifa(perfil.nombre)
            if categoria in CATEGORIAS_CON_TARIFA
            else None
        )
        return ResultadoClasificacion(
            codigo=perfil.codigo,
            nombre=perfil.nombre,
            categoria=categoria,
            confianza="alta",
            origen="declarada",
            tarifa=tarifa,
            puntajes={categoria: sig.PESO_HISTORIAL},
            senales=[
                Senal(
                    categoria=categoria,
                    puntaje=sig.PESO_HISTORIAL,
                    motivo="categoría declarada por el auditor (Mayor específico)",
                )
            ],
        )

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
    tarifa = sig.extraer_tarifa(perfil.nombre) if categoria in CATEGORIAS_CON_TARIFA else None

    return ResultadoClasificacion(
        codigo=perfil.codigo,
        nombre=perfil.nombre,
        categoria=categoria,
        confianza=confianza,
        origen=origen,
        tarifa=tarifa,
        puntajes=puntajes,
        # Se guardan TODAS las señales, incluidas las penalizaciones
        # (puntaje negativo): son la evidencia mas informativa para el
        # auditor (ej. "saldo deudor contradice naturaleza ingreso").
        # ResultadoClasificacion.justificacion filtra lo que se imprime.
        senales=senales,
    )


def clasificar(
    perfiles: dict[str, PerfilCuenta],
    *,
    historial: dict[str, str] | None = None,
    declaradas: dict[str, str] | None = None,
) -> list[ResultadoClasificacion]:
    """Clasifica todas las cuentas del mayor en dos pasadas.

    ``declaradas`` ({codigo: categoria}) fija la categoría de las cuentas que
    vienen de un Mayor específico (el auditor la declaró al subirlo).
    """
    historial = historial or {}
    declaradas = declaradas or {}

    primera = {
        codigo: clasificar_cuenta(p, historial=historial, declaradas=declaradas)
        for codigo, p in perfiles.items()
    }
    # Solo lo resuelto con confianza alta sirve de apoyo para las demás (las
    # declaradas entran acá porque quedan con confianza alta).
    apoyo = {
        codigo: r.categoria
        for codigo, r in primera.items()
        if r.categoria and r.confianza == "alta"
    }

    segunda = [
        clasificar_cuenta(p, historial=historial, clasificadas=apoyo, declaradas=declaradas)
        for p in perfiles.values()
    ]
    return sorted(segunda, key=lambda r: r.codigo)
