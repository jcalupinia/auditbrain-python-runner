"""Status classifiers and materialidad thresholds for ICT audit.

Thresholds are calibrated to standard audit materiality:
- Below 0.01% of total → OK (verde)
- Between 0.01% and 0.1% → REVISAR (amarillo)
- Above 0.1% → CRITICO (rojo)

When the total is zero (cannot compute %), returns NA (no aplica).
"""
from __future__ import annotations

from decimal import Decimal

from backend.app.ict.audit.schemas import Status

# Materialidad: % del total declarado a partir del cual se considera revisable.
UMBRAL_CUADRE_REVISAR_PCT: float = 0.01   # 0.01% — saldos cuadran si <
UMBRAL_CUADRE_CRITICO_PCT: float = 0.1    # 0.1% — sobre este = crítico


def semaforo_from_diff(diferencia: Decimal, total: Decimal) -> Status:
    """Classify a difference against a total into Status (semáforo).

    Uses absolute value: sign does not affect classification.
    Returns NA when total is zero (cannot compute relative materiality).
    """
    if total == 0:
        return Status.NA
    abs_pct = (abs(diferencia) / abs(total)) * Decimal("100")
    if abs_pct < Decimal(str(UMBRAL_CUADRE_REVISAR_PCT)):
        return Status.OK
    if abs_pct < Decimal(str(UMBRAL_CUADRE_CRITICO_PCT)):
        return Status.REVISAR
    return Status.CRITICO
