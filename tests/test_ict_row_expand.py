"""Tests para el helper de expansión de bloques tabulares (row_expand).

Cuando un anexo tiene más datos que filas disponibles (ej. A5 Cuadro A con
15 casilleros no deducibles vs 5 filas), se insertan filas y se reajustan
las fórmulas del template que quedaron desplazadas.

openpyxl.insert_rows NO reajusta las referencias de las fórmulas; este helper
(`shift_formula_rows`) lo hace: suma `amount` a cada referencia de fila >=
`threshold`, respetando refs absolutas ($), rangos, y SIN tocar literales
de texto entre comillas ni referencias a otras hojas.
"""
from __future__ import annotations

from backend.app.ict.fillers.row_expand import shift_formula_rows


def test_shift_simple_sum_range():
    # =SUM(G28:G32) con inserción de 3 filas en pos 22 → ambos refs >= 22 +3
    assert shift_formula_rows("=SUM(G28:G32)", threshold=22, amount=3) == "=SUM(G31:G35)"


def test_shift_no_cambia_refs_por_encima_del_umbral():
    # K17 y K21 están por encima del umbral (17,21 < 22) → no cambian
    assert shift_formula_rows("=SUM(K17:K21)", threshold=22, amount=3) == "=SUM(K17:K21)"


def test_shift_refs_mixtas():
    # =+K22+G51+H61-H72 con +3: todas >= 22 → +3
    assert shift_formula_rows("=+K22+G51+H61-H72", threshold=22, amount=3) == "=+K25+G54+H64-H75"


def test_shift_no_toca_porcentajes_ni_numeros_sueltos():
    # 15% NO es una referencia de celda (no tiene letra de columna delante)
    f = "=IF(((H59-H60)>=0),(H58*15%)+((H59-H60)*15%),(H58*15%))"
    out = shift_formula_rows(f, threshold=22, amount=3)
    assert out == "=IF(((H62-H63)>=0),(H61*15%)+((H62-H63)*15%),(H61*15%))"


def test_shift_respeta_literales_de_texto_entre_comillas():
    # "0,00%" es un literal — no debe modificarse
    f = '=IF(G33=0,"0,00%",G33/G41)'
    out = shift_formula_rows(f, threshold=22, amount=3)
    assert out == '=IF(G36=0,"0,00%",G36/G44)'


def test_shift_referencias_absolutas():
    # $B$17 con umbral 22: 17 < 22 → no cambia; $B$30 → $B$33
    assert shift_formula_rows("=$B$30+$B$17", threshold=22, amount=3) == "=$B$33+$B$17"


def test_shift_no_toca_referencias_a_otra_hoja():
    # 'DATOS F-101'!C500 es una ref externa — la fila NO debe desplazarse
    f = "='DATOS F-101'!C500"
    assert shift_formula_rows(f, threshold=22, amount=3) == "='DATOS F-101'!C500"


def test_shift_amount_cero_es_identidad():
    f = "=+K22+G51+H61-H72"
    assert shift_formula_rows(f, threshold=22, amount=0) == f
