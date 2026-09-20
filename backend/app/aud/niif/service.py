"""Transiciones de estado de la ficha NIIF.

Un solo camino, sin atajos:

    en_diseño ──marcar probada──> probada ──generar código──> enviada

- Solo se edita el contenido mientras está ``en_diseño``.
- No se salta de ``en_diseño`` a ``enviada``: primero alguien tiene que
  verificar que la prueba funciona, y ese alguien queda registrado.
- ``enviada`` es terminal.
"""

from __future__ import annotations

import datetime

from backend.app.aud.niif.models import NiifFicha
from backend.app.aud.niif.schemas import (
    ESTADO_EN_DISENO,
    ESTADO_ENVIADA,
    ESTADO_PROBADA,
)
from backend.app.auth.models import User

#: Única transición permitida desde cada estado.
TRANSICIONES: dict[str, set[str]] = {
    ESTADO_EN_DISENO: {ESTADO_PROBADA},
    ESTADO_PROBADA: {ESTADO_ENVIADA},
    ESTADO_ENVIADA: set(),
}


class TransicionInvalida(Exception):
    """El paso de estado pedido no existe en el circuito."""


def transicion_permitida(actual: str, nuevo: str) -> bool:
    return nuevo in TRANSICIONES.get(actual, set())


def _ahora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def aplicar_transicion(ficha: NiifFicha, nuevo: str, usuario: User) -> NiifFicha:
    """Mueve la ficha al siguiente estado dejando rastro de quién y cuándo.

    Lanza ``TransicionInvalida`` si el salto no está permitido.
    """
    if not transicion_permitida(ficha.estado, nuevo):
        raise TransicionInvalida(
            f"No se puede pasar de «{ficha.estado}» a «{nuevo}»."
        )

    ahora = _ahora()
    if nuevo == ESTADO_PROBADA:
        ficha.probada_por_user_id = usuario.id
        ficha.probada_por_email = usuario.email
        ficha.probada_en = ahora
    elif nuevo == ESTADO_ENVIADA:
        ficha.enviada_por_user_id = usuario.id
        ficha.enviada_por_email = usuario.email
        ficha.enviada_en = ahora

    ficha.estado = nuevo
    return ficha
