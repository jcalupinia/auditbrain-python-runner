"""Lectura nativa de archivos Power BI (.pbix) usando pbixray.

A diferencia de `powerbi_bridge.py` (que requiere que el usuario exporte
manualmente desde Power BI Desktop), este módulo lee el `.pbix` directamente:
- Tablas con datos reales (VertiPaq decompression).
- Medidas DAX definidas en el modelo.
- Queries M (Power Query) usadas para cargar datos.
- Metadata del modelo: relaciones, columnas, tipos.

Limitaciones conocidas:
- pbixray lee el MODELO de datos, NO la parte visual del reporte
  (slicers, gráficos, layouts). Para visuales hay que usar Power BI
  Desktop o el JSON del Report layer.
- Archivos .pbix muy grandes (>500 MB) pueden exceder el rlimit de
  memoria en el plan starter. Para esos casos usar
  `powerbi_bridge.ingest_export()` con CSV exportado.

Uso:

    from backend.app.utils import pbix_native

    if pbix_native.is_available():
        info = pbix_native.quick_overview("ventas.pbix")
        # {'tables': ['DimCliente', 'FactVentas'], 'table_count': 2, ...}

        df = pbix_native.read_table("ventas.pbix", "FactVentas")
        # DataFrame con las filas reales de la tabla

        measures = pbix_native.list_dax_measures("ventas.pbix")
        # {'Total Ventas': 'SUM(FactVentas[Monto])', ...}
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)


class PBIXUnavailable(RuntimeError):
    """pbixray no está instalado en este entorno."""


class PBIXError(RuntimeError):
    """Error al leer el archivo .pbix."""


def is_available() -> bool:
    """Devuelve True si la librería pbixray está disponible.

    Permite que el resto del código haga fallback elegante a
    `powerbi_bridge` (export CSV/Excel) si pbixray no está instalada.
    """
    try:
        import pbixray  # noqa: F401
        return True
    except ImportError:
        return False


def _require_lib():
    """Importa pbixray o levanta error claro."""
    try:
        from pbixray import PBIXRay
        return PBIXRay
    except ImportError as exc:
        raise PBIXUnavailable(
            "pbixray no está instalado. Añadir 'pbixray' a "
            "requirements-prod.txt."
        ) from exc


def _open(pbix_path: str | Path):
    """Abre un .pbix y devuelve el objeto PBIXRay."""
    p = Path(pbix_path)
    if not p.is_file():
        raise PBIXError(f"Archivo no encontrado: {pbix_path}")
    if p.suffix.lower() not in (".pbix", ".pbit"):
        raise PBIXError(
            f"Extensión {p.suffix} no soportada. Usar .pbix o .pbit."
        )

    PBIXRay = _require_lib()
    try:
        return PBIXRay(str(p))
    except Exception as exc:
        raise PBIXError(f"No se pudo abrir el .pbix: {exc}") from exc


def list_tables(pbix_path: str | Path) -> list[str]:
    """Lista los nombres de tablas del modelo."""
    model = _open(pbix_path)
    try:
        return list(model.tables)
    except Exception as exc:
        raise PBIXError(f"Error listando tablas: {exc}") from exc


def read_table(pbix_path: str | Path, table_name: str) -> pd.DataFrame:
    """Lee una tabla del modelo como DataFrame.

    Para tablas grandes ojo con el rlimit de memoria. Si el .pbix
    tiene tablas de millones de filas considera filtrarlas antes
    desde Power BI Desktop o usar `read_table_columns` (proyección).
    """
    model = _open(pbix_path)
    try:
        df = model.get_table(table_name)
        if df is None:
            raise PBIXError(
                f"Tabla '{table_name}' no encontrada. "
                f"Disponibles: {list(model.tables)}"
            )
        return df
    except PBIXError:
        raise
    except Exception as exc:
        raise PBIXError(f"Error leyendo tabla {table_name}: {exc}") from exc


def list_dax_measures(pbix_path: str | Path) -> dict:
    """Devuelve {nombre_medida: expresión_dax} del modelo."""
    model = _open(pbix_path)
    try:
        measures = getattr(model, "dax_measures", None)
        if measures is None:
            return {}
        # pbixray puede devolverlo como DataFrame o dict según versión.
        if isinstance(measures, pd.DataFrame):
            if "Name" in measures.columns and "Expression" in measures.columns:
                return dict(zip(measures["Name"], measures["Expression"]))
            # Fallback genérico
            return measures.to_dict(orient="records")
        return dict(measures)
    except Exception as exc:
        log.warning("No se pudieron extraer medidas DAX: %s", exc)
        return {}


def list_m_queries(pbix_path: str | Path) -> dict:
    """Devuelve {nombre_query: código_M} de Power Query."""
    model = _open(pbix_path)
    try:
        queries = getattr(model, "power_query", None) or getattr(
            model, "m_queries", None
        )
        if queries is None:
            return {}
        if isinstance(queries, pd.DataFrame):
            if "TableName" in queries.columns and "Expression" in queries.columns:
                return dict(zip(queries["TableName"], queries["Expression"]))
            return queries.to_dict(orient="records")
        return dict(queries)
    except Exception as exc:
        log.warning("No se pudieron extraer queries M: %s", exc)
        return {}


def list_relationships(pbix_path: str | Path) -> list[dict]:
    """Devuelve la lista de relaciones del modelo."""
    model = _open(pbix_path)
    try:
        rels = getattr(model, "relationships", None)
        if rels is None:
            return []
        if isinstance(rels, pd.DataFrame):
            return rels.to_dict(orient="records")
        return list(rels)
    except Exception as exc:
        log.warning("No se pudieron extraer relaciones: %s", exc)
        return []


def quick_overview(pbix_path: str | Path) -> dict:
    """Resumen rápido del modelo: ideal para preview en UI.

    Returns:
        {
          "tables": ["DimCliente", "FactVentas", ...],
          "table_count": int,
          "measures_count": int,
          "queries_count": int,
          "relationships_count": int,
          "file_size_bytes": int,
          "file_size_mb": float,
        }
    """
    model = _open(pbix_path)
    p = Path(pbix_path)
    size = p.stat().st_size

    try:
        tables = list(model.tables) if hasattr(model, "tables") else []
    except Exception:
        tables = []

    measures = list_dax_measures(pbix_path)
    queries = list_m_queries(pbix_path)
    rels = list_relationships(pbix_path)

    return {
        "tables": tables,
        "table_count": len(tables),
        "measures_count": len(measures),
        "queries_count": len(queries),
        "relationships_count": len(rels),
        "file_size_bytes": size,
        "file_size_mb": round(size / (1024 * 1024), 2),
    }


def find_business_tables(pbix_path: str | Path) -> dict:
    """Heurística: separa tablas de hechos (Fact) vs dimensiones (Dim).

    Útil para análisis de modelos no familiares. Basa la clasificación
    en convenciones de nombres comunes en el sector.
    """
    tables = list_tables(pbix_path)
    fact = [t for t in tables if t.lower().startswith(("fact", "hechos", "f_"))]
    dim = [t for t in tables if t.lower().startswith(("dim", "d_", "lkp"))]
    other = [t for t in tables if t not in fact and t not in dim]
    return {"fact": fact, "dim": dim, "other": other}
