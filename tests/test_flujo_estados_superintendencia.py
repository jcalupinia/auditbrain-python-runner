from backend.app.client_portal.flujo import motor_balances as mb


def test_estados_superintendencia_agrupa_y_rollup_por_super_cias():
    esf = {"periodos": ["2024"], "filas": [
        {"cuenta": "x", "super_cias": "1010101", "es_hoja": True, "saldos": {"2024": 100.0}},  # CAJA
        {"cuenta": "y", "super_cias": "1010103", "es_hoja": True, "saldos": {"2024": 50.0}},   # INST FIN PRIV
    ]}
    eri = {"periodos": [], "filas": []}
    out = mb.estados_superintendencia(esf, eri)
    esf_out = out["esf"]
    assert esf_out["periodos"] == ["2024"]
    lineas = {l["codigo"]: l for l in esf_out["lineas"]}
    assert lineas["1010101"]["valores"][0] == 100.0            # hoja
    assert lineas["10101"]["valores"][0] == 150.0              # EFECTIVO Y EQUIV = suma hijos
    assert lineas["1"]["valores"][0] == 150.0                  # ACTIVO (rollup total)
    assert lineas["10101"]["etiqueta"]                          # trae etiqueta oficial


def test_estados_superintendencia_multi_periodo_ignora_huerfanas():
    esf = {"periodos": ["2023", "2024"], "filas": [
        {"cuenta": "x", "super_cias": "1010101", "es_hoja": True, "saldos": {"2023": 10.0, "2024": 20.0}},
        {"cuenta": "z", "super_cias": "", "es_hoja": True, "saldos": {"2023": 999.0, "2024": 999.0}},  # huérfana: no entra
    ]}
    out = mb.estados_superintendencia(esf, {"periodos": [], "filas": []})
    lineas = {l["codigo"]: l for l in out["esf"]["lineas"]}
    assert lineas["1010101"]["valores"] == [10.0, 20.0]        # N columnas
    assert lineas["1"]["valores"] == [10.0, 20.0]              # sin la huérfana
