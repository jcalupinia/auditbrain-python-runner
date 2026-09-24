"""Audit trail verificable de las llamadas IA del ICT (control 3 del CLAUDE.md)."""
import dataclasses

import pytest
from openpyxl import Workbook

from backend.app.ict.audit.audit_trail import (
    GENESIS,
    CadenaIACorrupta,
    compute_hash,
    construir_trail,
    hash_input_de,
    hash_output_de,
    verificar_cadena_ia,
)


def _entrada(**k):
    base = dict(anexo_codigo="A1", modelo="claude-x", tokens=100, hash_input="ii",
                hash_output="oo", confianza="alta", requiere_revision=False,
                ts="2026-01-01T00:00:00")
    base.update(k)
    return base


def test_hash_input_output_deterministas():
    assert hash_input_de("hola") == hash_input_de("hola")
    assert len(hash_input_de("x")) == 64
    assert hash_output_de({"a": 1, "b": 2}) == hash_output_de({"b": 2, "a": 1})  # canónico


def test_vector_fijo_blinda_el_orden_de_campos():
    firma = {"seq": 1, "ts": "2026-01-01T00:00:00", "anexo_codigo": "A1",
             "modelo": "m", "tokens": 0, "hash_input": "", "hash_output": "",
             "confianza": "baja", "requiere_revision": True}
    h = compute_hash(firma, GENESIS)
    assert len(h) == 64 and h == compute_hash(firma, GENESIS)
    assert compute_hash(firma, h) != h  # encadena con el prev


def test_construir_y_verificar_cadena():
    trail = construir_trail([_entrada(anexo_codigo="A1"), _entrada(anexo_codigo="A2"),
                             _entrada(anexo_codigo="A3")])
    assert [r.seq for r in trail] == [1, 2, 3]
    assert trail[0].prev_hash == GENESIS
    assert trail[1].prev_hash == trail[0].hash and trail[2].prev_hash == trail[1].hash
    ok = verificar_cadena_ia(trail)  # no lanza
    assert [r.anexo_codigo for r in ok] == ["A1", "A2", "A3"]


def test_alterar_un_registro_rompe_la_verificacion():
    trail = construir_trail([_entrada(), _entrada(anexo_codigo="A2"), _entrada(anexo_codigo="A3")])
    trail[1] = dataclasses.replace(trail[1], hash_output="HACKEADO")  # sin recomputar el hash
    with pytest.raises(CadenaIACorrupta) as exc:
        verificar_cadena_ia(trail)
    assert exc.value.seq == 2


def test_borrar_un_registro_rompe_la_verificacion():
    trail = construir_trail([_entrada(), _entrada(), _entrada()])
    del trail[1]  # seq 1,3 → no contiguo
    with pytest.raises(CadenaIACorrupta):
        verificar_cadena_ia(trail)


# --- Integración con el interpreter -----------------------------------------

def _wb():
    wb = Workbook()
    wb.active.title = "A1"
    ws = wb["A1"]
    ws.append(["casillero", "valor"])
    ws.append(["799", 1000])
    wb.create_sheet("A2")
    return wb


def test_construir_trail_ia_desde_fallbacks():
    from backend.app.ict.audit.interpreter import _fallback_interpretation, construir_trail_ia
    interps = {"A1": _fallback_interpretation("A1"), "A2": _fallback_interpretation("A2")}
    trail = construir_trail_ia(_wb(), {"razon_social": "X"}, interps)
    assert [r.anexo_codigo for r in trail] == ["A1", "A2"]
    # los fallback quedan registrados como evidencia de que la IA no estuvo
    assert all(r.modelo == "fallback" and r.confianza == "baja" for r in trail)
    verificar_cadena_ia(trail)  # cadena íntegra


def test_interpret_all_con_trail_con_kill_switch(monkeypatch):
    """Con ICT_LLM_ENABLED=false no se llama a la API: 9 fallbacks + trail verificable."""
    monkeypatch.setenv("ICT_LLM_ENABLED", "false")
    # recargar el módulo para que lea el env var nuevo
    import importlib
    from backend.app.ict.audit import interpreter as itp
    importlib.reload(itp)
    import asyncio
    interps, trail = asyncio.run(itp.interpret_all_anexos_con_trail(_wb(), {"razon_social": "X"}))
    assert len(interps) == 9 and len(trail) == 9
    assert [r.seq for r in trail] == list(range(1, 10))
    from backend.app.ict.audit.audit_trail import verificar_cadena_ia as vc
    vc(trail)  # no lanza
    monkeypatch.delenv("ICT_LLM_ENABLED", raising=False)
    importlib.reload(itp)
