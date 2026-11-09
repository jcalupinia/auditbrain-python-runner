from decimal import Decimal
import pytest

from backend.app.client_portal.costos.engine import CostState, CostInputError, calculate, compare_ledger

def base(**overrides):
    data = dict(
        mp_opening="0", mp_purchases="13471.40", mp_closing="0", mp_adjustments="0",
        supplies_consumed="475.48", direct_labor="607.99", indirect_labor="0",
        other_overhead="0", pep_opening="0", pep_closing="0", pep_adjustments="0",
        pt_opening="0", pt_closing="10916.15", pt_adjustments="0", nonabsorbed_cost="0",
    )
    data.update(overrides)
    return CostState.from_mapping(data)

def test_order_45638_simulation():
    r = calculate(base())
    assert r["manufacturing_cost"] == Decimal("14554.87")
    assert r["transferred_to_finished_goods"] == Decimal("14554.87")
    assert r["cost_of_goods_sold"] == Decimal("3638.72")
    assert all(r[k] == 0 for k in ("mp_balance_check", "pep_balance_check", "pt_balance_check"))

def test_opening_closing_and_indirect_costs():
    r = calculate(base(mp_opening="100", mp_purchases="500", mp_closing="200",
                       direct_labor="50", supplies_consumed="0", indirect_labor="25",
                       other_overhead="10", pep_opening="40", pep_closing="30",
                       pt_opening="70", pt_closing="60", nonabsorbed_cost="15"))
    assert r["materials_used"] == 400
    assert r["manufacturing_cost"] == 485
    assert r["transferred_to_finished_goods"] == 495
    assert r["cost_of_goods_sold"] == 505
    assert r["nonabsorbed_cost_separate"] == 15

def test_ledger_difference():
    r = compare_ledger(calculate(base()), {"cost_of_goods_sold": "3650"})
    assert r["cost_of_goods_sold"]["difference"] == Decimal("-11.28")

@pytest.mark.parametrize("bad", [float("nan"), "Infinity", True, "xyz"])
def test_invalid_money_rejected(bad):
    with pytest.raises(CostInputError):
        base(mp_opening=bad)

def test_missing_field_is_error():
    with pytest.raises(CostInputError):
        CostState.from_mapping({})

def test_unknown_ledger_rubric_is_error():
    with pytest.raises(CostInputError):
        compare_ledger(calculate(base()), {"nonexistent": 100})

def test_negative_derived_amount_rejected():
    with pytest.raises(CostInputError):
        calculate(base(mp_closing="20000"))
