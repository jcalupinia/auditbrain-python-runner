"""Enriquecimiento del ciclo: scoring de riesgo y matriz de evidencia (aditivos)."""
import types

from backend.app.aud.niif.ciclo import insights


def _def(*num_keys):
    return {"id": "custom", "fields": [{"key": k, "label": k, "type": "number"} for k in num_keys]}


def test_scoring_marca_la_fila_atipica():
    d = _def("saldo")
    rows = [{"saldo": v} for v in ("100", "101", "99", "102", "98", "100")] + [{"saldo": "100000"}]
    r = insights.scoring_riesgo(d, rows)
    assert r["campos"] == ["saldo"]
    assert r["resumen"]["total"] == 7 and r["resumen"]["alto"] >= 1
    assert r["anomalias"] and r["anomalias"][0]["indice"] == 6  # el outlier
    assert r["anomalias"][0]["factores"]                        # explicable


def test_scoring_sin_campos_numericos_o_sin_rows_devuelve_vacio():
    assert insights.scoring_riesgo({"id": "custom", "fields": [{"key": "x", "type": "text"}]}, [{"x": "a"}]) == {}
    assert insights.scoring_riesgo(_def("saldo"), []) == {}
    assert insights.scoring_riesgo({"id": "proc", "processor": "cxc_cartera"}, [{"a": 1}]) == {}


def test_scoring_valores_no_numericos_no_rompen():
    r = insights.scoring_riesgo(_def("saldo"), [{"saldo": "n/a"}, {"saldo": "100"}, {"saldo": "abc"}])
    assert "resumen" in r and r["resumen"]["total"] == 3   # no lanza; strings → 0.0


def _archivo(req, sha, nombre="f.xlsx", estado="recibido"):
    return types.SimpleNamespace(requerimiento=req, sha256=sha, nombre=nombre, estado=estado)


def test_matriz_evidencia_cobertura_y_corroboracion():
    requests = [{"id": "RQ-001", "document": "Cartera"}, {"id": "RQ-002", "document": "Mayor"},
                {"id": "RQ-003", "document": "Contrato"}]
    archivos = [
        _archivo("RQ-001", "a" * 64), _archivo("RQ-001", "b" * 64),   # corroborado (2 fuentes)
        _archivo("RQ-002", "c" * 64),                                  # 1 fuente
        _archivo("RQ-002", "d" * 64, estado="rechazado"),             # rechazado: no cuenta
        # RQ-003 sin evidencia
    ]
    r = insights.matriz_evidencia(requests, archivos)
    assert r["resumen"] == {"requerimientos": 3, "con_evidencia": 2, "sin_evidencia": 1, "corroborados": 1}
    por_id = {e["requerimiento"]: e for e in r["entradas"]}
    assert por_id["RQ-001"]["fuentes"] == 2 and por_id["RQ-001"]["corroborado"] is True
    assert por_id["RQ-002"]["fuentes"] == 1 and por_id["RQ-002"]["corroborado"] is False
    assert por_id["RQ-003"]["fuentes"] == 0


def test_matriz_sin_requerimientos_devuelve_vacio():
    assert insights.matriz_evidencia([], []) == {}
