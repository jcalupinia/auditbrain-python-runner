"""El papel de trabajo se tiene que poder recalcular desde sus propias celdas.

Un papel auditable no vale por el número que archiva, sino porque cualquiera
que lo abra pueda rehacer el cálculo con lo que ve. Aquí se comprueba eso
literalmente: se corre el servicio con tres cortes reales, se construye el
libro con ``exporter.construir_excel`` y se releen las celdas con openpyxl
para verificar, banda por banda, que

    exposición mostrada × tasa mostrada × (1 + ajuste mostrado) = pérdida mostrada

al centavo, y que el total del libro es exactamente el ``ecl_total`` que el
servicio guardó.

El defecto que esta prueba fija (M-CENTAVO): la exposición anclada a los
estados financieros no cae en centavos exactos (el factor de anclaje le deja
decimales). El servicio medía sobre ese número SIN redondear y mostraba la
exposición YA redondeada, mientras el Excel recalculaba
``ROUND(exposición_mostrada × tasa, 2)`` sobre la mostrada. Dos bases, dos
resultados: en el tramo «181 a 360 días» de NO-RELACIONADOS el servicio
guardaba 10.925,64 y Excel mostraba 10.925,65.
"""
import io
from datetime import date
from decimal import Decimal

from openpyxl import Workbook, load_workbook

from backend.app.aud.pce_cxc.exporter import construir_excel
from backend.app.aud.pce_cxc.service import analizar
from tests.excel_calc import Libro

# ---------------------------------------------------------------------------
# Los tres cortes de prueba (mismos datos que `app/pruebas/cartera_*.xlsx`)
# ---------------------------------------------------------------------------

# (cliente, documento, segmento, días vencidos al corte, saldo)
COHORTE_2023 = [
    ("ALFA S.A.", "F-1001", "NO-RELACIONADOS", -30, 100000.0),
    ("ALFA S.A.", "F-1002", "NO-RELACIONADOS", 15, 50000.0),
    ("BETA CIA", "F-1003", "NO-RELACIONADOS", 45, 40000.0),
    ("BETA CIA", "F-1004", "NO-RELACIONADOS", 75, 30000.0),
    ("GAMMA S.A.", "F-1005", "NO-RELACIONADOS", 120, 25000.0),
    ("GAMMA S.A.", "F-1006", "NO-RELACIONADOS", 200, 20000.0),
    ("DELTA CIA", "F-1007", "NO-RELACIONADOS", 500, 15000.0),
    ("DELTA CIA", "F-1008", "NO-RELACIONADOS", 900, 10000.0),
    ("RELACIONADA UNO", "F-2001", "RELACIONADOS", -10, 60000.0),
    ("RELACIONADA UNO", "F-2002", "RELACIONADOS", 100, 20000.0),
]
REMANENTES = {"F-1001": 2000.0, "F-1002": 1000.0, "F-1003": 4000.0, "F-1004": 6000.0,
              "F-1005": 9000.0, "F-1006": 12000.0, "F-1007": 12000.0, "F-1008": 9500.0,
              "F-2001": 300.0}
CARTERA_2025 = [
    ("ALFA S.A.", "F-3001", "NO-RELACIONADOS", -45, 400000.0),
    ("ALFA S.A.", "F-3002", "NO-RELACIONADOS", 20, 60000.0),
    ("BETA CIA", "F-3003", "NO-RELACIONADOS", 50, 45000.0),
    ("BETA CIA", "F-3004", "NO-RELACIONADOS", 80, 28000.0),
    ("GAMMA S.A.", "F-3005", "NO-RELACIONADOS", 150, 22000.0),
    ("GAMMA S.A.", "F-3006", "NO-RELACIONADOS", 250, 18000.0),
    ("DELTA CIA", "F-3007", "NO-RELACIONADOS", 600, 14000.0),
    ("DELTA CIA", "F-3008", "NO-RELACIONADOS", 1000, 11000.0),
    ("GRANDES ALMACENES", "F-3100", "NO-RELACIONADOS", 10, 180000.0),
    ("GRANDES ALMACENES", "F-3101", "NO-RELACIONADOS", 200, 150000.0),
    ("RELACIONADA UNO", "F-4001", "RELACIONADOS", -5, 70000.0),
    ("RELACIONADA UNO", "F-4002", "RELACIONADOS", 120, 25000.0),
    ("RELACIONADA DOS", "F-4003", "RELACIONADOS", 500, 40000.0),
]
EXTRAS_2025 = [
    ("ALFA S.A.", "F-3002", "NO-RELACIONADOS", 20, 60000.0),   # fila idéntica repetida
    ("BETA CIA", "F-3003", "NO-RELACIONADOS", 50, 5000.0),     # mismo documento, otro saldo
]

PARAMETROS = {"entidad": "X", "materialidad": 50000, "umbral_individual": 200000,
              "eeff": {"no_relacionados": 1000000, "relacionados": 135300}}


def _xlsx(corte: date, filas) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = f"Cartera {corte.year}"
    ws.append(["Cliente", "N° Documento", "Tipo de cliente", "Fecha emisión",
               "Fecha vencimiento", "Saldo"])
    for cliente, doc, tipo, dias, saldo in filas:
        vence = date.fromordinal(corte.toordinal() - dias)
        emision = date.fromordinal(vence.toordinal() - 90)
        ws.append([cliente, doc, tipo, emision, vence, saldo])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _cortes() -> list[dict]:
    f23, f24, f25 = date(2023, 12, 31), date(2024, 12, 31), date(2025, 12, 31)
    intermedio = [(c, d, t, dias + 365, s) for c, d, t, dias, s in COHORTE_2023 if d in REMANENTES]
    remanentes = [(c, d, t, dias + 730, REMANENTES[d])
                  for c, d, t, dias, s in COHORTE_2023 if d in REMANENTES]
    return [
        {"nombre": "cartera_2023.xlsx", "contenido": _xlsx(f23, COHORTE_2023), "fecha": f23},
        {"nombre": "cartera_2024.xlsx", "contenido": _xlsx(f24, intermedio), "fecha": f24},
        {"nombre": "cartera_2025.xlsx",
         "contenido": _xlsx(f25, CARTERA_2025 + remanentes + EXTRAS_2025), "fecha": f25},
    ]


# ---------------------------------------------------------------------------
# Lectura de las celdas: openpyxl no evalúa fórmulas y el libro se escribe sin
# valores cacheados, así que las evalúa ``tests/excel_calc.py``, que recorre
# las referencias entre hojas igual que lo haría Excel. Antes aquí se
# reconocían A MANO las formas exactas que escribía el exportador, y eso ataba
# la prueba al TEXTO de la fórmula en vez de al número que produce: pasaba
# igual aunque la fórmula no aplicara los acotamientos del motor.
# ---------------------------------------------------------------------------

def _dec(valor) -> Decimal:
    return Decimal(str(valor))


# ---------------------------------------------------------------------------
# La prueba
# ---------------------------------------------------------------------------

def _informe(discrepancias: list[str]) -> str:
    """Todas las bandas que no cuadran, no solo la primera."""
    return "El papel no cuadra con lo archivado: " + " | ".join(discrepancias)


def _cuadre(resultado, parametros):
    """Rehace, desde las celdas del libro, la cuenta que haría el revisor.

    Devuelve la suma de las pérdidas de 05-Matriz recalculadas a mano, la suma
    de las de 06-Individual, cuántas bandas se midieron y qué bandas no cuadran
    contra lo que archivó la corrida.
    """
    libro = Libro(load_workbook(io.BytesIO(construir_excel(resultado, parametros))))
    wb = libro.wb
    ws = wb["05-Matriz"]
    por_banda = {(t.get("segmento"), t["tramo"]): t for t in resultado["matriz"]["tramos"]}
    suma_libro = Decimal("0.00")
    medidas = 0
    discrepancias = []
    for fila in range(2, ws.max_row + 1):
        segmento, banda = ws.cell(fila, 1).value, ws.cell(fila, 2).value
        if banda in (None, "TOTAL") or ws.cell(fila, 6).value == "SIN MEDIR":
            continue
        exposicion = _dec(ws.cell(fila, 3).value)
        tasa = _dec(libro.numero("05-Matriz", f"D{fila}"))
        # Lo que obtiene quien reabre el papel y rehace la cuenta con las cifras
        # que tiene delante: se EVALÚA la fórmula de la celda, no se
        # reimplementa aquí la cuenta que se supone que hace.
        segun_el_papel = _dec(libro.numero("05-Matriz", f"F{fila}"))
        archivado = _dec(por_banda[(segmento, banda)]["ecl"])
        if segun_el_papel != archivado:
            discrepancias.append(
                f"{segmento} / {banda}: el papel recalcula {segun_el_papel} "
                f"({exposicion} x {tasa}) y la corrida archivo {archivado}")
        suma_libro += segun_el_papel
        medidas += 1

    # 06-Individual escribe la PCE de cada caso como valor y su TOTAL la suma.
    wsi = wb["06-Individual"]
    suma_individual = sum(
        (_dec(wsi.cell(f, 5).value) for f in range(2, wsi.max_row)
         if isinstance(wsi.cell(f, 5).value, (int, float))), Decimal("0.00"))
    return wb, suma_libro, suma_individual, medidas, discrepancias


def test_el_papel_se_recalcula_desde_sus_propias_celdas():
    """Exposición × tasa × (1 + ajuste) = pérdida, al centavo, en cada banda
    medida de 05-Matriz; y el total del libro es el ``ecl_total`` archivado."""
    resultado = analizar(_cortes(), dict(PARAMETROS))
    wb, suma_libro, suma_individual, medidas, discrepancias = _cuadre(resultado, dict(PARAMETROS))

    assert medidas >= 5, "la corrida de prueba tiene que medir varias bandas"
    assert not discrepancias, _informe(discrepancias)

    # El TOTAL de 05-Matriz (=SUM(F...)) es la suma de esas mismas celdas.
    assert suma_libro == _dec(resultado["matriz"]["ecl_total"])
    assert suma_individual == _dec(resultado["individual"]["ecl_total"])

    # 09-Tributario B2 = '05-Matriz'!F(total) + '06-Individual'!E(total).
    assert str(wb["09-Tributario"]["B2"].value).startswith("='05-Matriz'!F")
    assert suma_libro + suma_individual == _dec(resultado["ecl_total"])


def test_el_caso_reportado_da_el_numero_del_excel():
    """El tramo «181 a 360 días» de NO-RELACIONADOS y los totales que el
    usuario contrastó abriendo el libro en Excel."""
    resultado = analizar(_cortes(), dict(PARAMETROS))
    tramo = next(t for t in resultado["matriz"]["tramos"]
                 if t.get("segmento") == "NO-RELACIONADOS" and t["tramo"] == "181 a 360 días")
    assert tramo["exposicion"] == 18209.41
    assert tramo["tasa_ajustada"] == 0.6
    assert tramo["ecl"] == 10925.65
    assert resultado["matriz"]["ecl_total"] == 102368.22
    assert resultado["ecl_total"] == 208943.84


def test_la_exposicion_anclada_sigue_cuadrando_con_los_eeff():
    """Redondear a centavos no puede desanclar la cartera de los EEFF: el
    remanente de centavos se reparte entre las propias filas ancladas."""
    resultado = analizar(_cortes(), dict(PARAMETROS))
    assert resultado["conciliacion"]["saldo_contable"] == 1135300.0
    assert resultado["conciliacion"]["diferencia"] == 0.0
    assert resultado["conciliacion"]["cuadra"] is True
    assert resultado["exposicion"]["total"] == 1135300.0


def test_el_redondeo_a_centavos_no_desancla_la_cartera_y_se_declara():
    """Sin evaluación individual las unidades de redondeo son las bandas
    completas, y su suma se aparta un centavo de la cartera anclada. Ese
    centavo se reparte entre las bandas -no se deja como descuadre contra los
    EEFF- y el papel lo declara en 12-Bitacora."""
    parametros = {k: v for k, v in PARAMETROS.items() if k != "umbral_individual"}
    resultado = analizar(_cortes(), parametros)

    assert resultado["bitacora"]["redondeo_exposicion"] == {"NO-RELACIONADOS": -1}
    # El ancla no se mueve: la conciliación sigue cuadrando al centavo.
    assert resultado["exposicion"]["total"] == 1135300.0
    assert resultado["conciliacion"]["diferencia"] == 0.0
    assert resultado["conciliacion"]["cuadra"] is True

    wb, suma_libro, suma_individual, medidas, discrepancias = _cuadre(resultado, parametros)
    assert medidas >= 5
    assert not discrepancias, _informe(discrepancias)
    assert suma_libro + suma_individual == _dec(resultado["ecl_total"])

    ws = wb["12-Bitacora"]
    fila = next(f for f in range(2, ws.max_row + 1)
                if ws.cell(f, 1).value == "Ajuste por redondeo de la exposición")
    detalle = str(ws.cell(fila, 2).value)
    assert "NO-RELACIONADOS: -1 centavo(s)" in detalle
    assert "05-Matriz" in detalle
