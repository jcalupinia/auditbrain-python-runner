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


def test_propagar_homologacion_marca_huerfanas():
    cons = {"periodos": ["2024"], "filas": [
        {"cuenta": "1.01.01.02.001", "nombre": "Produbanco", "saldos": {"2024": 100.0}},
        {"cuenta": "1.01.01.01.002", "nombre": "Caja Chica", "saldos": {"2024": 5.0}},
    ]}
    mapeo = {"1.01.01.02.001": ("1010103", "311")}
    out = mb.propagar_homologacion(cons["filas"], mapeo)
    homolog = {f["cuenta"]: f for f in out}
    assert homolog["1.01.01.02.001"]["super_cias"] == "1010103"
    assert homolog["1.01.01.02.001"]["sri"] == "311"
    assert homolog["1.01.01.01.002"]["super_cias"] == ""
    assert mb.huerfanas(out) == ["1.01.01.01.002"]


def test_cuadre_por_periodo_esf_no_fuerza():
    fichas = [
        {"cuenta": "a", "super_cias": "1010101", "sri": "311", "saldos": {"2024": 100.0}},
        {"cuenta": "b", "super_cias": "2010301", "sri": "413", "saldos": {"2024": -60.0}},
        {"cuenta": "c", "super_cias": "3010101", "sri": "601", "saldos": {"2024": -40.0}},
    ]
    cua = mb.cuadre_por_periodo(fichas, ["2024"])
    assert cua["2024"]["cuadra"] is True
    assert abs(cua["2024"]["diferencia"]) < 0.01


def test_cuadre_por_periodo_reporta_descuadre():
    fichas = [
        {"cuenta": "a", "super_cias": "1010101", "sri": "311", "saldos": {"2024": 100.0}},
        {"cuenta": "b", "super_cias": "2010301", "sri": "413", "saldos": {"2024": -60.0}},
    ]
    cua = mb.cuadre_por_periodo(fichas, ["2024"])
    assert cua["2024"]["cuadra"] is False
    assert abs(cua["2024"]["diferencia"] - 40.0) < 0.01


def test_consolidar_suma_misma_cuenta_en_varias_filas_del_mismo_archivo():
    # misma cuenta en 2 filas del MISMO archivo, cada una con el valor de un período distinto
    arch = _archivo("esf", ["2023", "2024"], [
        {"cuenta": "1.01", "nombre": "CxL", "saldos": [60.0, 0.0]},
        {"cuenta": "1.01", "nombre": "CxL", "saldos": [0.0, 60.0]},
    ])
    cons = mb.consolidar_multiarchivo([arch])
    assert len(cons["filas"]) == 1
    assert cons["filas"][0]["saldos"] == {"2023": 60.0, "2024": 60.0}
    assert cons["avisos"] == []   # NO es año duplicado (mismo archivo)


def test_consolidar_marca_es_hoja_y_huerfanas_solo_hojas():
    arch = _archivo("esf", ["2024"], [
        {"cuenta": "1.01.", "nombre": "CORRIENTES", "saldos": [100.0]},   # grupo (termina en punto)
        {"cuenta": "1.01.01", "nombre": "Caja", "saldos": [60.0]},         # hoja
    ])
    cons = mb.consolidar_multiarchivo([arch])
    fichas = {f["cuenta"]: f for f in cons["filas"]}
    assert fichas["1.01."]["es_hoja"] is False
    assert fichas["1.01.01"]["es_hoja"] is True
    hom = mb.propagar_homologacion(cons["filas"], {})
    assert mb.huerfanas(hom) == ["1.01.01"]   # solo la hoja; el grupo no cuenta
