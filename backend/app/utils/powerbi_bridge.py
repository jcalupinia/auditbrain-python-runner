"""Bridge para ingestar datos exportados desde Power BI Desktop.

Limitación raíz: no existe librería Python pública para leer archivos
.pbix directamente (formato propietario Microsoft con binarios cifrados).

Workaround práctico: el usuario exporta el dataset/tabla desde Power BI
Desktop como CSV o Excel, y AuditBrain ingesta ese archivo asociándolo
a metadatos del dashboard original (nombre, fecha de refresh, etc.).

Flujo recomendado para el usuario final:

1. En Power BI Desktop, abrir el .pbix.
2. Click derecho en una tabla del panel "Datos" → "Copiar tabla" o
   "Exportar datos" → CSV / Excel.
3. Subir el archivo a AuditBrain vía el endpoint /api/v1/powerbi/ingest
   junto con metadatos (dashboard_name, table_name, refresh_date).
4. AuditBrain almacena el snapshot y permite consultarlo / cruzarlo
   con otros datos (mayor contable, declaraciones, etc.).

Esto NO sustituye al .pbix; sustituye su CONTENIDO consultable.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

# Extensiones aceptadas como export de Power BI.
SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".tsv", ".txt"}

# Codificaciones a probar en orden cuando no se detecta.
ENCODINGS_TO_TRY = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]


@dataclass
class PowerBISnapshot:
    """Representa una tabla exportada desde Power BI."""
    dashboard_name: str
    table_name: str
    refresh_date: str  # ISO 8601
    rows_count: int
    columns: list[str]
    sample_rows: list[dict]  # primeras 5 filas para preview
    file_size_bytes: int
    notes: str = ""
    warnings: list[str] = field(default_factory=list)


def _sniff_csv_dialect(path: Path) -> tuple[str, str]:
    """Detecta delimitador y encoding de un CSV/TSV."""
    encoding_used = "utf-8"
    sample = b""
    with open(path, "rb") as fh:
        sample = fh.read(8192)

    # Probar encodings
    text_sample = ""
    for enc in ENCODINGS_TO_TRY:
        try:
            text_sample = sample.decode(enc)
            encoding_used = enc
            break
        except UnicodeDecodeError:
            continue

    if not text_sample:
        return ",", "utf-8"

    # Sniff delimiter
    try:
        dialect = csv.Sniffer().sniff(text_sample, delimiters=",;\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = ","
    return delim, encoding_used


def ingest_export(
    path: str | Path,
    dashboard_name: str,
    table_name: str,
    refresh_date: str | None = None,
    notes: str = "",
) -> PowerBISnapshot:
    """Ingesta un archivo exportado de Power BI y devuelve un snapshot.

    Args:
        path: ruta al .csv / .xlsx exportado desde Power BI.
        dashboard_name: nombre del dashboard origen (ej. "Ventas 2026").
        table_name: nombre de la tabla del modelo (ej. "FactVentas").
        refresh_date: ISO 8601 del último refresh del dataset.
            Si es None, se usa "now()".
        notes: notas libres del operador.

    Returns:
        PowerBISnapshot con metadata + preview.

    Raises:
        ValueError si el archivo no existe o tiene extensión no soportada.
        RuntimeError si pandas no logra parsearlo.
    """
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"Archivo no encontrado: {path}")
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Extensión {p.suffix} no soportada. Exporta desde Power BI como "
            f"CSV o Excel. Aceptados: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    warnings: list[str] = []
    file_size = p.stat().st_size

    # Sanity check de tamaño (rlimit FSIZE_MB = 100)
    if file_size > 100 * 1024 * 1024:
        warnings.append(
            f"Archivo grande ({file_size / 1024 / 1024:.1f} MB). "
            "Considera usar excel_chunks para procesamiento."
        )

    # Parsear según extensión
    suffix = p.suffix.lower()
    try:
        if suffix == ".xlsx" or suffix == ".xls":
            df = pd.read_excel(p)
        else:
            delim, enc = _sniff_csv_dialect(p)
            df = pd.read_csv(p, sep=delim, encoding=enc, low_memory=False)
    except Exception as exc:
        raise RuntimeError(f"No se pudo leer el archivo: {exc}") from exc

    if df.empty:
        warnings.append("El archivo no contiene filas de datos.")

    # Validar tipos comunes de Power BI export
    if any(col.startswith("Unnamed:") for col in df.columns):
        warnings.append(
            "El archivo tiene columnas sin nombre. Power BI a veces "
            "exporta con cabeceras en filas distintas. Verifica el header."
        )

    refresh = refresh_date or datetime.utcnow().isoformat()

    sample = df.head(5).to_dict(orient="records")
    # Limpiar NaN para que sean JSON-serializables
    for row in sample:
        for k, v in list(row.items()):
            if pd.isna(v):
                row[k] = None

    return PowerBISnapshot(
        dashboard_name=dashboard_name.strip()[:200],
        table_name=table_name.strip()[:200],
        refresh_date=refresh,
        rows_count=len(df),
        columns=[str(c) for c in df.columns],
        sample_rows=sample,
        file_size_bytes=file_size,
        notes=notes.strip()[:1000],
        warnings=warnings,
    )


def validate_export_for_module(
    snapshot: PowerBISnapshot,
    required_columns: list[str],
) -> tuple[bool, list[str]]:
    """Valida que un export de Power BI tenga las columnas esperadas
    por un módulo de AuditBrain.

    Ejemplo: para reconciliación bancaria, required_columns puede ser
    ['Fecha', 'Descripción', 'Monto']. Devuelve (True, []) si todo bien,
    (False, [columnas_faltantes]) si falta algo.
    """
    columns_lower = {c.lower().strip() for c in snapshot.columns}
    missing = [c for c in required_columns if c.lower().strip() not in columns_lower]
    return (not missing, missing)


def quick_stats(path: str | Path) -> dict:
    """Estadísticas rápidas de un export para preview en el frontend.

    Devuelve filas, columnas, tipos detectados, % de nulos por columna.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(p)
    else:
        delim, enc = _sniff_csv_dialect(p)
        df = pd.read_csv(p, sep=delim, encoding=enc, low_memory=False)

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": [str(c) for c in df.columns],
        "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
        "nulls_pct": {
            str(c): float(df[c].isna().mean() * 100) for c in df.columns
        },
        "memory_mb": float(df.memory_usage(deep=True).sum() / 1024 / 1024),
    }
