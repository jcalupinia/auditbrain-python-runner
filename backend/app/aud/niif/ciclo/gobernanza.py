"""Gobierno de la bitácora del encargo: hash-chain append-only (P2-G, ENG-020).

La bitácora ``PruebaEvento`` deja de ser una tabla suelta y pasa a ser una
**cadena verificable**, igual que ``ForgeDecision``: cada evento firma su
contenido y encadena con el hash del anterior, de modo que borrar o alterar un
evento intermedio rompe la verificación.

**Vendoring con contrato, no reutilización.** El primitivo de hash de Forge
(``backend/app/forge/engine/governance/audit.py``) firma OTROS campos (los de un
plan de código). El ciclo del encargo firma los suyos, así que aquí se calca el
patrón —mismo ``sha256("|".join(campos) + "|" + prev_hash)``, mismo ``GENESIS``,
campo ausente = ``""``— con su propio ``_CAMPOS_EVENTO``. El orden de esos campos
es un CONTRATO: cambiarlo invalida las cadenas ya escritas (por eso hay un test
de vector fijo que lo blinda).

La cadena es **por prueba** (``prueba_id``): cada prueba arranca en ``GENESIS``.
El ``parent_id`` versiona una prueba, no encadena entre versiones.
"""

from __future__ import annotations

import hashlib
from typing import Any, Sequence

#: Hash "cero" del que cuelga el primer evento de cada prueba. Igual que Forge.
GENESIS = "0" * 64

#: Campos firmados, en ORDEN FIJO. Contrato: no reordenar ni quitar sin subir
#: versión y recomputar (rompe la verificación de las cadenas existentes).
_CAMPOS_EVENTO = (
    "seq",
    "ts",
    "actor",
    "rol",
    "accion",
    "prueba_id",
    "revision",
    "estado_anterior",
    "estado_nuevo",
    "content_hash",
    "comentario",
)


class CadenaCorrupta(Exception):
    """La verificación de la bitácora falló: un evento fue alterado o borrado."""

    def __init__(self, seq: int, motivo: str) -> None:
        self.seq = seq
        super().__init__(f"bitácora corrupta en seq={seq}: {motivo}")


def compute_hash_evento(entrada: dict[str, Any], prev_hash: str) -> str:
    """Hash de un evento. Función pura: mismos datos → mismo hash.

    Campo ausente cuenta como cadena vacía (``str("")``), igual que en Forge.
    """
    material = "|".join(str(entrada.get(c, "")) for c in _CAMPOS_EVENTO)
    return hashlib.sha256(f"{material}|{prev_hash}".encode()).hexdigest()


def entrada_firmada(**campos: Any) -> dict[str, Any]:
    """Arma el dict firmable con exactamente las claves de ``_CAMPOS_EVENTO``.

    Ignora claves extra y rellena las faltantes con ``""``. Un valor ``None``
    explícito se normaliza a ``""`` (igual que ``entrada_de_evento`` al
    reconstruir), para que firmar y verificar den EXACTAMENTE lo mismo aunque
    ``estado_anterior`` sea ``None`` en el primer evento.
    """
    salida: dict[str, Any] = {}
    for c in _CAMPOS_EVENTO:
        v = campos.get(c, "")
        salida[c] = "" if v is None else v
    return salida


def entrada_de_evento(ev: Any) -> dict[str, Any]:
    """Reconstruye la entrada firmable desde una fila ``PruebaEvento``.

    Usa los MISMOS campos que se firmaron al escribir (ts desde ``creado_en``).
    Sirve para re-verificar la cadena.
    """
    creado = getattr(ev, "creado_en", None)
    return entrada_firmada(
        seq=getattr(ev, "seq", "") or "",
        ts=creado.isoformat() if creado is not None else "",
        actor=getattr(ev, "actor", "") or "",
        rol=getattr(ev, "rol", "") or "",
        accion=getattr(ev, "accion", "") or "",
        prueba_id=getattr(ev, "prueba_id", "") or "",
        revision=getattr(ev, "revision", "") or "",
        estado_anterior=getattr(ev, "estado_anterior", None) or "",
        estado_nuevo=getattr(ev, "estado_nuevo", None) or "",
        content_hash=getattr(ev, "content_hash", "") or "",
        comentario=getattr(ev, "comentario", None) or "",
    )


def verificar_cadena(eventos: Sequence[Any]) -> list[Any]:
    """Verifica una cadena de eventos (ya ordenados o no) y la devuelve ordenada.

    Comprueba, evento por evento en orden de ``seq``: que el ``seq`` sea
    contiguo desde 1, que ``prev_hash`` sea el ``hash`` del anterior (o
    ``GENESIS`` para el primero) y que el ``hash`` almacenado coincida con el
    recomputado. Cualquier discrepancia lanza ``CadenaCorrupta``. Cadena vacía
    → lista vacía (una prueba sin eventos no está corrupta).
    """
    ordenados = sorted(eventos, key=lambda e: (getattr(e, "seq", 0) or 0))
    prev = GENESIS
    for i, ev in enumerate(ordenados, start=1):
        seq = getattr(ev, "seq", None)
        if seq != i:
            raise CadenaCorrupta(seq or 0, f"seq no contiguo (esperado {i})")
        if (getattr(ev, "prev_hash", None) or "") != prev:
            raise CadenaCorrupta(i, "prev_hash no encadena con el evento anterior")
        esperado = compute_hash_evento(entrada_de_evento(ev), prev)
        if (getattr(ev, "hash", None) or "") != esperado:
            raise CadenaCorrupta(i, "el hash no coincide (evento alterado)")
        prev = esperado
    return ordenados


# --- Segregación de funciones: rol real del usuario (ENG-005/018) -----------

#: Roles del ciclo que pueden aprobar (espejo de ``reglas.PUEDEN_APROBAR``).
_MAPA_ROL = {
    "admin": "ADMIN",
    "socio": "SOCIO",
    "gerente": "GERENTE",
    "revisor": "REVISOR",
    "user": "PREPARADOR",
    "operador": "PREPARADOR",
    "client": "CLIENTE",
}


def rol_de_usuario(user: Any) -> str:
    """Traduce el rol del ``User`` autenticado al rol del ciclo del encargo.

    Punto único para que el servicio ejerza la segregación de funciones con el
    rol REAL (hoy el portal entra siempre como ``ADMIN``). No decide la
    transición —eso lo hace ``reglas.transicion``—, solo traduce.
    """
    crudo = str(getattr(user, "role", "") or "").strip().lower()
    return _MAPA_ROL.get(crudo, "ADMIN" if crudo in ("", "admin") else crudo.upper())
