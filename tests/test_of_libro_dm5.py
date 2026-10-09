"""DM5 Ventas: ventas gravadas, ventas 0% e IVA en ventas, libros vs declaraciones."""

import datetime
from io import BytesIO

from openpyxl import Workbook, load_workbook

from backend.app.aud.obligaciones_fiscales.libro.cedulas.dm5_ventas import (
    CASILLEROS_IVA_VENTAS, CASILLEROS_VENTAS, CASILLEROS_VENTAS_0, ETIQUETA_POR_ASIGNAR,
    SHEET_DM5, build_dm5,
)
from backend.app.aud.obligaciones_fiscales.libro.ensamblador import armar_libro
from backend.app.aud.obligaciones_fiscales.mayor.tipos import Movimiento

PERIODOS = [f"2025-{m:02d}" for m in range(1, 13)]

# 4.1.1.1.1 es gravada ≠0%; 4.1.1.1.2 es 0% local. hoja_mayores publica la
# lista de cuentas con movimiento por tramo (`cuentas_tramo:<tramo>`) y la
# dirección de cada cuenta en su tramo.
DIR_MAYORES = {
    ("cuenta:4.1.1.1.1", "01"): "'Mayores homologados'!D4",
    ("cuenta:4.1.1.1.2", "01"): "'Mayores homologados'!D5",
    ("cuenta:4.1.1.1.1:gravada", "01"): "'Mayores homologados'!D40",
    ("cuenta:4.1.1.1.2:cero", "01"): "'Mayores homologados'!D44",
    ("cuentas_tramo:gravada", "cuentas"): ["4.1.1.1.1"],
    ("cuentas_tramo:exportacion", "cuentas"): [],
    ("cuentas_tramo:cero", "cuentas"): ["4.1.1.1.2"],
    ("cuentas_tramo:reembolso", "cuentas"): [],
    ("cuentas_tramo:otro_ingreso", "cuentas"): [],
    ("cuentas_tramo:por_asignar", "cuentas"): [],
    ("VENTAS:por_asignar", "01"): "'Mayores homologados'!D52",
    ("orden:VENTAS", "cuentas"): ["4.1.1.1.1", "4.1.1.1.2"],
    ("cuenta:2.1.3.1.1", "01"): "'Mayores homologados'!D8",
    ("orden:IVA_VENTAS", "cuentas"): ["2.1.3.1.1"],
}

_TODOS_CASILLEROS = list(dict.fromkeys(
    CASILLEROS_VENTAS + CASILLEROS_VENTAS_0 + CASILLEROS_IVA_VENTAS
))
DIR_F104 = {("2025-01", cas): f"'DATOS F-104'!C{i}"
            for i, cas in enumerate(_TODOS_CASILLEROS, start=20)}

NOMBRES = {
    "4.1.1.1.1": "Ventas Tarifa 15%",
    "4.1.1.1.2": "Ventas Tarifa 0%",
    "2.1.3.1.1": "IVA en Ventas",
}


def _cedula(**kw):
    wb = Workbook()
    datos = dict(dir_mayores=DIR_MAYORES, dir_f104=DIR_F104, periodos=PERIODOS,
                 nombres_cuenta=NOMBRES, cliente="C", periodo="2025")
    datos.update(kw)
    build_dm5(wb, **datos)
    return wb[SHEET_DM5]


def _etiquetas(ws):
    return [ws.cell(r, 2).value for r in range(1, ws.max_row + 1)]


def test_cada_cuenta_aparece_solo_en_el_bloque_de_su_tramo():
    """Con la tarifa leída de la cuenta, cada cuenta aparece una sola vez, en
    el bloque de su tramo (la gravada en «gravadas», la 0% en «0% local»)."""
    ws = _cedula()
    etiquetas = _etiquetas(ws)
    assert etiquetas.count("Ventas Tarifa 15%") == 1
    assert etiquetas.count("Ventas Tarifa 0%") == 1


def test_el_bloque_de_iva_en_ventas_lista_su_cuenta():
    ws = _cedula()
    assert "IVA en Ventas" in _etiquetas(ws)


def test_el_valor_de_una_cuenta_es_una_formula_al_resumen():
    ws = _cedula()
    fila = next(r for r in range(1, ws.max_row + 1)
                if ws.cell(r, 2).value == "IVA en Ventas")
    assert ws.cell(fila, 3).value == "='Mayores homologados'!D8"


def test_los_casilleros_son_formulas_a_la_hoja_de_datos_no_valores():
    ws = _cedula()
    fila = next(r for r in range(1, ws.max_row + 1)
                if str(ws.cell(r, 2).value or "").startswith("Casillero 411"))
    valor = ws.cell(fila, 3).value
    assert isinstance(valor, str) and valor.startswith("='DATOS F-104'!")


def test_estan_los_casilleros_de_los_tres_bloques():
    ws = _cedula()
    etiquetas = [str(ws.cell(r, 2).value or "") for r in range(1, ws.max_row + 1)]
    for cas in CASILLEROS_VENTAS + CASILLEROS_VENTAS_0 + CASILLEROS_IVA_VENTAS:
        assert any(e.startswith(f"Casillero {cas}") for e in etiquetas), cas


def test_hay_una_diferencia_por_cada_bloque_cruzado():
    # Gravadas, exportación, 0% local, reembolsos e IVA en ventas cruzan contra
    # casilleros (5 diferencias). "Otros ingresos" es informativo, sin cruce.
    ws = _cedula()
    assert _etiquetas(ws).count("Diferencia") == 5


def test_la_diferencia_resta_libros_menos_declarado_y_redondea():
    ws = _cedula()
    filas = [r for r in range(1, ws.max_row + 1) if ws.cell(r, 2).value == "Diferencia"]
    for fila in filas:
        assert ws.cell(fila, 3).value.startswith("=ROUND(")


def test_hay_una_fila_total_ventas_declaradas():
    ws = _cedula()
    assert "Total ventas declaradas" in _etiquetas(ws)


def test_el_total_declarado_suma_las_dos_filas_con_sum_no_con_mas():
    """`=SUM(C20,C35)` y no `=C20+C35`.

    Es la única suma de celdas sueltas de la MISMA hoja en toda la cédula.
    Escribirla como SUM mantiene la regla del libro: en DM3..DM8, una fórmula
    que son puras referencias unidas por '+' es siempre una referencia a otra
    hoja y por tanto debe ir calificada. Sin esto, esta fila es un falso
    positivo permanente del test de regresión de direcciones.
    """
    ws = _cedula()
    fila = next(r for r in range(1, ws.max_row + 1)
                if ws.cell(r, 2).value == "Total ventas declaradas")
    formula = ws.cell(fila, 3).value
    assert formula.startswith("=SUM("), formula
    assert "+" not in formula, formula


def test_lleva_el_encabezado_de_cedula_con_su_referencia():
    ws = _cedula()
    valores = [ws.cell(r, c).value for r in range(1, 11) for c in range(1, 6)]
    assert "OBLIGACIONES FISCALES" in valores
    assert "DM5" in valores


def test_publica_las_direcciones_que_dm6_consume():
    wb = Workbook()
    lookup = build_dm5(wb, dir_mayores=DIR_MAYORES, dir_f104=DIR_F104, periodos=PERIODOS,
                        nombres_cuenta=NOMBRES, cliente="C", periodo="2025")
    for clave in ("ventas_libros", "ventas_0_libros", "iva_ventas_libros", "total_declarado"):
        assert (clave, "01") in lookup, clave
        assert lookup[(clave, "01")].startswith(f"'{SHEET_DM5}'!")


def test_la_direccion_publicada_de_ventas_libros_apunta_a_la_fila_segun_libros():
    wb = Workbook()
    lookup = build_dm5(wb, dir_mayores=DIR_MAYORES, dir_f104=DIR_F104, periodos=PERIODOS,
                        nombres_cuenta=NOMBRES, cliente="C", periodo="2025")
    ws = wb[SHEET_DM5]
    addr = lookup[("ventas_libros", "01")]
    fila = int(addr.split("!")[1].lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    assert ws.cell(fila, 2).value == "Según libros"


def test_el_bloque_crece_con_mas_cuentas_de_venta_y_el_subtotal_se_desplaza():
    """El numero de cuentas de venta varia por cliente: el subtotal debe
    sumar exactamente el rango de cuentas listadas, no una posicion fija."""
    dir_mayores_grande = {
        **{(f"cuenta:4.1.1.1.{i}", "01"): f"'Mayores homologados'!D{i}" for i in range(1, 13)},
        ("orden:VENTAS", "cuentas"): [f"4.1.1.1.{i}" for i in range(1, 13)],
    }
    nombres_grande = {f"4.1.1.1.{i}": f"Venta {i}" for i in range(1, 13)}
    wb = Workbook()
    build_dm5(wb, dir_mayores=dir_mayores_grande, dir_f104=DIR_F104, periodos=PERIODOS,
              nombres_cuenta=nombres_grande, cliente="C", periodo="2025")
    ws = wb[SHEET_DM5]
    primera_fila_libros = next(r for r in range(1, ws.max_row + 1)
                                if ws.cell(r, 2).value == "Según libros")
    formula = ws.cell(primera_fila_libros, 3).value
    assert formula == f"=SUM(C14:C{primera_fila_libros - 1})"


# ------------------------------------------- separación gravadas / 0% ---
#
# El motor agrega por cuenta y mes sin distinguir tarifa: los dos bloques de
# ventas leían la MISMA celda del resumen y contrastaban esa única cifra
# contra casilleros distintos del F-104. Ahora cada bloque lee su tramo del
# desglose por asiento que publica la hoja de mayores.

def _fila_del_titulo(ws, titulo: str) -> int:
    return next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == titulo)


def test_cada_bloque_de_ventas_lee_su_propio_tramo_del_desglose():
    ws = _cedula()
    primera_grav = _fila_del_titulo(ws, "VENTAS GRAVADAS ≠ 0%") + 1
    primera_cero = _fila_del_titulo(ws, "VENTAS 0% LOCAL") + 1
    assert ws.cell(primera_grav, 3).value == "='Mayores homologados'!D40"
    assert ws.cell(primera_cero, 3).value == "='Mayores homologados'!D44"


def test_no_hay_fila_por_asignar_cuando_todas_las_cuentas_tienen_tarifa():
    """Con la tarifa leída de la cuenta ninguna queda 'por asignar': esa fila
    informativa sólo aparece si el reparto por asiento no cuadró una cuenta."""
    ws = _cedula()
    assert _etiquetas(ws).count(ETIQUETA_POR_ASIGNAR) == 0


def test_la_fila_por_asignar_aparece_cuando_hay_cuentas_sin_tarifa():
    ws = _cedula(dir_mayores={
        **DIR_MAYORES,
        ("cuentas_tramo:por_asignar", "cuentas"): ["4.1.1.1.1"],
    })
    etiquetas = _etiquetas(ws)
    assert etiquetas.count(ETIQUETA_POR_ASIGNAR) == 1
    fila = etiquetas.index(ETIQUETA_POR_ASIGNAR) + 1
    assert ws.cell(fila, 3).value == "='Mayores homologados'!D52"
    # Va DESPUÉS del "Según libros" del bloque gravadas (fuera de su suma).
    fila_libros = next(r for r in range(1, ws.max_row + 1)
                       if ws.cell(r, 2).value == "Según libros")
    assert fila_libros < fila


# --------------------------------------- regresión: DM5!C14 vs DM5!C36 ---

class _FilaClasif:
    def __init__(self, codigo, nombre, categoria, por_mes):
        self.codigo_cuenta = codigo
        self.nombre_cuenta = nombre
        self.categoria_final = categoria
        self.por_mes_json = por_mes
        self.n_movimientos = 1
        self.debe = 0.0
        self.haber = 0.0


def _mov(codigo, haber, asiento):
    return Movimiento(codigo=codigo, asiento=asiento,
                      fecha=datetime.date(2025, 1, 15), haber=haber)


def test_los_dos_bloques_de_ventas_ya_no_apuntan_a_la_misma_celda():
    """Regresión del defecto reportado: DM5!C14 y DM5!C36 leían ambos
    'Mayores homologados'!D30, así que los dos bloques mostraban la misma
    cifra contrastada contra casilleros distintos."""
    filas = [
        _FilaClasif("4.1.1.1", "Venta de mercadería", "VENTAS", {"01": 1150.0}),
        _FilaClasif("2.1.7.4.1", "IVA en ventas", "IVA_VENTAS", {"01": 120.0}),
    ]
    movimientos = [
        _mov("4.1.1.1", 100.0, "VTA 1"), _mov("4.1.1.1", 250.0, "VTA 1"),
        _mov("4.1.1.1", 300.0, "VTA 1"), _mov("2.1.7.4.1", 45.0, "VTA 1"),
        _mov("4.1.1.1", 500.0, "VTA 2"), _mov("2.1.7.4.1", 75.0, "VTA 2"),
    ]
    wb = load_workbook(BytesIO(armar_libro(
        clasificacion=filas, movimientos=movimientos,
        f104_monthly={"2025-01": {"casilleros": {"411": 800.0}}},
        f103_monthly={}, cliente="C", periodo="2025",
    )))
    ws = wb[SHEET_DM5]
    fila_no_cero = _fila_del_titulo(ws, "VENTAS GRAVADAS ≠ 0%") + 1
    fila_cero = _fila_del_titulo(ws, "VENTAS 0% LOCAL") + 1
    gravada = ws.cell(fila_no_cero, 3).value
    cero = ws.cell(fila_cero, 3).value
    assert gravada != cero, gravada
    mayores = wb["Mayores homologados"]
    assert mayores[gravada.split("!", 1)[1]].value == 800.0
    assert mayores[cero.split("!", 1)[1]].value == 350.0


# ---------------------------------- casilleros sin duplicar (regresión) ---

def test_los_casilleros_de_ventas_no_se_duplican_entre_bloques():
    """412 y 444 estaban en los dos bloques e inflaban el 'Total ventas
    declaradas'. Ningún casillero debe aparecer en ≠0% y en 0% a la vez."""
    assert set(CASILLEROS_VENTAS).isdisjoint(CASILLEROS_VENTAS_0)


def test_el_412_es_gravado_y_el_444_reembolso_no_entra():
    # 412 = ventas de activos fijos gravadas ≠0% → bloque gravadas.
    assert "412" in CASILLEROS_VENTAS
    assert "412" not in CASILLEROS_VENTAS_0
    # 444 = reembolsos (informativo) → fuera de ambos bloques de ventas.
    assert "444" not in CASILLEROS_VENTAS
    assert "444" not in CASILLEROS_VENTAS_0
