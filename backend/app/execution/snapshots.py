"""Snapshot inmutable de una corrida: parámetros + engine_version + ruleset.

Una corrida solo es reproducible si podemos congelar TODO lo que influyó en
su resultado. Este módulo construye ese congelado ANTES de encolar
(``queue.enqueue`` lo recibe ya sellado en ``EnqueueRequest``) y lo verifica
después.

Capacidades:
  * **AUT-009** — Snapshot de parámetros del encargo (bloque U): materialidad,
    umbrales, feriados, semilla, etc. tal como estaban al disparar la corrida.
    Si el auditor cambia un parámetro mañana, la corrida de hoy conserva los
    suyos.
  * **AUT-010** — Inmutabilidad: el snapshot NO se muta una vez escrito. Se
    valida con ``verify_snapshot`` (recalcula el hash y compara).
  * **DATA-011** — ``engine_version`` congelada (versión del motor
    determinista con el que corrió).
  * **DATA-012** — ``ruleset_hash``: huella del conjunto de reglas activo
    (catálogo + versiones de cada regla), para saber que dos corridas
    "iguales" usaron exactamente el mismo cuerpo de reglas.

El snapshot es un dict JSON-serializable que se guarda en
``ExecutionRun.parameter_snapshot``. Su ``snapshot_hash`` entra en la
idempotency_key (ver ``queue.build_idempotency_key``).

ESTADO: IMPLEMENTADO a verde con TDD (Task P1-D). Pruebas en
tests/test_execution_*.py.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class RulesetRef:
    """Referencia al cuerpo de reglas activo en una corrida.

    ``rules`` es una lista de (regla_id, version) ordenada; ``ruleset_hash``
    es su sha256 canónico. Proviene de ``motor.nucleo.resumen_catalogo()``
    (Agente A ya expone ``version`` por regla) o del manifest de la audit app.
    """

    engine_version: str
    rules: tuple[tuple[str, str], ...]
    ruleset_hash: str


def compute_ruleset_hash(rules: list[tuple[str, str]]) -> str:
    """sha256 canónico del catálogo de reglas (id, version) — DATA-012.

    Ordena por id y serializa determinísticamente para que el hash sea
    estable frente al orden. Implementación de referencia (Task 8):

        canon = sorted((str(rid), str(ver)) for rid, ver in rules)
        blob = json.dumps(canon, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
    """
    canon = sorted((str(rid), str(ver)) for rid, ver in rules)
    blob = json.dumps(canon, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_snapshot(
    *,
    parameters: dict,
    engine_version: str,
    ruleset: RulesetRef,
    app_id: str,
    app_version: str,
) -> dict:
    """Construye el snapshot inmutable a guardar en ``parameter_snapshot``.

    ``parameters`` es el dict ya validado del bloque U (equivalente a
    ``motor.parametros.ParametrosEncargo.a_dict()``): importes como str
    (Decimal serializado), fechas ISO, etc. — JSON-serializable y estable.

    Devuelve un dict con forma:

        {
            "schema_version": "1",
            "app_id": ..., "app_version": ...,
            "engine_version": engine_version,
            "ruleset_hash": ruleset.ruleset_hash,
            "rules": [[id, version], ...],
            "parameters": parameters,            # snapshot bloque U (AUT-009)
            "snapshot_hash": "<sha256 de todo lo anterior>",  # AUT-010
        }

    El ``snapshot_hash`` se calcula sobre el contenido SIN incluirse a sí
    mismo (se agrega al final). Implementar en Task 8.
    """
    payload = {
        "schema_version": "1",
        "app_id": app_id,
        "app_version": app_version,
        "engine_version": engine_version,
        "ruleset_hash": ruleset.ruleset_hash,
        "rules": [[str(rid), str(ver)] for rid, ver in ruleset.rules],
        "parameters": parameters,
    }
    payload["snapshot_hash"] = snapshot_hash(payload)
    return payload


def snapshot_hash(payload: dict) -> str:
    """sha256 canónico de un snapshot (excluyendo la clave ``snapshot_hash``).

    JSON con sort_keys + separadores fijos para determinismo. Implementar en
    Task 8.
    """
    material = {k: v for k, v in payload.items() if k != "snapshot_hash"}
    blob = json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def verify_snapshot(payload: dict) -> bool:
    """True si el ``snapshot_hash`` guardado coincide con el recalculado.

    Detecta mutación posterior del snapshot (AUT-010). El servidor lo corre
    antes de reproducir o de mostrar la ficha de lineage; una discrepancia es
    un incidente de integridad, no un warning. Implementar en Task 8.
    """
    guardado = payload.get("snapshot_hash")
    if not guardado:
        return False
    return guardado == snapshot_hash(payload)
