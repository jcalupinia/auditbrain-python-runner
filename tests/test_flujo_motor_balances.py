from backend.app.client_portal.flujo import motor_balances as mb


def _archivo(estado, periodos, filas):
    return {"estado": estado, "periodos": periodos, "filas": filas}


def test_consolidar_une_por_cuenta_una_columna_por_periodo():
    a2023 = _archivo("esf", ["2023"], [
        {"cuenta": "1.01", "nombre": "Caja", "saldos": [100.0]},
        {"cuenta": "1.02", "nombre": "Bancos", "saldos": [50.0]},
    ])
    a2024 = _archivo("esf", ["2024"], [
        {"cuenta": "1.01", "nombre": "Caja", "saldos": [110.0]},
        {"cuenta": "1.03", "nombre": "Inversiones", "saldos": [70.0]},
    ])
    cons = mb.consolidar_multiarchivo([a2023, a2024])
    assert cons["periodos"] == ["2023", "2024"]
    fichas = {f["cuenta"]: f for f in cons["filas"]}
    assert fichas["1.01"]["saldos"] == {"2023": 100.0, "2024": 110.0}
    assert fichas["1.02"]["saldos"] == {"2023": 50.0, "2024": 0.0}
    assert fichas["1.03"]["saldos"] == {"2023": 0.0, "2024": 70.0}
    assert cons["avisos"] == []


def test_consolidar_avisa_anio_duplicado_no_suma():
    a = _archivo("esf", ["2024"], [{"cuenta": "1.01", "nombre": "Caja", "saldos": [100.0]}])
    b = _archivo("esf", ["2024"], [{"cuenta": "1.01", "nombre": "Caja", "saldos": [999.0]}])
    cons = mb.consolidar_multiarchivo([a, b])
    assert any("2024" in av and "duplicad" in av.lower() for av in cons["avisos"])
    assert cons["filas"][0]["saldos"]["2024"] == 100.0


def test_consolidar_ordena_periodos_cronologicamente():
    a = _archivo("esf", ["2025"], [{"cuenta": "1.01", "nombre": "Caja", "saldos": [3.0]}])
    b = _archivo("esf", ["2023"], [{"cuenta": "1.01", "nombre": "Caja", "saldos": [1.0]}])
    cons = mb.consolidar_multiarchivo([a, b])
    assert cons["periodos"] == ["2023", "2025"]
