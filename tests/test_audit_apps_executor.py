"""Ejecutor de Audit Apps: allow-list + corrida determinista (P2.1)."""
import pytest

from backend.app.audit_apps.manifest import AuditAppManifest, StepSpec
from backend.app.audit_apps.executor import (
    AuditAppExecutor,
    EngineRefNotAllowedError,
    ExecutorError,
    InsufficientInputError,
)

MANIFEST_DICT = {
    "id": "AUD-DEMO-DOS",
    "name": "Demo dos pasos",
    "version": "1.0.0",
    "owner": "AuditConsulting",
    "frameworks": ["IFRS_FULL"],
    "assertions": ["existencia"],
    "risks": ["fraude"],
    "permissions": ["ejecutar"],
    "inputs": [{"id": "mayor_in", "kind": "mayor", "columns": ["cuenta"], "required": True}],
    "parameters": [{"id": "materialidad", "type": "decimal", "required": True}],
    "steps": [
        {"id": "paso1", "engine_ref": "motor.demo.uno", "inputs": ["mayor_in"],
         "parameters": ["materialidad"], "produces": "tabla"},
        {"id": "paso2", "engine_ref": "motor.demo.dos", "inputs": ["tabla"], "produces": "resultado"},
    ],
    "outputs": [{"id": "papel", "kind": "excel", "from_step": "paso2"}],
    "acceptance_tests": [{"id": "ac1", "description": "A=P+Pa", "expects": "diff==0"}],
}


def _manifest():
    return AuditAppManifest.from_dict(MANIFEST_DICT).validate()


def _resolver_fake(step: StepSpec):
    def paso1(ctx):
        assert "mayor_in" in ctx["inputs"] and ctx["parameters"]["materialidad"] == "50000.00"
        return {"filas": [1, 2, 3]}

    def paso2(ctx):
        assert ctx["intermediates"]["tabla"] == {"filas": [1, 2, 3]}
        return b"XLSXBYTES"

    return {"paso1": paso1, "paso2": paso2}[step.id]


# --- run() con resolver inyectado -------------------------------------------
def test_run_encadena_pasos_y_sella_salida():
    ex = AuditAppExecutor(engine_version="motor-0.1.0", resolver=_resolver_fake)
    res = ex.run(_manifest(), inputs={"mayor_in": b"...datos..."},
                 parameters={"materialidad": "50000.00"}, executed_by="jvinicio")
    assert res.app_id == "AUD-DEMO-DOS" and res.engine_version == "motor-0.1.0"
    assert "mayor_in" in res.input_hashes and "mayor_in" in res.disponibles
    assert [s.step_id for s in res.steps] == ["paso1", "paso2"]
    assert res.outputs["papel"] == b"XLSXBYTES" and res.output_hashes["papel"]
    assert res.parameter_snapshot == {"materialidad": "50000.00"}
    assert res.acceptance[0]["evaluado"] is False  # nunca "cumplida" a ciegas


def test_run_falta_parametro_requerido():
    ex = AuditAppExecutor(resolver=_resolver_fake)
    with pytest.raises(InsufficientInputError):
        ex.run(_manifest(), inputs={"mayor_in": b"x"}, parameters={}, executed_by="x")


def test_run_insumo_ausente_deja_paso_no_disponible():
    ex = AuditAppExecutor(resolver=_resolver_fake)
    res = ex.run(_manifest(), inputs={},  # sin el mayor
                 parameters={"materialidad": "1"}, executed_by="x")
    assert "mayor_in" in res.no_disponibles
    assert "tabla" in res.no_disponibles and "resultado" in res.no_disponibles
    assert res.steps == () and res.outputs == {}


# --- resolve_engine_ref: allow-list (seguridad) -----------------------------
def test_resolve_rechaza_fuera_de_allowlist():
    ex = AuditAppExecutor()
    with pytest.raises(EngineRefNotAllowedError):
        ex.resolve_engine_ref(StepSpec(id="s", engine_ref="os.system"))
    with pytest.raises(EngineRefNotAllowedError):
        ex.resolve_engine_ref(StepSpec(id="s", engine_ref="backend.app.forge.governance_service.x"))


def test_resolve_prefijo_permitido_pero_inexistente():
    ex = AuditAppExecutor()
    # prefijo permitido (motor.) pero el módulo no existe en este runtime → ExecutorError
    with pytest.raises(ExecutorError):
        ex.resolve_engine_ref(StepSpec(id="s", engine_ref="motor.no.existe_fn"))
