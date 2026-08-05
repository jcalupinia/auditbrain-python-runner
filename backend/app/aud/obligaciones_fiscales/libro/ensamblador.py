"""Arma el libro DM de Obligaciones Fiscales.

Orden de las hojas: primero el resumen del motor y su detalle, después los
casilleros declarados. Las cédulas DM3..DM7 se insertan en el Plan 3b, y
leerán de estas hojas POR FÓRMULA usando los mapas de direcciones que este
módulo recolecta.
"""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from backend.app.aud.obligaciones_fiscales.libro.fuentes import (
    construir_hojas_de_casilleros,
)
from backend.app.aud.obligaciones_fiscales.libro.hoja_detalle import build_hoja_detalle
from backend.app.aud.obligaciones_fiscales.libro.hoja_mayores import build_hoja_mayores

ORDEN_HOJAS = ["Mayores homologados", "Detalle mayor", "DATOS F-104", "DATOS F-103"]


def armar_libro(
    *,
    clasificacion,
    movimientos,
    f104_monthly: dict,
    f103_monthly: dict,
    cliente: str = "",
    periodo: str = "",
    preparado_por: str | None = None,
    revisado_por: str | None = None,
) -> bytes:
    """Devuelve los bytes del libro DM con sus hojas de datos."""
    wb = Workbook()
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    direcciones = {"mayores": build_hoja_mayores(wb, clasificacion)}
    build_hoja_detalle(
        wb, movimientos, {f.codigo_cuenta: f.categoria_final for f in clasificacion}
    )
    direcciones.update(
        construir_hojas_de_casilleros(
            wb, f104_monthly=f104_monthly, f103_monthly=f103_monthly
        )
    )

    orden = [h for h in ORDEN_HOJAS if h in wb.sheetnames]
    orden += [h for h in wb.sheetnames if h not in orden]
    wb._sheets = [wb[h] for h in orden]

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()
