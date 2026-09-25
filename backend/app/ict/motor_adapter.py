"""Puente de contrato motor → papel de trabajo ICT (P2-F · Task 9).

El motor (`motor-auditoria-analitica`, `motor/exportar_excepciones.py`) produce
la especificación de la hoja EXCEPCIONES como datos puros:

    {"hoja": "EXCEPCIONES",
     "columnas": ["regla_id", "nia", ...],          # nombres planos (clave)
     "filas": [{"regla_id": ..., "monto_expuesto": "12500.00", ...}, ...],
     "resumen": {"total_excepciones", "monto_total",
                 "por_severidad", "monto_por_severidad"}}

La capa de presentación del runner (`exceptions_sheet.build_exceptions_sheet`)
espera un `EspecHojaExcepciones` más rico, con las columnas como objetos
`{clave, titulo, tipo}` (el `tipo` gobierna formato/alineación en Excel) y con
metadatos de trazabilidad (`titulo`, `engine_version`, `generado_en`, `run_id`).

Este módulo es la ÚNICA capa que traduce entre ambos contratos. No recalcula
nada (el `resumen` del motor pasa tal cual: "Python calcula, la presentación no
recalcula"); solo enriquece las columnas planas con su título y tipo de
presentación, y adjunta la trazabilidad. Así, cuando el flujo ICT disponga de la
salida del motor, `service.generate_excel` puede volcar la hoja con una sola
llamada, sin decidir formato por columna.

Alcance deliberado: aquí se cubre SOLO la hoja EXCEPCIONES. El puente del sello
(`motor.exportar_excepciones.sellar_salida` → `sealing.SelloSalida`) NO se
implementa todavía: el `Sello` del motor sella sobre los BYTES del entregable
(`sha256_contenido`), mientras que la "nota de circularidad" de `sealing.py`
asume que `hash_salida` es el hash de la SALIDA DETERMINISTA del motor (no del
.xlsx), embebido en el libro. Reconciliar ambos es una decisión de diseño
pendiente (qué se sella y dónde se registra el hash del .xlsx), no un simple
renombre de claves; se resolverá al cablear el sello en `generate_excel`.
"""
from __future__ import annotations

import datetime

from backend.app.ict.exceptions_sheet import (
    ColumnaExcepciones,
    EspecHojaExcepciones,
)

#: Título y tipo de presentación de cada columna canónica del motor
#: (`motor.exportar_excepciones.COLUMNAS_EXCEPCIONES`). El `tipo` es un
#: `TipoColumna` de `exceptions_sheet` (gobierna formato/alineación en Excel).
_COLUMNAS_MOTOR: dict[str, tuple[str, str]] = {
    "regla_id": ("Regla", "texto"),
    "nia": ("NIA", "nia"),
    "entidad_tipo": ("Tipo de entidad", "texto"),
    "entidad_id": ("Entidad", "texto"),
    "monto_expuesto": ("Monto expuesto", "monto"),
    "severidad": ("Severidad", "severidad"),
    "mensaje": ("Detalle", "texto"),
    "evidencia": ("Evidencia", "texto"),
    "hash": ("Hash", "hash"),
}

#: Título por defecto de la hoja (el motor no lo provee).
TITULO_POR_DEFECTO = "Excepciones detectadas por el motor analítico"


def _columna(clave: str) -> ColumnaExcepciones:
    """Enriquerce un nombre de columna del motor con su título y tipo.

    Defensivo: una columna nueva que el motor agregue y que aún no esté en
    `_COLUMNAS_MOTOR` no rompe el volcado — se presenta como texto con un
    título legible derivado de la clave.
    """
    titulo, tipo = _COLUMNAS_MOTOR.get(clave, (clave.replace("_", " ").capitalize(), "texto"))
    return {"clave": clave, "titulo": titulo, "tipo": tipo}


def spec_motor_a_espec(
    spec_motor: dict,
    *,
    engine_version: str = "",
    run_id: str = "",
    generado_en: str | None = None,
    titulo: str = TITULO_POR_DEFECTO,
) -> EspecHojaExcepciones:
    """Traduce la spec del motor a un `EspecHojaExcepciones` del runner.

    `spec_motor` es el dict que devuelve
    `motor.exportar_excepciones.especificar_hoja_excepciones(...)`. Las `filas`
    y el `resumen` pasan sin tocarse (sus claves ya coinciden); las `columnas`
    (nombres planos) se enriquecen a `{clave, titulo, tipo}`. `generado_en` por
    defecto es el instante actual en ISO-8601 si no se provee.

    Lanza `ValueError` si la spec no trae `columnas`/`filas` (contrato roto del
    motor), para fallar en la frontera y no escribir una hoja inconsistente.
    """
    if not isinstance(spec_motor, dict):
        raise ValueError("la spec del motor debe ser un dict")
    if "columnas" not in spec_motor or "filas" not in spec_motor:
        raise ValueError("spec del motor incompleta: faltan 'columnas'/'filas'")

    columnas = [_columna(str(c)) for c in spec_motor["columnas"]]
    if generado_en is None:
        generado_en = datetime.datetime.now(datetime.timezone.utc).isoformat()

    espec: EspecHojaExcepciones = {
        "titulo": titulo,
        "columnas": columnas,
        "filas": list(spec_motor["filas"]),
        "resumen": dict(spec_motor.get("resumen", {})),
        "engine_version": engine_version,
        "generado_en": generado_en,
        "run_id": run_id,
    }
    return espec
