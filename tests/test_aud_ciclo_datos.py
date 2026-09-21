"""Reglas de datos portadas a Python (E7), contra ``espejo_datos.json``.

Ese archivo lo genera el JavaScript del sitio sobre casos fijos
(``frontend/src/aud/niif/espejo/generarDatos.mjs``). Aquí se exige el mismo
resultado caso por caso: el mismo valor, o el mismo mensaje de error. Los
archivos XLSX y CSV viajan en base64: Python lee exactamente los mismos bytes.
"""
import base64
import json
from pathlib import Path

import pytest

from backend.app.aud.niif.ciclo import datos
from backend.app.aud.niif.ciclo.reglas import ReglaIncumplida

E = json.loads(
    (Path(__file__).resolve().parents[1] / "backend/app/aud/niif/ciclo/espejo_datos.json").read_text(encoding="utf-8")
)


def _mismo(esperado, fn):
    """Compara con el resultado del sitio: {'ok': valor} o {'error': mensaje}."""
    if "error" in esperado:
        with pytest.raises(ReglaIncumplida) as e:
            fn()
        assert str(e.value) == esperado["error"]
    else:
        ok = esperado["ok"]
        valor = fn()
        if isinstance(ok, dict) and set(ok) == {"bigint"}:
            assert str(valor) == ok["bigint"]
        else:
            assert json.loads(json.dumps(valor, ensure_ascii=False)) == ok


@pytest.mark.parametrize("c", E["definiciones"], ids=lambda c: c["nombre"])
def test_definicion(c):
    _mismo(c["esperado"], lambda: datos.validate_definition(c["d"]))


@pytest.mark.parametrize("c", E["decimales"], ids=lambda c: repr(c["v"]))
def test_decimal(c):
    _mismo(c["esperado"], lambda: datos.decimal(c["v"]))


@pytest.mark.parametrize("c", E["formateados"], ids=lambda c: c["v"])
def test_formateado(c):
    _mismo(c["esperado"], lambda: datos.formatted(int(c["v"])))


@pytest.mark.parametrize("c", E["conciliaciones"], ids=lambda c: f"{c['total']}/{c['ledger']}/{c['tol']}")
def test_conciliacion(c):
    _mismo(c["esperado"], lambda: datos.reconcile(c["total"], c["ledger"], c["tol"], c["acc"]))


@pytest.mark.parametrize("c", E["filas"], ids=lambda c: c["nombre"])
def test_filas(c):
    _mismo(c["esperado"], lambda: datos.validate_rows(c["d"], c["filas"]))


@pytest.mark.parametrize("c", E["totales_control"], ids=lambda c: c["d"]["id"] + str(len(c["filas"])))
def test_total_de_control(c):
    _mismo(c["esperado"], lambda: datos.control_total(c["d"], c["filas"]))


@pytest.mark.parametrize("c", E["flujos"], ids=lambda c: json.dumps(c["flujos"])[:40])
def test_flujos(c):
    _mismo(c["esperado"], lambda: datos.validate_flows(c["flujos"]))


@pytest.mark.parametrize("c", E["requerimientos"], ids=lambda c: c["definicion"] if isinstance(c["definicion"], str) else "custom")
def test_requerimiento(c):
    from backend.app.aud.niif.ciclo import reglas
    d = reglas.CATALOGO[c["definicion"]] if isinstance(c["definicion"], str) else c["definicion"]
    programa = reglas.crear_programa(d, {"framework": "NIIF completas"})
    assert datos.create_requests(programa, c["corte"], d) == c["esperado"]


@pytest.mark.parametrize("c", E["formatos"], ids=lambda c: c["v"] or "vacío")
def test_formatos(c):
    assert datos.parse_formats(c["v"]) == c["esperado"]


def test_requerimientos_como_items():
    assert datos.requests_as_items(E["cobertura"]["requerimientos"]) == E["cobertura"]["items"]


@pytest.mark.parametrize("c", E["cobertura"]["escenarios"], ids=lambda c: c["nombre"])
def test_cobertura(c):
    reqs = E["cobertura"]["requerimientos"]
    assert datos.tool_gaps(reqs, c["archivos"], c["rechazados"]) == c["huecos"]
    assert datos.tool_coverage(reqs, c["archivos"], c["rechazados"]) == c["cobertura"]


@pytest.mark.parametrize("c", E["csv_directo"], ids=lambda c: repr(c["texto"]))
def test_csv(c):
    _mismo(c["esperado"], lambda: datos.parse_csv(c["texto"], c["sep"]))


@pytest.mark.parametrize("c", E["archivos"], ids=lambda c: c["nombre"])
def test_lectura_de_hojas(c):
    _mismo(c["esperado"], lambda: datos.read_spreadsheet(base64.b64decode(c["b64"]), c["nombre"]))


@pytest.mark.parametrize("c", E["mapeos"], ids=lambda c: c["nombre"])
def test_mapeo(c):
    _mismo(c["esperado"], lambda: datos.mapped_rows(c["sheet"], c["header"], c["mapping"], c["d"], c["archivo"]))


# --- E8 ----------------------------------------------------------------------

@pytest.mark.parametrize("c", E["tramos"], ids=lambda c: c["nombre"])
def test_tramos_de_mora(c):
    _mismo(c["esperado"] if "error" in c["esperado"] else {"ok": None}, lambda: datos.check_buckets(c["p"]))


@pytest.mark.parametrize("c", E["excepciones"], ids=lambda c: c["nombre"])
def test_excepciones_sobre_el_motor_python(c):
    # El motor Python calcula y el puerto saca las excepciones: tienen que ser
    # las mismas que calculate() del sitio, en el mismo orden.
    from backend.app.aud.niif import estudio
    run = estudio.ejecutar_definicion(c["d"], c["filas"], c["p"])
    assert datos.excepciones(c["d"], run) == c["esperado"]


@pytest.mark.parametrize("c", E["preliminares"], ids=lambda c: str(len(c["t"]["run"]["totals"])))
def test_conclusion_preliminar(c):
    assert datos.preliminary(c["t"]) == c["esperado"]


def test_contraste_nombra_lo_que_difiere():
    py = {"engine": "3.0.0", "rows": [{"id": "A", "x": "1.00"}], "totals": {"x": "1.00"}, "exceptions": []}
    assert datos.motivo_contraste(py, {**py}) == ""
    assert datos.motivo_contraste(py, None) == "no llegó el resultado del navegador"
    assert datos.motivo_contraste(py, {**py, "engine": "2.0.0"}) == "versión del motor: Python usa 3.0.0"
    assert datos.motivo_contraste(py, {**py, "rows": []}) == "número de filas: 1 en Python y 0 en el navegador"
    assert datos.motivo_contraste(py, {**py, "rows": [{"id": "A", "x": "1.01"}]}) == "fila 1, campos: x"
    assert datos.motivo_contraste(py, {**py, "rows": [{"id": "A", "x": "1.00", "y": "0"}]}) == "fila 1, campos: y"
    assert datos.motivo_contraste(py, {**py, "totals": {}}) == "totales: x"
    assert datos.motivo_contraste(py, {**py, "exceptions": [{"code": "RESULT"}]}) == "excepciones"
