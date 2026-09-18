"""Excel del papel de trabajo: hojas, fórmulas y cuadres."""
import io

from openpyxl import load_workbook

from backend.app.aud.pce_cxc.exporter import construir_excel

RESULTADO = {
    "exposicion": {"colectiva": 100000.0, "individual": 0.0, "sin_estratificar": 0.0,
                   "total": 100000.0, "segun_archivo": 100000.0,
                   "factores_anclaje": {"NO-RELACIONADOS": 1.0, "RELACIONADOS": 1.0}},
    "tasas": {"NO-RELACIONADOS": {"Por vencer": 0.01, "0 a 30 días": 0.05}},
    "detalle_cohorte": {"NO-RELACIONADOS": {"Por vencer": {"inicial": 50000.0, "remanente": 500.0, "documentos": 12}}},
    "trazabilidad": 0.99,
    "matriz": {"tramos": [{"tramo": "Por vencer", "exposicion": 80000.0, "tasa_perdida": 0.01,
                           "tasa_ajustada": 0.01, "lgd": 1.0, "horizonte": None,
                           "factor_descuento": 1.0, "ecl": 800.0},
                          {"tramo": "0 a 30 días", "exposicion": 20000.0, "tasa_perdida": 0.05,
                           "tasa_ajustada": 0.05, "lgd": 1.0, "horizonte": None,
                           "factor_descuento": 1.0, "ecl": 1000.0}],
               "exposicion_total": 100000.0, "ecl_total": 1800.0, "exposicion_sin_medir": 0.0,
               "descuento_aplicado": False, "ajuste_prospectivo": 0.0, "justificacion_ajuste": "",
               "fuente_tasas": "Permanencia a 24 meses"},
    "individual": {"casos": [], "saldo_total": 0.0, "ecl_total": 0.0},
    "conciliacion": {"cartera_total": 100000.0, "saldo_contable": 100000.0, "diferencia": 0.0, "cuadra": True},
    "tributario": {"limite_ejercicio_1pct": 1000.0, "tope_acumulado_10pct": 10000.0,
                   "excede_limite_ejercicio": True, "nota": "Límite de deducción"},
    "politica": {"filas": [{"banda": "Por vencer", "banda_origen": "Por vencer", "exposicion": 80000.0,
                            "tasa_politica": 0.0, "provision_politica": 0.0, "ecl": 800.0, "diferencia": 800.0}],
                 "provision_politica_total": 0.0, "diferencia_bruta": 800.0},
    "ecl_total": 1800.0, "hallazgos": [], "pendientes": [],
    "bitacora": {"bandas": ["Por vencer", "0 a 30 días"], "umbral_incumplimiento": 730,
                 "umbral_individual": 0, "cortes": [], "metodo": "Permanencia a 24 meses",
                 "descuento": "No aplicado (NIIF 9 B5.5.44)"},
}


def _abrir(binario, con_formulas=True):
    return load_workbook(io.BytesIO(binario), data_only=not con_formulas)


def test_el_libro_trae_todas_las_hojas():
    wb = _abrir(construir_excel(RESULTADO, {"entidad": "PRUEBA S.A."}))
    assert wb.sheetnames == ["00-Caratula", "01-Parametros", "02-Fuentes", "03-Cohorte", "04-Tasas",
                             "05-Matriz", "06-Individual", "07-Politica", "08-Conciliacion",
                             "09-Tributario", "10-Hallazgos", "11-Pendientes", "12-Bitacora"]


def test_la_matriz_calcula_con_formulas_y_no_con_valores_pegados():
    ws = _abrir(construir_excel(RESULTADO, {}))["05-Matriz"]
    formulas = [c.value for fila in ws.iter_rows() for c in fila
                if isinstance(c.value, str) and c.value.startswith("=")]
    assert any("*" in f for f in formulas), "la pérdida de cada banda debe ser una fórmula"
    assert any(f.startswith("=SUM(") for f in formulas), "el total debe ser una suma"


def test_los_parametros_estan_en_celdas_con_nombre_y_las_formulas_los_usan():
    wb = _abrir(construir_excel(RESULTADO, {}))
    assert "AjusteProspectivo" in wb.defined_names
    ws = wb["05-Matriz"]
    assert any(isinstance(c.value, str) and "AjusteProspectivo" in c.value
               for fila in ws.iter_rows() for c in fila)


def test_el_libro_abre_sin_reparacion_y_recalcula_al_abrirse():
    wb = _abrir(construir_excel(RESULTADO, {}))
    assert wb.calculation.fullCalcOnLoad is True


def test_banda_sin_medir_no_escribe_cero_ni_formula_de_perdida():
    """Un tramo con ``tasa_perdida`` y ``ecl`` en ``None`` (banda sin tasa
    observada ni sustituta, camino que existe en el motor pero que ninguna
    prueba ejercitaba) debe rotularse "SIN MEDIR" en 05-Matriz, nunca como
    0,00 ni como fórmula: un cero confundiría "no medido" con "pérdida cero
    real"."""
    resultado = {
        "matriz": {"tramos": [
            {"segmento": "NO-RELACIONADOS", "tramo": "Más de 360 días",
             "exposicion": 5000.0, "tasa_perdida": None, "ecl": None},
        ]},
    }
    ws = _abrir(construir_excel(resultado, {}))["05-Matriz"]
    fila = 2
    assert ws.cell(fila, 3).value == 5000.0  # la exposición sí se traslada
    assert ws.cell(fila, 4).value == "SIN MEDIR"
    assert ws.cell(fila, 6).value == "SIN MEDIR"
    assert ws.cell(fila, 6).value != 0
    valor_col_f = ws.cell(fila, 6).value
    assert not (isinstance(valor_col_f, str) and valor_col_f.startswith("=")), \
        "una banda sin medir no debe llevar fórmula de pérdida"


def test_cada_segmento_resuelve_su_propio_factor_prospectivo():
    """El motor mide cada segmento por separado (``service.analizar`` llama a
    ``medir_ecl`` una vez por segmento) y cada uno puede traer un factor
    prospectivo distinto (p. ej. 1,05 para terceros y 1,10 para
    relacionadas). 05-Matriz debe resolver, fila por fila, el nombre
    definido que corresponde al segmento de ESA fila -no un único factor
    global que desconoce el resto de segmentos-."""
    resultado = {
        "matriz": {"tramos": [
            {"segmento": "NO-RELACIONADOS", "tramo": "Por vencer",
             "exposicion": 80000.0, "tasa_perdida": 0.01, "ecl": 800.0},
            {"segmento": "RELACIONADOS", "tramo": "Por vencer",
             "exposicion": 20000.0, "tasa_perdida": 0.02, "ecl": 400.0},
        ]},
    }
    parametros = {"factor_prospectivo": {"NO-RELACIONADOS": 1.05, "RELACIONADOS": 1.10}}
    wb = _abrir(construir_excel(resultado, parametros))

    # Los dos nombres existen en el libro, cada uno con el valor esperado
    # (factor - 1: la misma convención que ya tenía AjusteProspectivo).
    esperados = {"AjusteProspectivoNoRelacionados": 0.05, "AjusteProspectivoRelacionados": 0.10}
    for nombre, esperado in esperados.items():
        assert nombre in wb.defined_names, f"falta el nombre definido {nombre}"
        dn = wb.defined_names[nombre]
        hoja, celda = next(dn.destinations)
        valor = wb[hoja][celda].value
        assert abs(valor - esperado) < 1e-9, f"{nombre} debería ser {esperado}, es {valor}"

    ws = wb["05-Matriz"]
    fila_no_relacionados, fila_relacionados = 2, 3
    assert ws.cell(fila_no_relacionados, 1).value == "NO-RELACIONADOS"
    assert ws.cell(fila_relacionados, 1).value == "RELACIONADOS"

    # Cada fila resuelve el nombre según SU PROPIO segmento (columna A de esa
    # misma fila), no el de otra fila ni un nombre único compartido.
    formula_no_relacionados = ws.cell(fila_no_relacionados, 5).value
    formula_relacionados = ws.cell(fila_relacionados, 5).value
    esperado_no_relacionados = (f'=IF(A{fila_no_relacionados}="RELACIONADOS",'
                                f'AjusteProspectivoRelacionados,AjusteProspectivoNoRelacionados)')
    esperado_relacionados = (f'=IF(A{fila_relacionados}="RELACIONADOS",'
                             f'AjusteProspectivoRelacionados,AjusteProspectivoNoRelacionados)')
    assert formula_no_relacionados == esperado_no_relacionados, formula_no_relacionados
    assert formula_relacionados == esperado_relacionados, formula_relacionados
