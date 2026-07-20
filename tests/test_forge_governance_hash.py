"""P8 — El hash vendorizado NO diverge del CLI.

La promesa de producto es que una traza exportada por la plataforma **verifica en
la máquina del cliente** con ``forge audit verify`` (P7). Eso solo se cumple si el
``compute_hash`` copiado en el backend produce el **mismo** hash que el del CLI.

Como el CLI (``auditbrain-forge``) no es importable desde este repo, se blinda con
**vectores fijos**: los hashes de abajo se calcularon con el ``compute_hash`` real
del CLI (`forge.governance.audit`). Si la copia del backend diverge —otro orden de
campos, otra codificación, otro separador— estos vectores dejan de cuadrar y el
test cae. La divergencia no puede pasar en silencio.

Para regenerar los vectores (solo si el CLI cambia su contrato a propósito):
    from forge.governance.audit import compute_hash, GENESIS
    compute_hash(ENTRADA_1, GENESIS)          # -> VECTOR_1
    compute_hash(ENTRADA_2, VECTOR_1)         # -> VECTOR_2
"""

from backend.app.forge.engine.governance import GENESIS, _CAMPOS_FIRMADOS, compute_hash

# --- Contrato de campos ----------------------------------------------------------

CAMPOS_ESPERADOS = (
    "seq",
    "ts",
    "actor",
    "action",
    "plan_id",
    "task_id",
    "content_hash",
    "decision",
    "rationale",
)

ENTRADA_1 = {
    "seq": 1,
    "ts": "2026-07-18T00:00:00+00:00",
    "actor": "jorge@audit-ia.ec",
    "action": "approve",
    "plan_id": "p-abc",
    "task_id": "t1",
    "content_hash": "deadbeefcafe0001",
    "decision": "approved",
    "rationale": "ok",
}
VECTOR_1 = "5325a6617c1aca9831edace9db494adf4cc0677ceff08e8239e407136c0b3fec"

ENTRADA_2 = {
    "seq": 2,
    "ts": "2026-07-18T00:01:00+00:00",
    "actor": "jorge@audit-ia.ec",
    "action": "reject",
    "plan_id": "p-abc",
    "task_id": "t2",
    "content_hash": "deadbeefcafe0002",
    "decision": "rejected",
    "rationale": "faltan pruebas",
}
VECTOR_2 = "ca20c73ba3d015f317b7d938e7034b46dd2aabbb78ef64f5c63da122d3f69586"


def test_el_orden_de_campos_firmados_es_el_contrato_del_cli():
    """Si esto cambia, TODAS las cadenas escritas dejan de verificar."""
    assert _CAMPOS_FIRMADOS == CAMPOS_ESPERADOS


def test_genesis_es_64_ceros():
    assert GENESIS == "0" * 64


def test_hash_de_la_primera_decision_coincide_con_el_cli():
    assert compute_hash(ENTRADA_1, GENESIS) == VECTOR_1


def test_el_encadenado_coincide_con_el_cli():
    assert compute_hash(ENTRADA_2, VECTOR_1) == VECTOR_2


def test_un_campo_ausente_cuenta_como_cadena_vacia_igual_que_el_cli():
    """`str(entrada.get(c, ""))` — un content_hash ausente no rompe, va como ''."""
    sin_ch = {k: v for k, v in ENTRADA_1.items() if k != "content_hash"}
    con_ch_vacio = {**sin_ch, "content_hash": ""}
    assert compute_hash(sin_ch, GENESIS) == compute_hash(con_ch_vacio, GENESIS)


def test_cambiar_un_campo_firmado_cambia_el_hash():
    alterada = {**ENTRADA_1, "decision": "rejected"}
    assert compute_hash(alterada, GENESIS) != VECTOR_1
