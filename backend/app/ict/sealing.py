"""Sello inmutable del libro ICT (REP-013).

Aplica al workbook el sello que produce el motor
(`motor-auditoria-analitica`): versión de la app/motor + timestamp + hash de
la salida determinista. Da a cualquier revisor (auditor, SRI, socio) una
huella verificable de QUÉ motor, con QUÉ parámetros y CUÁNDO se generó el
papel de trabajo.

CONTRATO CON EL MOTOR (Agente C · `motor/exportar_excepciones.py`, aún NO
existe). Este módulo asume como ENTRADA el dict que devolverá
`motor.exportar_excepciones.sellar_salida(...)`. Ese sello se calcula sobre
la SALIDA DETERMINISTA del motor (excepciones + parámetros + input_hashes del
ExecutionRun), NO sobre los bytes del .xlsx. Ver nota de circularidad abajo.

NOTA DE CIRCULARIDAD (crítica):
    No se puede escribir dentro del libro el hash de ESE MISMO libro ya
    escrito (cambiaría el hash). Por eso hay dos huellas distintas:
      - `SelloSalida.hash_salida`  → hash de la salida del motor (lo provee
        `sellar_salida`); SÍ se embebe en el libro.
      - hash del .xlsx final       → se calcula con `hash_workbook_bytes`
        DESPUÉS de guardar, y se registra FUERA del libro (nombre de archivo,
        ExecutionRun.output_hashes, bitácora). NUNCA dentro del propio libro.

REGLAS DE CLAUDE.md:
  - Hoja "SELLO" es interna del auditor → ocultarla en el archivo SRI
    (agregar "SELLO" a `service.HIDDEN_SHEETS_FOR_SRI`).
  - El sello NO reemplaza la protección de estructura existente
    (`_protect_workbook_structure`); la complementa.
  - Todo texto pasa por `_safe_text` (un hash o versión no debe romper Excel).
"""

from __future__ import annotations

import hashlib
from typing import TypedDict

from openpyxl import Workbook

SHEET_NAME = "SELLO"

#: Algoritmo de hash estándar del proyecto (coincide con runHash de NIIF).
ALGORITMO_HASH = "sha256"


class SelloSalida(TypedDict, total=False):
    """Salida esperada de `motor.exportar_excepciones.sellar_salida`.

    Es la huella de la SALIDA DETERMINISTA del motor, no del xlsx.
    """

    version_app: str        # versión de AUDIT-IA / app_version del ExecutionRun
    version_motor: str      # engine_version del motor
    timestamp: str          # ISO-8601 UTC de la corrida del motor
    hash_salida: str        # hash de excepciones+parámetros (hex, del motor)
    algoritmo: str          # "sha256"
    run_id: str             # ExecutionRun.run_id
    input_hashes: dict[str, str]   # {nombre_insumo: hash} — F-101, F-103, ...


def apply_seal(
    wb: Workbook,
    sello: SelloSalida,
    *,
    session_data: dict | None = None,
) -> None:
    """Embebe `sello` en `wb`: hoja "SELLO" legible + propiedades del libro.

    Comportamiento esperado (a implementar con TDD en el servidor):
        1. Escribir la hoja "SELLO" (crear/reemplazar) con: versión app,
           versión motor, timestamp, run_id, algoritmo, hash_salida y una
           tabla de input_hashes (un insumo por fila).
        2. Escribir el sello también en las propiedades del documento
           (`wb.properties`: `keywords`/`description`) y en custom properties
           si openpyxl las soporta, para que el sello viaje aunque se copien
           celdas.
        3. Un pie de página con `version · timestamp · hash_salida[:12]…`.
        4. `_safe_text` sobre todo valor de texto.

    NO calcula el hash del propio libro (ver NOTA DE CIRCULARIDAD).

    Raises:
        NotImplementedError: scaffold; implementación en el servidor.
    """
    raise NotImplementedError(
        "apply_seal: scaffold P2-F (REP-013). Ver plan "
        "docs/superpowers/plans/2026-09-24-p2f-workpaper.md, Task 7."
    )


def hash_workbook_bytes(wb_bytes: bytes, *, algoritmo: str = ALGORITMO_HASH) -> str:
    """Hash hex de los bytes del .xlsx ya serializado.

    Se usa DESPUÉS de `wb.save(...)`, sobre los bytes finales, para registrar
    la huella del archivo entregado FUERA del libro (ExecutionRun.output_hashes,
    nombre de archivo, bitácora). Función pura y determinista.

    Esta sí puede implementarse directamente (no depende del motor), pero se
    deja como scaffold para desarrollarla con su test de determinismo:
    mismo input → mismo hash; dos libros idénticos byte a byte → mismo hash.

    Raises:
        NotImplementedError: scaffold; implementación + test en el servidor.
    """
    raise NotImplementedError(
        "hash_workbook_bytes: scaffold P2-F (REP-013). "
        "Implementación de referencia: "
        "hashlib.new(algoritmo, wb_bytes).hexdigest()."
    )


def verify_seal(wb: Workbook, sello_esperado: SelloSalida) -> bool:
    """Comprueba que la hoja/propiedades "SELLO" de `wb` coincidan con
    `sello_esperado`. Para tests de regresión y para re-verificar un libro
    descargado. Scaffold.

    Raises:
        NotImplementedError: scaffold; implementación en el servidor.
    """
    raise NotImplementedError
