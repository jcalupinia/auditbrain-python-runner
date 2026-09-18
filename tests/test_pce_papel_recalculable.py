"""El papel de trabajo se recalcula desde sus propias celdas y da lo archivado.

Éstas son las pruebas de extremo a extremo que faltaban: parten de un resultado
REAL de ``service.analizar`` sobre tres cortes, construyen el libro con
``exporter.construir_excel`` y vuelven a hacer la cuenta LEYENDO LAS CELDAS con
openpyxl, igual que haría el revisor que recibe el archivo.

Sin ellas, los acotamientos que protegen la medición (piso cero ante notas de
crédito, techo del importe en libros bruto ante un factor prospectivo
desbocado) vivían solo en el motor: la pantalla y la base decían una cosa y las
fórmulas del libro, otra. Un papel de trabajo que no se puede recalcular desde
sus propias celdas no sirve como evidencia de auditoría.
"""
import io
from datetime import date

import pytest
from openpyxl import Workbook, load_workbook

from backend.app.aud.pce_cxc.exporter import construir_excel
from backend.app.aud.pce_cxc.service import analizar
from tests.excel_calc import Libro

CENTAVO = 0.005


def _xlsx(filas):
    wb = Workbook()
    ws = wb.active
    ws.append(["Cliente", "Documento", "Tipo", "Emisión", "Vencimiento", "Saldo"])
    for f in filas:
        ws.append(list(f))
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _cortes(filas_2023, filas_2024, filas_2025):
    contenidos = [_xlsx(filas_2023), _xlsx(filas_2024), _xlsx(filas_2025)]
    fechas = [date(2023, 12, 31), date(2024, 12, 31), date(2025, 12, 31)]
    return [{"nombre": f"cartera_{f.year}.xlsx", "contenido": c, "fecha": f}
            for c, f in zip(contenidos, fechas)]


def _libro(resultado, parametros=None):
    binario = construir_excel(resultado, parametros or {})
    return Libro(load_workbook(io.BytesIO(binario)))


def _filas_medidas(ws):
    """Filas de 05-Matriz con pérdida calculada (las SIN MEDIR no se recalculan)."""
    filas = []
    for i in range(2, ws.max_row + 1):
        banda = ws.cell(i, 2).value
        if banda in (None, "TOTAL"):
            break
        filas.append(i)
    return filas


# ---------------------------------------------------------------------------
# Cohorte compartida: ALFA/F-1 pasa de 100.000 (t-2, banda "0 a 30 días") a
# 10.000 en el corte actual, así que esa banda observa una tasa del 10 %.
# ---------------------------------------------------------------------------

COHORTE_2023 = [("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0)]
COHORTE_2024 = [("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 20000.0)]
COHORTE_2025 = [("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 10000.0)]


def _corrida_con_nota_de_credito():
    """C3: una nota de crédito deja la banda con exposición acreedora.

    El motor le aplica el piso cero (la corrección de valor no puede ser
    negativa); si la fórmula del libro no lo aplica, el papel imprime una
    pérdida esperada negativa que neutraliza pérdidas reales.
    """
    actual = COHORTE_2025 + [
        ("GAMMA", "F-9", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 200000.0),
        ("GAMMA", "NC-1", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), -250000.0),
    ]
    return analizar(_cortes(COHORTE_2023, COHORTE_2024, actual),
                    {"umbral_dias_incumplimiento": 730})


def _corrida_con_factor_desbocado():
    """I1: un factor prospectivo de 12,0 lleva la tasa observada sobre el 100 %.

    El motor acota la tasa al 100 % y la pérdida al importe en libros bruto
    (B5.5.35); sin esos topes el libro provisiona más cartera de la que existe.
    """
    actual = COHORTE_2025 + [
        ("GAMMA", "F-9", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 200100.0),
    ]
    return analizar(
        _cortes(COHORTE_2023, COHORTE_2024, actual),
        {"umbral_dias_incumplimiento": 730, "factor_prospectivo": 12.0,
         "justificacion_prospectivo": "Contracción del sector prevista por el BCE para 2026."})


def _corrida_con_nota_de_credito_individual():
    """C4 + I8: un cliente de evaluación individual con una nota de crédito.

    DELTA supera el umbral individual con 300.000 en una banda SIN tasa y una
    nota de crédito de 100.000 en una banda CON tasa. Su saldo sin medir no
    puede superar su propia exposición, y la nota de crédito tiene que quedar
    declarada igual que en la matriz colectiva.
    """
    actual = COHORTE_2025 + [
        ("DELTA", "F-5", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), -100000.0),
        ("DELTA", "F-6", "NO-RELACIONADOS", date(2023, 1, 1), date(2023, 6, 1), 300000.0),
        ("OMEGA", "F-7", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 50000.0),
    ]
    return analizar(_cortes(COHORTE_2023, COHORTE_2024, actual),
                    {"umbral_dias_incumplimiento": 730, "umbral_individual": 100000})


# ---------------------------------------------------------------------------
# T1 — 05-Matriz recalcula exactamente la pérdida esperada archivada
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("corrida", [
    _corrida_con_nota_de_credito,
    _corrida_con_factor_desbocado,
    _corrida_con_nota_de_credito_individual,
])
def test_cada_banda_de_la_matriz_recalcula_la_perdida_archivada(corrida):
    """La celda recalculada tiene que dar, al centavo, la pérdida que archivó la
    corrida: si el libro no aplica el piso cero ni el techo del importe en
    libros bruto, el revisor que rehaga la cuenta obtiene otra cifra."""
    resultado = corrida()
    libro = _libro(resultado)
    ws = libro.wb["05-Matriz"]
    tramos = {(t.get("segmento"), t["tramo"]): t for t in resultado["matriz"]["tramos"]}
    medidas = 0
    for i in _filas_medidas(ws):
        clave = (ws.cell(i, 1).value, ws.cell(i, 2).value)
        archivada = tramos[clave]["ecl"]
        if archivada is None:
            assert ws.cell(i, 6).value == "SIN MEDIR"
            continue
        medidas += 1
        assert libro.numero("05-Matriz", f"F{i}") == pytest.approx(archivada, abs=CENTAVO), \
            f"{clave} recalcula distinto de lo archivado"
    assert medidas, "la corrida de prueba tiene que traer bandas medidas"


@pytest.mark.parametrize("corrida", [
    _corrida_con_nota_de_credito,
    _corrida_con_factor_desbocado,
    _corrida_con_nota_de_credito_individual,
])
def test_el_total_de_la_matriz_recalcula_el_total_archivado(corrida):
    resultado = corrida()
    libro = _libro(resultado)
    ws = libro.wb["05-Matriz"]
    fila_total = next(i for i in range(2, ws.max_row + 1) if ws.cell(i, 2).value == "TOTAL")
    assert libro.numero("05-Matriz", f"F{fila_total}") == pytest.approx(
        resultado["matriz"]["ecl_total"], abs=CENTAVO)


@pytest.mark.parametrize("corrida", [
    _corrida_con_nota_de_credito,
    _corrida_con_factor_desbocado,
    _corrida_con_nota_de_credito_individual,
])
def test_la_hoja_tributaria_recalcula_la_perdida_esperada_de_la_corrida(corrida):
    """09-Tributario B2 se construye sobre 05-Matriz y 06-Individual: si la
    matriz arrastra el negativo, el efecto tributario también."""
    resultado = corrida()
    libro = _libro(resultado)
    assert libro.numero("09-Tributario", "B2") == pytest.approx(
        resultado["ecl_total"], abs=CENTAVO)


def test_la_perdida_esperada_del_papel_nunca_es_negativa():
    """C3: la corrección de valor no puede ser negativa (NIIF 9 5.5.15)."""
    resultado = _corrida_con_nota_de_credito()
    libro = _libro(resultado)
    ws = libro.wb["05-Matriz"]
    for i in _filas_medidas(ws):
        if ws.cell(i, 6).value == "SIN MEDIR":
            continue
        assert libro.numero("05-Matriz", f"F{i}") >= -CENTAVO
    assert libro.numero("09-Tributario", "B2") >= -CENTAVO


def test_la_perdida_esperada_del_papel_nunca_supera_la_exposicion_de_su_banda():
    """I1: B5.5.35 mide sobre el importe en libros bruto."""
    resultado = _corrida_con_factor_desbocado()
    libro = _libro(resultado)
    ws = libro.wb["05-Matriz"]
    for i in _filas_medidas(ws):
        if ws.cell(i, 6).value == "SIN MEDIR":
            continue
        exposicion = libro.numero("05-Matriz", f"C{i}")
        assert libro.numero("05-Matriz", f"F{i}") <= max(exposicion, 0.0) + CENTAVO


def test_el_papel_declara_cuando_un_acotamiento_actuo():
    """Un acotamiento que actúa en silencio es justo lo que C3 pedía evitar: el
    papel tiene que decir cuál actuó y cuánto separó del cálculo puro."""
    for corrida, esperado in ((_corrida_con_nota_de_credito, "PISO CERO"),
                              (_corrida_con_factor_desbocado, "TASA ACOTADA")):
        resultado = corrida()
        libro = _libro(resultado)
        ws = libro.wb["05-Matriz"]
        declarados = []
        for i in _filas_medidas(ws):
            valor = ws.cell(i, 8).value
            declarados.append(str(libro.evaluar(valor, "05-Matriz")
                                  if isinstance(valor, str) and valor.startswith("=") else valor))
        assert any(esperado in d.upper() for d in declarados), \
            f"05-Matriz no declara el acotamiento {esperado}: {declarados}"


def test_la_politica_recalcula_la_misma_perdida_que_la_matriz():
    """07-Politica suma 05-Matriz con SUMIFS: hereda sus fórmulas, y con ellas
    el piso cero."""
    resultado = _corrida_con_nota_de_credito()
    libro = _libro(resultado)
    ws = libro.wb["07-Politica"]
    for i in range(2, ws.max_row + 1):
        banda = ws.cell(i, 1).value
        if banda in (None, "TOTAL"):
            break
        fila = next(f for f in resultado["politica"]["filas"] if f["banda"] == banda)
        celda = ws.cell(i, 6).value
        if fila["ecl"] is None:
            assert celda in ("SIN MEDIR", "SIN COMPARAR")
            continue
        assert libro.numero("07-Politica", f"F{i}") == pytest.approx(fila["ecl"], abs=CENTAVO)


# ---------------------------------------------------------------------------
# T2 — La cartera medida cuadra sobre la misma base
# ---------------------------------------------------------------------------

def test_la_cartera_medida_no_es_negativa_ni_supera_la_cartera_total():
    """El saldo sin medir de un caso individual sumaba solo sus bandas positivas
    mientras su exposición era el neto, así que «Cartera medida» salía negativa
    sobre una cartera positiva."""
    resultado = _corrida_con_nota_de_credito_individual()
    exposicion = resultado["exposicion"]
    assert exposicion["total"] > 0
    assert exposicion["medida"] >= 0, "la cartera medida no puede ser negativa"
    assert exposicion["medida"] <= exposicion["total"] + CENTAVO
    assert exposicion["sin_medir"] <= exposicion["total"] + CENTAVO
    assert resultado["porcentaje_sobre_cartera"] >= 0


def test_el_saldo_sin_medir_de_un_caso_no_supera_su_propia_exposicion():
    """06-Individual mostraba «Saldo sin medir» por encima de la «Exposición»
    del mismo cliente."""
    resultado = _corrida_con_nota_de_credito_individual()
    for caso in resultado["individual"]["casos"]:
        assert caso["saldo_sin_tasa"] <= max(caso["saldo"], 0.0) + CENTAVO, caso["identificacion"]


def test_la_conciliacion_recalcula_la_cartera_medida_de_la_pantalla():
    """08-Conciliacion B9 y el KPI «Cartera medida» son la misma cifra."""
    resultado = _corrida_con_nota_de_credito_individual()
    libro = _libro(resultado)
    assert libro.numero("08-Conciliacion", "B9") == pytest.approx(
        resultado["exposicion"]["medida"], abs=CENTAVO)
    assert libro.numero("08-Conciliacion", "B8") == pytest.approx(
        resultado["exposicion"]["sin_medir"], abs=CENTAVO)


# ---------------------------------------------------------------------------
# T7 — La nota de crédito de un cliente individual se declara
# ---------------------------------------------------------------------------

def test_la_nota_de_credito_de_un_cliente_individual_se_declara():
    """Un cliente con neto positivo escondía su nota de crédito: el piso cero
    actuaba en silencio sobre 10.000,00 de pérdida."""
    resultado = _corrida_con_nota_de_credito_individual()
    assert resultado["exposicion"]["negativa"] == pytest.approx(-100000.0, abs=CENTAVO)
    assert resultado["individual"]["ecl_acotada_por_piso"] == pytest.approx(10000.0, abs=CENTAVO)
    titulos = [h["titulo"] for h in resultado["hallazgos"]]
    assert "Saldos acreedores en la cartera medida" in titulos


def test_el_papel_muestra_el_saldo_acreedor_del_cliente_individual():
    """06-Individual tiene que poder sumarse: el saldo acreedor va en su propia
    columna, no dentro de una frase."""
    resultado = _corrida_con_nota_de_credito_individual()
    libro = _libro(resultado)
    ws = libro.wb["06-Individual"]
    encabezados = [str(ws.cell(1, c).value or "") for c in range(1, ws.max_column + 1)]
    columna = next((c for c, t in enumerate(encabezados, start=1) if "acreedor" in t.lower()), None)
    assert columna, f"06-Individual no declara el saldo acreedor: {encabezados}"
    acreedores = [ws.cell(i, columna).value for i in range(2, ws.max_row + 1)
                  if ws.cell(i, 1).value not in (None, "TOTAL")]
    assert any(isinstance(v, (int, float)) and v < -CENTAVO for v in acreedores)
