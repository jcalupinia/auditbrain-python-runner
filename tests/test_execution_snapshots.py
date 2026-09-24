"""Snapshots inmutables (Task 8 del plan P1-D)."""
from backend.app.execution.snapshots import (
    RulesetRef,
    build_snapshot,
    compute_ruleset_hash,
    snapshot_hash,
    verify_snapshot,
)


def _ruleset(h="rr"):
    return RulesetRef(engine_version="0.1.0", rules=(("AST-001", "1"), ("GAS-006", "2")), ruleset_hash=h)


def test_compute_ruleset_hash_estable_ante_orden():
    a = compute_ruleset_hash([("AST-001", "1"), ("GAS-006", "2")])
    b = compute_ruleset_hash([("GAS-006", "2"), ("AST-001", "1")])
    assert a == b and len(a) == 64


def test_build_snapshot_tiene_forma_y_hash():
    snap = build_snapshot(
        parameters={"materialidad": "25000.00"},
        engine_version="0.1.0", ruleset=_ruleset(),
        app_id="ICT_2025", app_version="1",
    )
    for k in ("schema_version", "engine_version", "ruleset_hash", "rules",
              "parameters", "snapshot_hash"):
        assert k in snap
    assert verify_snapshot(snap) is True


def test_verify_detecta_mutacion():
    snap = build_snapshot(
        parameters={"materialidad": "25000.00"},
        engine_version="0.1.0", ruleset=_ruleset(),
        app_id="ICT_2025", app_version="1",
    )
    snap["parameters"]["materialidad"] = "30000.00"  # mutación sin recalcular
    assert verify_snapshot(snap) is False


def test_distinto_ruleset_distinto_snapshot_hash():
    a = build_snapshot(parameters={"m": "1"}, engine_version="0.1.0",
                       ruleset=_ruleset("aaaa"), app_id="A", app_version="1")
    b = build_snapshot(parameters={"m": "1"}, engine_version="0.1.0",
                       ruleset=_ruleset("bbbb"), app_id="A", app_version="1")
    assert a["snapshot_hash"] != b["snapshot_hash"]


def test_snapshot_hash_excluye_su_propia_clave():
    payload = {"a": 1, "snapshot_hash": "loquesea"}
    assert snapshot_hash(payload) == snapshot_hash({"a": 1})
