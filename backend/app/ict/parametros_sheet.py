"""Hoja "PARÁMETROS" del papel de trabajo ICT (REP-005).

Deja constancia, en el propio libro, de los parámetros del encargo con los
que se corrió el motor: materialidad, materialidad de ejecución, umbrales,
rango del ejercicio, feriados, semilla, confianza. Sin esto, un resultado
"sin excepciones" no es interpretable: NIA 320/450/530 exigen documentar el
umbral aplicado.

CONTRATO DE ENTRADA. Los parámetros los produce y valida el motor
(`motor.parametros.ParametrosEncargo.a_dict()` — bloque U del formulario
AUT-2026-001). Esta capa asume ese dict serializado como ENTRADA y SOLO lo
presenta; no re-valida reglas cruzadas (eso ya lo hizo el motor).

REGLAS DE CLAUDE.md:
  - Importes como Decimal(str), number_format `#,##0.00`, NUNCA float.
  - Hoja interna del auditor → ocultar en SRI (agregar "PARÁMETROS" a
    `service.HIDDEN_SHEETS_FOR_SRI`).
  - `_safe_text` sobre texto; el Excel no debe pedir reparación.
  - Formato profesional: dos columnas (Parámetro / Valor), bordes thin,
    encabezado de bloque en negrita 11, anchos explícitos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from openpyxl import Workbook

SHEET_NAME = "PARÁMETROS"


class ParametrosEncargoDict(TypedDict, total=False):
    """Espejo del `ParametrosEncargo.a_dict()` del motor (bloque U).

    Los importes llegan como str (Decimal serializado); las fechas como
    ISO-8601; enteros como int. Se declara aquí solo para tipado del
    scaffold — la fuente de verdad es `motor.parametros`.
    """

    ejercicio_inicio: str
    ejercicio_fin: str
    materialidad: str
    materialidad_ejecucion: str
    umbral_insignificante: str
    umbral_aprobacion: str
    feriados: list[str]
    hora_inicio: int
    hora_fin: int
    error_tolerable: str
    confianza: int
    semilla: int
    fecha_registro_es_contable: bool


#: Orden y etiquetas legibles de cada parámetro para la hoja. La clave es la
#: del dict del motor; el valor es (etiqueta visible, tipo de formato).
#: tipo: "monto" | "fecha" | "entero" | "texto" | "lista_fechas" | "booleano".
PARAMETROS_LAYOUT: tuple[tuple[str, str, str], ...] = (
    ("ejercicio_inicio", "Inicio del ejercicio", "fecha"),
    ("ejercicio_fin", "Fin del ejercicio", "fecha"),
    ("materialidad", "Materialidad global", "monto"),
    ("materialidad_ejecucion", "Materialidad de ejecución", "monto"),
    ("umbral_insignificante", "Umbral insignificante", "monto"),
    ("umbral_aprobacion", "Umbral de aprobación", "monto"),
    ("error_tolerable", "Error tolerable", "monto"),
    ("feriados", "Feriados considerados", "lista_fechas"),
    ("hora_inicio", "Hora laborable — inicio", "entero"),
    ("hora_fin", "Hora laborable — fin", "entero"),
    ("confianza", "Nivel de confianza (%)", "entero"),
    ("semilla", "Semilla de muestreo", "entero"),
    ("fecha_registro_es_contable", "Fecha de registro = fecha contable", "booleano"),
)


@dataclass
class ParametrosSheetResult:
    """Resultado del volcado para trazabilidad."""

    sheet_name: str = SHEET_NAME
    parametros_escritos: int = 0
    advertencias: list[str] = field(default_factory=list)


def build_parametros_sheet(
    wb: Workbook,
    parametros: ParametrosEncargoDict,
    *,
    session_data: dict | None = None,
) -> ParametrosSheetResult:
    """Crea/reemplaza la hoja PARÁMETROS en `wb`.

    Comportamiento esperado (a implementar con TDD en el servidor):
        1. Si la hoja existe, borrarla y recrearla.
        2. Título de marca + cabecera del encargo (razon_social/ruc/ejercicio).
        3. Recorrer `PARAMETROS_LAYOUT` en orden; por cada clave presente en
           `parametros`, escribir (etiqueta, valor) formateando según tipo:
           - monto → Decimal(str), number_format `#,##0.00`, derecha.
           - fecha → date.fromisoformat, number_format `yyyy-mm-dd`.
           - lista_fechas → unir con ", " y `_safe_text`.
           - entero/booleano → como int / "Sí"/"No".
        4. Si falta un parámetro obligatorio, escribir "(no informado)" y
           acumular una advertencia (no lanzar: la hoja debe generarse).
        5. Anchos de columna explícitos; bordes thin; registro en trace log.

    Raises:
        NotImplementedError: scaffold; implementación en el servidor.
    """
    raise NotImplementedError(
        "build_parametros_sheet: scaffold P2-F (REP-005). Ver plan "
        "docs/superpowers/plans/2026-09-24-p2f-workpaper.md, Task 2."
    )
