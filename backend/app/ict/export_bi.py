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

from dataclasses import dataclass, field
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

    Raises:
        NotImplementedError: scaffold; implementación en el servidor.
    """
    raise NotImplementedError(
        "build_bi_dataset: scaffold P2-F (REP-011). Ver plan "
        "docs/superpowers/plans/2026-09-24-p2f-workpaper.md, Task 6."
    )


def export_bi_csv_zip(contexto: BIExportContexto) -> bytes:
    """Serializa `build_bi_dataset(contexto)` a un ZIP de CSV para Power BI.

    Comportamiento esperado (a implementar con TDD en el servidor):
        1. `dataset = build_bi_dataset(contexto)`.
        2. Un CSV por tabla, UTF-8 con BOM (\\ufeff) y separador ";".
        3. Nombre de archivo `{tabla.nombre}.csv`.
        4. Devolver los bytes del ZIP (patrón `libro.csv_zip`).

    Raises:
        NotImplementedError: scaffold; implementación en el servidor.
    """
    raise NotImplementedError(
        "export_bi_csv_zip: scaffold P2-F (REP-011). Ver plan "
        "docs/superpowers/plans/2026-09-24-p2f-workpaper.md, Task 6."
    )
