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
