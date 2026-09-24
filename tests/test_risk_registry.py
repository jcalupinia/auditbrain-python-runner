"""Gobierno del modelo de riesgo (P1, ML-009/010/011)."""
import pytest

from backend.app.risk.registry import (
    ConflictoDeVersion,
    ModeloRiesgo,
    RegistroModelos,
    hash_config,
    modelo_estadistico,
    modelo_isolation_forest,
)


def test_hash_config_estable_ante_orden():
    a = hash_config("if", ("m", "f"), {"c": 0.05}, 0.0)
    b = hash_config("if", ("f", "m"), {"c": 0.05}, 0.0)
    assert a == b and len(a) == 64
    assert a != hash_config("if", ("m", "f"), {"c": 0.10}, 0.0)


def test_config_hash_en_ficha():
    m = modelo_estadistico(("monto",))
    assert m.config_hash == hash_config("mad_zscore", ("monto",), m.parametros, m.umbral)
    assert m.a_dict()["algoritmo"] == "mad_zscore"


def test_registro_idempotente_y_conflicto():
    reg = RegistroModelos()
    m = modelo_isolation_forest(("m", "f"), version="1.0.0")
    reg.registrar(m)
    reg.registrar(modelo_isolation_forest(("m", "f"), version="1.0.0"))  # misma config → no-op
    assert len(reg.listar()) == 1
    # misma versión, distinta config → conflicto (una versión publicada no muta)
    with pytest.raises(ConflictoDeVersion):
        reg.registrar(modelo_isolation_forest(("m", "f"), contaminacion=0.2, version="1.0.0"))


def test_versiones_y_obtener_ultima():
    reg = RegistroModelos()
    reg.registrar(ModeloRiesgo("x", "1.0.0", "mad_zscore", ("a",)))
    reg.registrar(ModeloRiesgo("x", "1.2.0", "mad_zscore", ("a",), umbral=4.0))
    reg.registrar(ModeloRiesgo("x", "1.10.0", "mad_zscore", ("a",), umbral=5.0))
    assert [m.version for m in reg.versiones("x")] == ["1.0.0", "1.2.0", "1.10.0"]
    assert reg.obtener("x").version == "1.10.0"  # más reciente
    assert reg.obtener("x", "1.2.0").umbral == 4.0
    assert reg.obtener("noexiste") is None
