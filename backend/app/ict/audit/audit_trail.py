"""Audit trail verificable de las llamadas LLM del ICT (control 3 del CLAUDE.md).

Cada interpretación de un anexo (éxito, fallback o error degradado) deja un
registro firmado: qué modelo se usó, cuántos tokens, la huella del prompt
(``hash_input``), la huella de la salida (``hash_output``), la confianza
autoreportada y si pide revisión humana. Los registros se **encadenan** con el
mismo patrón que ``forge_decisions`` y la bitácora del ciclo
(``sha256("|".join(campos) + "|" + prev_hash)``, ``GENESIS`` para el primero):
alterar o borrar un registro intermedio rompe la verificación.

Módulo **puro** (sin BD ni red ni Anthropic): recibe los datos ya calculados y
devuelve la cadena. El interpreter arma las entradas; el servicio la persiste y
la renderiza en el papel de trabajo. Determinista: mismos datos → mismo hash.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Sequence

#: Hash "cero" del que cuelga el primer registro. Igual que forge/bitácora.
GENESIS = "0" * 64

#: Campos firmados, en ORDEN FIJO (contrato: reordenar invalida cadenas escritas).
_CAMPOS = (
    "seq",
    "ts",
    "anexo_codigo",
    "modelo",
    "tokens",
    "hash_input",
    "hash_output",
    "confianza",
    "requiere_revision",
)


class CadenaIACorrupta(Exception):
    """La verificación del audit trail IA falló: un registro fue alterado/borrado."""

    def __init__(self, seq: int, motivo: str) -> None:
        self.seq = seq
        super().__init__(f"audit trail IA corrupto en seq={seq}: {motivo}")


@dataclass(frozen=True)
class RegistroIA:
    """Un registro firmado de una llamada de interpretación IA."""

    seq: int
    ts: str
    anexo_codigo: str
    modelo: str
    tokens: int
    hash_input: str
    hash_output: str
    confianza: str
    requiere_revision: bool
    prev_hash: str
    hash: str

    def a_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq, "ts": self.ts, "anexo_codigo": self.anexo_codigo,
            "modelo": self.modelo, "tokens": self.tokens, "hash_input": self.hash_input,
            "hash_output": self.hash_output, "confianza": self.confianza,
            "requiere_revision": self.requiere_revision, "prev_hash": self.prev_hash,
            "hash": self.hash,
        }


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def hash_input_de(prompt: str) -> str:
    """Huella del prompt enviado al modelo (entrada de la llamada)."""
    return _sha(prompt or "")


def hash_output_de(interpretacion: Any) -> str:
    """Huella de la salida. Acepta un modelo Pydantic (``model_dump_json``), un
    dict o un texto: en todos los casos serializa de forma canónica y hashea."""
    if hasattr(interpretacion, "model_dump_json"):
        try:
            blob = interpretacion.model_dump_json()
        except Exception:
            blob = str(interpretacion)
    elif isinstance(interpretacion, (dict, list)):
        blob = json.dumps(interpretacion, sort_keys=True, ensure_ascii=False, default=str)
    else:
        blob = str(interpretacion)
    return _sha(blob)


def _material(entrada: dict[str, Any]) -> str:
    return "|".join(str(entrada.get(c, "")) for c in _CAMPOS)


def compute_hash(entrada: dict[str, Any], prev_hash: str) -> str:
    """Hash firmado de un registro. Función pura: mismos datos → mismo hash."""
    return _sha(f"{_material(entrada)}|{prev_hash}")


def construir_trail(entradas: Sequence[dict[str, Any]]) -> list[RegistroIA]:
    """Encadena una secuencia de entradas (una por llamada IA, en orden) en un
    trail firmado. Cada entrada trae: ``anexo_codigo``, ``modelo``, ``tokens``,
    ``hash_input``, ``hash_output``, ``confianza``, ``requiere_revision``, ``ts``.
    Asigna ``seq`` contiguo desde 1 y encadena ``prev_hash``/``hash`` desde GENESIS.
    """
    registros: list[RegistroIA] = []
    prev = GENESIS
    for i, e in enumerate(entradas, start=1):
        firma = {
            "seq": i,
            "ts": str(e.get("ts", "")),
            "anexo_codigo": str(e.get("anexo_codigo", "")),
            "modelo": str(e.get("modelo", "")),
            "tokens": int(e.get("tokens", 0) or 0),
            "hash_input": str(e.get("hash_input", "")),
            "hash_output": str(e.get("hash_output", "")),
            "confianza": str(e.get("confianza", "")),
            "requiere_revision": bool(e.get("requiere_revision", False)),
        }
        h = compute_hash(firma, prev)
        registros.append(RegistroIA(prev_hash=prev, hash=h, **firma))
        prev = h
    return registros


def verificar_cadena_ia(registros: Sequence[RegistroIA]) -> list[RegistroIA]:
    """Verifica el trail y lo devuelve ordenado. Lanza ``CadenaIACorrupta`` si un
    registro fue alterado o borrado. Cadena vacía → lista vacía."""
    ordenados = sorted(registros, key=lambda r: r.seq)
    prev = GENESIS
    for i, r in enumerate(ordenados, start=1):
        if r.seq != i:
            raise CadenaIACorrupta(r.seq or 0, f"seq no contiguo (esperado {i})")
        if (r.prev_hash or "") != prev:
            raise CadenaIACorrupta(i, "prev_hash no encadena con el registro anterior")
        firma = {
            "seq": r.seq, "ts": r.ts, "anexo_codigo": r.anexo_codigo, "modelo": r.modelo,
            "tokens": r.tokens, "hash_input": r.hash_input, "hash_output": r.hash_output,
            "confianza": r.confianza, "requiere_revision": r.requiere_revision,
        }
        if compute_hash(firma, prev) != (r.hash or ""):
            raise CadenaIACorrupta(i, "el hash no coincide (registro alterado)")
        prev = r.hash
    return ordenados
