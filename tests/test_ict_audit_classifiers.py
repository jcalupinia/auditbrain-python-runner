"""Tests for backend.app.ict.audit.classifiers."""
from decimal import Decimal

from backend.app.ict.audit.classifiers import (
    UMBRAL_CUADRE_CRITICO_PCT,
    UMBRAL_CUADRE_REVISAR_PCT,
    semaforo_from_diff,
)
from backend.app.ict.audit.schemas import Status


def test_semaforo_ok_when_difference_below_revisar_threshold():
    # Diferencia $50 sobre total $10M → 0.0005% (debajo de 0.01% por defecto)
    assert semaforo_from_diff(Decimal("50"), Decimal("10000000")) == Status.OK


def test_semaforo_revisar_when_between_thresholds():
    # Diferencia $1500 sobre total $10M → 0.015% (entre revisar y critico)
    assert semaforo_from_diff(Decimal("1500"), Decimal("10000000")) == Status.REVISAR


def test_semaforo_critico_when_above_critico_threshold():
    # Diferencia $15000 sobre total $10M → 0.15% (sobre crítico 0.1%)
    assert semaforo_from_diff(Decimal("15000"), Decimal("10000000")) == Status.CRITICO


def test_semaforo_handles_zero_total():
    assert semaforo_from_diff(Decimal("100"), Decimal("0")) == Status.NA


def test_semaforo_handles_negative_diff():
    # Signo no importa: usa valor absoluto
    assert semaforo_from_diff(Decimal("-1500"), Decimal("10000000")) == Status.REVISAR


def test_umbrales_are_documented_constants():
    assert UMBRAL_CUADRE_REVISAR_PCT == 0.01
    assert UMBRAL_CUADRE_CRITICO_PCT == 0.1
