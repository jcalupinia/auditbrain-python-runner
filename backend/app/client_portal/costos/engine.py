"""Motor deterministico base de costos AuditSmart, sin operaciones de E/S.
Las categorias MOI y GIF deben ser excluyentes. Los no absorbidos se reportan aparte.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

class CostInputError(ValueError):
    pass

def money(value: object) -> Decimal:
    if isinstance(value, bool):
        raise CostInputError("boolean is not a monetary amount")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CostInputError(f"invalid monetary amount: {value!r}") from exc
    if not result.is_finite():
        raise CostInputError("monetary amount must be finite")
    return result

@dataclass(frozen=True)
class CostState:
    mp_opening: Decimal
    mp_purchases: Decimal
    mp_closing: Decimal
    mp_adjustments: Decimal
    supplies_consumed: Decimal
    direct_labor: Decimal
    indirect_labor: Decimal
    other_overhead: Decimal
    pep_opening: Decimal
    pep_closing: Decimal
    pep_adjustments: Decimal
    pt_opening: Decimal
    pt_closing: Decimal
    pt_adjustments: Decimal
    nonabsorbed_cost: Decimal

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> CostState:
        names = set(cls.__dataclass_fields__)
        missing = sorted(names - set(data))
        if missing:
            raise CostInputError("missing fields: " + ", ".join(missing))
        unexpected = sorted(set(data) - names)
        if unexpected:
            raise CostInputError("unexpected fields: " + ", ".join(unexpected))
        return cls(**{k: money(data[k]) for k in names})

def calculate(state: CostState) -> dict[str, Decimal]:
    mp_used = state.mp_opening + state.mp_purchases + state.mp_adjustments - state.mp_closing
    incurred = mp_used + state.supplies_consumed + state.direct_labor + state.indirect_labor + state.other_overhead
    transferred = state.pep_opening + incurred + state.pep_adjustments - state.pep_closing
    cogs = state.pt_opening + transferred + state.pt_adjustments - state.pt_closing
    if min(mp_used, incurred, transferred, cogs) < 0:
        raise CostInputError("negative derived cost; check balances and signed adjustments")
    return {
        "materials_used": mp_used,
        "manufacturing_cost": incurred,
        "transferred_to_finished_goods": transferred,
        "cost_of_goods_sold": cogs,
        "nonabsorbed_cost_separate": state.nonabsorbed_cost,
        "mp_balance_check": state.mp_opening + state.mp_purchases + state.mp_adjustments - mp_used - state.mp_closing,
        "pep_balance_check": state.pep_opening + incurred + state.pep_adjustments - transferred - state.pep_closing,
        "pt_balance_check": state.pt_opening + transferred + state.pt_adjustments - cogs - state.pt_closing,
    }

def compare_ledger(computed: Mapping[str, Decimal], ledger: Mapping[str, object]) -> dict[str, dict[str, Decimal]]:
    comparison = {}
    for rubric, amount in ledger.items():
        if rubric not in computed:
            raise CostInputError(f"unknown ledger rubric: {rubric}")
        book = money(amount)
        comparison[rubric] = {"audit_ia": computed[rubric], "ledger": book, "difference": computed[rubric] - book}
    if not comparison:
        raise CostInputError("at least one ledger rubric is required")
    return comparison
