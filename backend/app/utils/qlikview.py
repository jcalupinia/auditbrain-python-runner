"""Lectura de archivos QlikView/QlikSense Data (.qvd) usando PyQvd.

Formatos QVD:
- .qvd  : Qlik View Data — formato binario propietario de Qlik para
  almacenar tablas. Contiene un header XML + symbol table + index table.
- .qvw  : QlikView app completa. NO soportado nativamente (formato
  cerrado más complejo). Workaround: dentro de QlikView/Sense exportar
  la tabla deseada como .qvd y usar este módulo.
- .qvf  : QlikSense Cloud app. Mismo workaround que .qvw.

Uso:

    from backend.app.utils import qlikview

    if qlikview.is_available():
        df = qlikview.read_qvd("transacciones.qvd")
        # DataFrame con las filas del .qvd

        info = qlikview.quick_overview("transacciones.qvd")
        # {'rows': 50000, 'columns': ['Fecha', 'Monto', ...], ...}
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)


class QVDUnavailable(RuntimeError):
    """PyQvd no está instalado en este entorno."""


class QVDError(RuntimeError):
    """Error al leer el archivo .qvd."""


def is_available() -> bool:
    """True si PyQvd está disponible."""
    try:
        import pyqvd  # noqa: F401
        return True
    except ImportError:
        return False


def _require_lib():
    try:
        from pyqvd import QvdTable
        return QvdTable
    except ImportError as exc:
        raise QVDUnavailable(
            "PyQvd no está instalado. Añadir 'PyQvd' a "
            "requirements-prod.txt."
        ) from exc


def _open(qvd_path: str | Path):
    """Abre un .qvd y devuelve el objeto QvdTable."""
    p = Path(qvd_path)
    if not p.is_file():
        raise QVDError(f"Archivo no encontrado: {qvd_path}")
    if p.suffix.lower() != ".qvd":
        raise QVDError(
            f"Extensión {p.suffix} no soportada. Solo .qvd es leíble "
            "nativamente. Para .qvw/.qvf exportar primero a .qvd dentro "
            "de QlikView/Sense."
        )

    QvdTable = _require_lib()
    try:
        return QvdTable.from_qvd(str(p))
    except Exception as exc:
        raise QVDError(f"No se pudo abrir el .qvd: {exc}") from exc


def read_qvd(qvd_path: str | Path) -> pd.DataFrame:
    """Lee un .qvd completo como DataFrame.

    Para archivos muy grandes considera usar `iter_qvd_chunks` que
    todavía no existe — por ahora el .qvd se carga completo.
    """
    tbl = _open(qvd_path)
    try:
        # PyQvd expone to_pandas() en versiones recientes.
        if hasattr(tbl, "to_pandas"):
            return tbl.to_pandas()
        # Fallback: construir DataFrame desde la representación interna.
        return pd.DataFrame(tbl.to_dict())
    except Exception as exc:
        raise QVDError(f"Error convirtiendo QVD a DataFrame: {exc}") from exc


def quick_overview(qvd_path: str | Path) -> dict:
    """Resumen del .qvd: filas, columnas, tipos, tamaño en disco.

    Returns:
        {
          "rows": int,
          "columns": [str],
          "column_count": int,
          "dtypes": {col: dtype_str},
          "file_size_bytes": int,
          "file_size_mb": float,
        }
    """
    p = Path(qvd_path)
    size = p.stat().st_size

    df = read_qvd(qvd_path)
    return {
        "rows": len(df),
        "columns": [str(c) for c in df.columns],
        "column_count": len(df.columns),
        "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
        "file_size_bytes": size,
        "file_size_mb": round(size / (1024 * 1024), 2),
    }


def validate_for_module(
    qvd_path: str | Path,
    required_columns: list[str],
) -> tuple[bool, list[str]]:
    """Valida que el .qvd tenga las columnas esperadas por un módulo.

    Ejemplo para reconciliación bancaria:
        ok, missing = validate_for_module(
            "movimientos.qvd",
            ["Fecha", "Descripción", "Débito", "Crédito"],
        )
    """
    overview = quick_overview(qvd_path)
    columns_lower = {c.lower().strip() for c in overview["columns"]}
    missing = [
        c for c in required_columns if c.lower().strip() not in columns_lower
    ]
    return (not missing, missing)


def export_to_csv(qvd_path: str | Path, csv_path: str | Path) -> int:
    """Convierte un .qvd a CSV. Útil para pipelines híbridos.

    Returns:
        Número de filas exportadas.
    """
    df = read_qvd(qvd_path)
    df.to_csv(str(csv_path), index=False, encoding="utf-8")
    return len(df)
