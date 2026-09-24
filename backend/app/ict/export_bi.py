"""Export del papel de trabajo ICT a dataset tabular para Power BI (REP-011).

Convierte el resultado del trabajo en tablas planas (esquema estrella) listas
para modelar en Power BI / Tableau / Looker, entregadas como un ZIP de CSV
UTF-8 con BOM y separador ";" (para que Excel en español las abra bien),
siguiendo el mismo criterio que `libro.csv_zip`.

Datos SOLO de lectura: se arman con lo que ya calcularon el motor y las hojas
del papel de trabajo (excepciones, parámetros, control de revisión, sello).
Ninguna cifra se recalcula aquí.

MODELO TABULAR (esquema estrella):
  - `hechos_excepciones`  : una fila por excepción (grano fino), con FKs a las
    dimensiones. Es la tabla de hechos principal.
  - `dim_anexo`           : catálogo de anexos (A1..A9, INDICE) + descripción.
  - `dim_severidad`       : P0/P1/P2 + etiqueta + orden de gravedad.
  - `dim_parametros`      : una fila con los parámetros del encargo (bloque U).
  - `dim_encargo`         : una fila con razón social, RUC, ejercicio, sello.
Cada CSV lleva encabezados estables (contrato del dataset): renombrarlos rompe
los reportes ya construidos en Power BI, así que se versionan con el sello.

REGLA DE CLAUDE.md: el papel de trabajo NIIF ya entrega CSV (ZIP) auditable;
esta salida es su equivalente para el ICT. Los importes van como texto Decimal
sin separador de miles y con punto decimal, para que Power BI los tipe como
número sin ambigüedad regional.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from backend.app.ict.exceptions_sheet import EspecHojaExcepciones
    from backend.app.ict.parametros_sheet import ParametrosEncargoDict
    from backend.app.ict.review_control_sheet import EventoRevision
    from backend.app.ict.sealing import SelloSalida

#: Nombres de archivo del dataset (contrato estable). Cambiarlos rompe los
#: modelos de Power BI ya construidos: versionarlos vía el sello, no renombrar.
TABLAS: tuple[str, ...] = (
    "hechos_excepciones",
    "dim_anexo",
    "dim_severidad",
    "dim_parametros",
    "dim_encargo",
)


class BIExportContexto(TypedDict, total=False):
    """Entrada del export BI."""

    session_data: dict
    excepciones: "EspecHojaExcepciones"
    parametros: "ParametrosEncargoDict"
    eventos_revision: list["EventoRevision"]
    sello: "SelloSalida"


@dataclass
class Tabla:
    """Una tabla del dataset: columnas + filas (valores ya formateados a str)."""

    nombre: str
    columnas: list[str]
    filas: list[list[str]] = field(default_factory=list)


@dataclass
class BIDataset:
    """Conjunto de tablas del modelo estrella, previo a serializar."""

    tablas: list[Tabla] = field(default_factory=list)

    def por_nombre(self, nombre: str) -> Tabla | None:
        return next((t for t in self.tablas if t.nombre == nombre), None)


def build_bi_dataset(contexto: BIExportContexto) -> BIDataset:
    """Construye el modelo tabular (esquema estrella) en memoria.

    Comportamiento esperado (a implementar con TDD en el servidor):
        1. `hechos_excepciones`: una fila por `excepciones["filas"]`, con
           columnas estables (id/hash, anexo, casillero, severidad, monto,
           nia, mensaje, estado, run_id). Importes como Decimal-str con punto.
        2. `dim_anexo`, `dim_severidad`: catálogos fijos.
        3. `dim_parametros`: una fila desde `parametros`.
        4. `dim_encargo`: una fila desde `session_data` + `sello`.
        5. Devolver `BIDataset` con las `TABLAS` en orden.
    """
    session_data = contexto.get("session_data") or {}
    excepciones = contexto.get("excepciones") or {}
    parametros = contexto.get("parametros") or {}
    sello = contexto.get("sello") or {}

    filas_exc = list(excepciones.get("filas") or [])
    run_id = str(excepciones.get("run_id", "") or "")

    # --- hechos_excepciones: una fila por excepción (grano fino) ---
    hechos_cols = [
        "id_excepcion", "hash", "anexo", "casillero", "severidad",
        "monto", "nia", "estado", "mensaje", "run_id",
    ]
    hechos = Tabla("hechos_excepciones", hechos_cols)
    for idx, fila in enumerate(filas_exc, start=1):
        hechos.filas.append([
            str(idx),
            _s(fila.get("hash")),
            _s(fila.get("anexo")),
            _s(fila.get("casillero")),
            _s(fila.get("severidad")),
            _monto(fila.get("monto")),
            _s(fila.get("nia")),
            _s(fila.get("estado")),
            _s(fila.get("mensaje")),
            run_id,
        ])

    # --- dim_anexo: catálogo fijo ---
    dim_anexo = Tabla("dim_anexo", ["anexo", "descripcion"])
    for anexo, desc in _CAT_ANEXOS:
        dim_anexo.filas.append([anexo, desc])

    # --- dim_severidad: catálogo fijo ---
    dim_severidad = Tabla("dim_severidad", ["severidad", "etiqueta", "orden_gravedad"])
    for sev, etiqueta, orden in _CAT_SEVERIDAD:
        dim_severidad.filas.append([sev, etiqueta, str(orden)])

    # --- dim_parametros: una fila con los parámetros del encargo ---
    param_cols = [k for k, _e, _t in _PARAM_KEYS]
    dim_parametros = Tabla("dim_parametros", param_cols)
    dim_parametros.filas.append([
        _monto(parametros.get(k)) if t == "monto" else _s(parametros.get(k))
        for k, _e, t in _PARAM_KEYS
    ])

    # --- dim_encargo: una fila con razón social, RUC, ejercicio, sello ---
    dim_encargo = Tabla("dim_encargo", [
        "razon_social", "ruc", "ejercicio_fiscal",
        "version_app", "version_motor", "run_id", "hash_salida",
    ])
    dim_encargo.filas.append([
        _s(session_data.get("razon_social")),
        _s(session_data.get("ruc")),
        _s(session_data.get("ejercicio_fiscal")),
        _s(sello.get("version_app")),
        _s(sello.get("version_motor")),
        _s(sello.get("run_id") or run_id),
        _s(sello.get("hash_salida")),
    ])

    orden = {
        "hechos_excepciones": hechos,
        "dim_anexo": dim_anexo,
        "dim_severidad": dim_severidad,
        "dim_parametros": dim_parametros,
        "dim_encargo": dim_encargo,
    }
    return BIDataset(tablas=[orden[n] for n in TABLAS])


#: Catálogos fijos del modelo estrella.
_CAT_ANEXOS: tuple[tuple[str, str], ...] = (
    ("INDICE", "Índice del ICT"),
    ("A1", "Conciliación tributaria / balance"),
    ("A2", "Ingresos"),
    ("A3", "Costos y gastos"),
    ("A4", "Activos"),
    ("A5", "Pasivos y patrimonio"),
    ("A6", "Retenciones en la fuente"),
    ("A7", "IVA"),
    ("A8", "Impuesto a la renta"),
    ("A9", "Otros"),
)

_CAT_SEVERIDAD: tuple[tuple[str, str, int], ...] = (
    ("P0", "Crítica", 0),
    ("P1", "Alta", 1),
    ("P2", "Media", 2),
)

_PARAM_KEYS: tuple[tuple[str, str, str], ...] = (
    ("ejercicio_inicio", "Inicio del ejercicio", "texto"),
    ("ejercicio_fin", "Fin del ejercicio", "texto"),
    ("materialidad", "Materialidad global", "monto"),
    ("materialidad_ejecucion", "Materialidad de ejecución", "monto"),
    ("umbral_insignificante", "Umbral insignificante", "monto"),
    ("umbral_aprobacion", "Umbral de aprobación", "monto"),
    ("error_tolerable", "Error tolerable", "monto"),
    ("confianza", "Nivel de confianza", "texto"),
    ("semilla", "Semilla de muestreo", "texto"),
)


def _s(value) -> str:
    """Serializa a str plano (sin None)."""
    return "" if value is None else str(value)


def _monto(value) -> str:
    """Normaliza un importe a Decimal-str con punto decimal, sin separador de
    miles, para que Power BI lo tipe como número sin ambigüedad regional."""
    if value is None or value == "":
        return ""
    try:
        return str(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return str(value)


def export_bi_csv_zip(contexto: BIExportContexto) -> bytes:
    """Serializa `build_bi_dataset(contexto)` a un ZIP de CSV para Power BI.

    Comportamiento esperado (a implementar con TDD en el servidor):
        1. `dataset = build_bi_dataset(contexto)`.
        2. Un CSV por tabla, UTF-8 con BOM (\\ufeff) y separador ";".
        3. Nombre de archivo `{tabla.nombre}.csv`.
        4. Devolver los bytes del ZIP (patrón `libro.csv_zip`).
    """
    dataset = build_bi_dataset(contexto)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for tabla in dataset.tablas:
            sio = io.StringIO()
            w = csv.writer(sio, delimiter=";")
            w.writerow(tabla.columnas)
            for fila in tabla.filas:
                w.writerow(fila)
            # UTF-8 con BOM para que Excel en español lo abra bien.
            z.writestr(f"{tabla.nombre}.csv", ("﻿" + sio.getvalue()).encode("utf-8"))
    return buf.getvalue()
