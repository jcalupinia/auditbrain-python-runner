"""Ninguna cota del módulo puede actuar en silencio ni quedarse fuera del papel.

Este archivo es la guarda que impide repetir el patrón que se rompió una vez
por ronda: una cota nueva se pone en el MOTOR, la fórmula del Excel se queda
con la cuenta cruda, y el papel empieza a decir algo distinto de lo que archiva
la corrida y muestra la pantalla. Pasó con ``05-Matriz`` (T1) y volvió a pasar
con ``08-Conciliacion`` (U1).

Son tres guardas, y ninguna depende de que alguien se acuerde:

1. `test_no_hay_ningun_recorte_fuera_del_helper` lee el CÓDIGO del módulo y
   falla si aparece un recorte escrito a mano. La única forma de acotar es
   `motor.acotar`, que devuelve el par (valor, motivo): no existe la variante
   "solo el número".
2. `test_toda_cota_registrada_tiene_un_escenario` falla si `motor.COTAS` gana
   una entrada sin un escenario donde esa cota ACTÚE.
3. Las dos pruebas parametrizadas comprueban, para cada cota, que la celda del
   papel recalcule al centavo lo archivado y que la celda vecina declare qué
   cota actuó.
"""
import ast
import inspect
import io
from datetime import date

import pytest
from openpyxl import Workbook, load_workbook

from backend.app.aud.pce_cxc import motor
from backend.app.aud.pce_cxc.exporter import SIN_ACOTAR, construir_excel
from backend.app.aud.pce_cxc.service import analizar
from tests.excel_calc import Libro

CENTAVO = 0.005

# Módulos donde no puede haber un recorte escrito a mano. `exporter.py` queda
# fuera a propósito: ahí las cotas SON las fórmulas de Excel, que es justo
# donde tienen que estar.
MODULOS_SIN_RECORTES_A_MANO = ("motor", "service", "cohortes", "lectura", "bandas")

#: Funciones del motor que SÍ pueden contener el recorte: es donde vive.
FUNCIONES_QUE_ACOTAN = {"acotar"}


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


COHORTE_2023 = [("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0)]
COHORTE_2024 = [("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 20000.0)]
COHORTE_2025 = [("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 10000.0)]


def _escenario_perdida_de_la_banda():
    """Piso cero: una nota de crédito deja la banda con exposición acreedora."""
    actual = COHORTE_2025 + [
        ("GAMMA", "F-9", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 200000.0),
        ("GAMMA", "NC-1", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), -250000.0),
    ]
    return analizar(_cortes(COHORTE_2023, COHORTE_2024, actual),
                    {"umbral_dias_incumplimiento": 730})


def _escenario_perdida_del_caso():
    """Piso cero en la evaluación individual: la pérdida provisional del caso
    sale negativa por una nota de crédito en una de sus bandas."""
    actual = COHORTE_2025 + [
        ("DELTA", "F-5", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), -100000.0),
        ("DELTA", "F-6", "NO-RELACIONADOS", date(2023, 1, 1), date(2023, 6, 1), 300000.0),
        ("OMEGA", "F-7", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 50000.0),
    ]
    return analizar(_cortes(COHORTE_2023, COHORTE_2024, actual),
                    {"umbral_dias_incumplimiento": 730, "umbral_individual": 100000})


def _escenario_cartera_medida():
    """Lo que no se pudo medir supera a la cartera estratificada."""
    actual = COHORTE_2025 + [
        ("BETA", "F-2", "NO-RELACIONADOS", date(2020, 1, 1), date(2020, 6, 1), 500000.0),
        ("GAMMA", "F-9", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 100000.0),
        ("GAMMA", "NC-1", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), -450000.0),
    ]
    return analizar(_cortes(COHORTE_2023, COHORTE_2024, actual),
                    {"umbral_dias_incumplimiento": 730, "umbral_individual": 100000})


def _escenario_tasa_observada():
    """La tasa observada de la cohorte se sale de [0 %; 100 %].

    El documento de la cohorte tiene MÁS saldo en el corte actual que en el
    corte t-2 (nueva facturación reclasificada al mismo número, una reversión o
    un error de carga), así que el ratio crudo pasa del 100 % y la cota lo topa
    en 1,00.
    """
    cohorte = [("ALFA", "F-1", "NO-RELACIONADOS", date(2019, 1, 1), date(2020, 1, 1), 100000.0)]
    intermedio = [("ALFA", "F-1", "NO-RELACIONADOS", date(2019, 1, 1), date(2020, 1, 1), 40000.0)]
    actual = [("ALFA", "F-1", "NO-RELACIONADOS", date(2019, 1, 1), date(2020, 1, 1), 200000.0)]
    return analizar(_cortes(cohorte, intermedio, actual),
                    {"umbral_dias_incumplimiento": 730})


#: Un escenario por cota, donde esa cota ACTÚA. Es lo que faltaba en las rondas
#: anteriores: las pruebas que evaluaban la celda solo corrían escenarios donde
#: la cota no mordía.
ESCENARIOS = {
    "perdida_esperada_de_la_banda": _escenario_perdida_de_la_banda,
    "perdida_esperada_del_caso_individual": _escenario_perdida_del_caso,
    "saldo_sin_medir_del_caso_individual": _escenario_perdida_del_caso,
    "tasa_observada_de_la_cohorte": _escenario_tasa_observada,
    "cartera_medida": _escenario_cartera_medida,
}

#: Lo que la corrida archiva para cada cota, celda a celda del papel. Cada
#: entrada devuelve `{fila_de_datos: importe archivado}` o, para las cotas de
#: fila fija, `{fila: importe}`.
def _archivado_perdida_de_la_banda(resultado, ws):
    salida = {}
    for i in range(2, ws.max_row + 1):
        clave = (ws.cell(i, 1).value, ws.cell(i, 2).value)
        if clave[1] in (None, "TOTAL"):
            break
        t = next((t for t in resultado["matriz"]["tramos"]
                  if (t.get("segmento"), t["tramo"]) == clave), None)
        if t and t["ecl"] is not None:
            salida[i] = (t["ecl"], t["acotado"])
    return salida


def _archivado_del_caso(resultado, ws, campo, campo_acotado):
    salida = {}
    casos = resultado["individual"]["casos"]
    for i, caso in zip(range(2, 2 + len(casos)), casos):
        salida[i] = (caso[campo], caso[campo_acotado])
    return salida


def _archivado_tasa_observada(resultado, ws):
    """Tasa aplicada y motivo de la cota, fila a fila de `04-Tasas`."""
    salida = {}
    tasas = resultado.get("tasas") or {}
    anomalias = resultado.get("anomalias") or []
    for i in range(2, ws.max_row + 1):
        segmento, banda = ws.cell(i, 1).value, ws.cell(i, 2).value
        if not segmento or not banda:
            break
        tasa = (tasas.get(segmento) or {}).get(banda)
        if tasa is None:
            continue
        anomalia = next((a for a in anomalias
                         if a.get("segmento") == segmento and a.get("banda") == banda), None)
        salida[i] = (tasa, (anomalia or {}).get("cota"))
    return salida


ARCHIVADO = {
    "perdida_esperada_de_la_banda": _archivado_perdida_de_la_banda,
    "tasa_observada_de_la_cohorte": _archivado_tasa_observada,
    "perdida_esperada_del_caso_individual":
        lambda r, ws: _archivado_del_caso(r, ws, "ecl", "acotado"),
    "saldo_sin_medir_del_caso_individual":
        lambda r, ws: _archivado_del_caso(r, ws, "saldo_sin_tasa", "saldo_sin_tasa_acotado"),
    # La fila la declara `motor.COTAS`, no esta prueba: clavarla aquí era otra
    # copia del número de fila, justo el error que `excel_calc.columna` vino a
    # quitar de las pruebas de columnas.
    "cartera_medida":
        lambda r, ws: {next(c.fila for c in motor.COTAS if c.nombre == "cartera_medida"):
                       (r["exposicion"]["medida"], r["exposicion"]["medida_acotada"])},
}


# ---------------------------------------------------------------------------
# Guarda 1 — ningún recorte fuera de `motor.acotar`
# ---------------------------------------------------------------------------

class _BuscadorDeRecortes(ast.NodeVisitor):
    """Encuentra `min(max(...), ...)` y `max(min(...), ...)` escritos a mano.

    Un recorte así devuelve SOLO el número: es exactamente la forma en la que
    las cotas de este módulo terminaron aplicándose en silencio, porque quien
    lo escribe no recibe ningún motivo que declarar.
    """

    def __init__(self):
        self.hallazgos = []
        self._funcion = []

    def visit_FunctionDef(self, nodo):  # noqa: N802 (nombre de la API de ast)
        self._funcion.append(nodo.name)
        self.generic_visit(nodo)
        self._funcion.pop()

    def visit_Call(self, nodo):  # noqa: N802
        if self._funcion and self._funcion[-1] in FUNCIONES_QUE_ACOTAN:
            return  # es el helper: aquí es donde el recorte debe vivir
        externo = getattr(nodo.func, "id", None)
        if externo in ("min", "max") and len(nodo.args) == 2:
            for arg in nodo.args:
                interno = getattr(getattr(arg, "func", None), "id", None)
                if interno in ("min", "max") and interno != externo:
                    self.hallazgos.append(
                        (nodo.lineno, self._funcion[-1] if self._funcion else "<módulo>"))
        self.generic_visit(nodo)


@pytest.mark.parametrize("nombre_modulo", MODULOS_SIN_RECORTES_A_MANO)
def test_no_hay_ningun_recorte_fuera_del_helper(nombre_modulo):
    """`min(max(x, piso), techo)` escrito a mano es una cota que no declara nada.

    La única forma de acotar en este módulo es `motor.acotar`, que devuelve el
    par (valor, motivo): así el motivo no se puede tirar por descuido, y
    `COTAS` obliga a que llegue al papel.
    """
    modulo = __import__(f"backend.app.aud.pce_cxc.{nombre_modulo}",
                        fromlist=[nombre_modulo])
    arbol = ast.parse(inspect.getsource(modulo))
    buscador = _BuscadorDeRecortes()
    buscador.visit(arbol)
    assert not buscador.hallazgos, (
        f"{nombre_modulo}.py acota a mano en {buscador.hallazgos}: use `motor.acotar`, que "
        "devuelve el motivo junto al valor, y registre la cota en `motor.COTAS` para que el "
        "papel la reproduzca en su fórmula."
    )


# ---------------------------------------------------------------------------
# Guarda 2 — toda cota registrada tiene escenario, celda y declaración
# ---------------------------------------------------------------------------

def test_toda_cota_registrada_tiene_un_escenario():
    """Una cota nueva sin escenario donde ACTÚE no está probada: las rondas
    anteriores tenían pruebas sobre la celda que solo corrían escenarios donde
    la cota no mordía, y por eso quitar la cota dejaba todo en verde."""
    faltan = [c.nombre for c in motor.COTAS if c.nombre not in ESCENARIOS]
    assert not faltan, (
        f"Cotas registradas en motor.COTAS sin escenario en esta prueba: {faltan}. "
        "Añada un escenario donde la cota ACTÚE y su entrada en ARCHIVADO.")
    sobran = [n for n in ESCENARIOS if n not in {c.nombre for c in motor.COTAS}]
    assert not sobran, f"Escenarios sin cota registrada: {sobran}"


@pytest.mark.parametrize("cota", motor.COTAS, ids=lambda c: c.nombre)
def test_la_cota_actua_en_su_escenario(cota):
    """Un escenario donde la cota no muerde no prueba nada sobre la cota."""
    resultado = ESCENARIOS[cota.nombre]()
    libro = Libro(load_workbook(io.BytesIO(construir_excel(resultado, {}))))
    archivado = ARCHIVADO[cota.nombre](resultado, libro.wb[cota.hoja])
    assert any(motivo for _, motivo in archivado.values()), (
        f"{cota.nombre}: el escenario no hace actuar la cota que acota "
        f"«{cota.que_acota}», así que la prueba no prueba nada.")


@pytest.mark.parametrize("cota", motor.COTAS, ids=lambda c: c.nombre)
def test_el_papel_recalcula_el_valor_acotado(cota):
    """La celda del papel tiene que dar, al centavo, lo que archivó la corrida,
    EN EL ESCENARIO DONDE LA COTA ACTÚA."""
    if cota.columna_valor is None:
        pytest.skip(f"{cota.nombre}: el papel imprime el importe medido, no lo deriva")
    resultado = ESCENARIOS[cota.nombre]()
    libro = Libro(load_workbook(io.BytesIO(construir_excel(resultado, {}))))
    archivado = ARCHIVADO[cota.nombre](resultado, libro.wb[cota.hoja])
    filas = [cota.fila] if cota.fila else list(archivado)
    for fila in filas:
        esperado = archivado[fila][0]
        celda = f"{cota.columna_valor}{fila}"
        # Tiene que ser una FÓRMULA. Comparar solo la cifra no separa una
        # fórmula de un número pegado -mientras nadie toque el libro los dos
        # dan lo mismo-, y un número pegado deja de cuadrar en cuanto el
        # revisor corrige una celda, que es para lo que existe el papel.
        crudo = libro.wb[cota.hoja][celda].value
        assert isinstance(crudo, str) and crudo.startswith("="), (
            f"{cota.nombre}: {cota.hoja}!{celda} es un valor pegado ({crudo!r}), no una "
            f"fórmula: el papel no recalcularía «{cota.que_acota}» desde sus propias celdas.")
        assert libro.numero(cota.hoja, celda) == pytest.approx(esperado, abs=CENTAVO), (
            f"{cota.nombre}: {cota.hoja}!{celda} recalcula distinto de lo archivado "
            f"({cota.que_acota})")


@pytest.mark.parametrize("cota", motor.COTAS, ids=lambda c: c.nombre)
def test_el_papel_declara_que_la_cota_actuo(cota):
    """Y la celda vecina tiene que decir qué cota actuó, no «SIN ACOTAR»."""
    resultado = ESCENARIOS[cota.nombre]()
    libro = Libro(load_workbook(io.BytesIO(construir_excel(resultado, {}))))
    archivado = ARCHIVADO[cota.nombre](resultado, libro.wb[cota.hoja])
    declarados = []
    for fila, (_, motivo) in archivado.items():
        objetivo = cota.fila_declaracion or fila
        celda = f"{cota.columna_declaracion}{objetivo}"
        texto = str(libro.valor(cota.hoja, celda) or "")
        if motivo:
            assert texto and texto != SIN_ACOTAR, (
                f"{cota.nombre}: la corrida declara «{motivo}» en la fila {fila} y "
                f"{cota.hoja}!{celda} dice «{texto}»")
            declarados.append(texto)
    assert declarados, f"{cota.nombre}: ninguna fila declaró el acotamiento"
