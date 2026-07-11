from backend.app.client_portal.flujo import catalogos, motor_no_efectivo


def test_cargar_no_efectivo_catalogo():
    cat = catalogos.cargar_no_efectivo()
    # 13 códigos ERI no monetarios, con categorías del set canónico
    assert set(cat.values()) <= {"DEPRECIACION", "AMORTIZACION", "DETERIORO"}
    assert cat.get("5020221") == "DEPRECIACION"
    assert cat.get("5020122") == "DETERIORO"
    assert len(cat) >= 13


def test_gastos_no_efectivo_agrupa_por_categoria():
    tot_eri = {"5020221": 103472.22, "5020122": 8068.89, "5020121": 500.0,
               "401": 9999.0}  # ruido: código de ingreso, no está en catálogo
    catalogo = {"5020221": "DEPRECIACION", "5020122": "DETERIORO",
                "5020121": "AMORTIZACION"}
    r = motor_no_efectivo.gastos_no_efectivo(tot_eri, catalogo)
    assert r["DEPRECIACION"] == 103472.22
    assert r["AMORTIZACION"] == 500.0
    assert r["DETERIORO"] == 8068.89
    assert r["total"] == round(103472.22 + 8068.89 + 500.0, 2)
    assert r["detalle"] == {"5020221": 103472.22, "5020122": 8068.89, "5020121": 500.0}


def test_gastos_no_efectivo_codigo_sin_saldo_no_entra_al_detalle():
    tot_eri = {"5020221": 0.0}
    catalogo = {"5020221": "DEPRECIACION", "5010401": "DEPRECIACION"}
    r = motor_no_efectivo.gastos_no_efectivo(tot_eri, catalogo)
    assert r["total"] == 0.0
    assert r["detalle"] == {}          # ningún código con monto ≠ 0
    assert r["DEPRECIACION"] == 0.0
