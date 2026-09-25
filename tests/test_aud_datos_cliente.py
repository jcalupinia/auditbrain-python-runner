"""Datos del cliente dentro del libro en las 19 herramientas que no los arman a mano
(decisión del dueño, 2026-09-25: extender el piloto de pérdidas incurridas a todas).

``procesadores/datos_cliente.py`` agrega una hoja ``D<n>_…`` por documento entregado (con la
columna «Origen del dato» y la guía «¿De dónde saco este dato?») y cambia cada dato del cliente
que una cédula traía pegado por una fórmula a su celda en esa hoja. La igualdad fórmula = valor
en LibreOffice la comprueba ``python scripts/verificar_datos_cliente.py`` («DIFERENCIAS: 0»).
"""
import re

import pytest
from openpyxl.utils import column_index_from_string

from backend.app.aud.niif import ejercicio_modelo as em
from backend.app.aud.niif.procesadores import PROCESADORES, datos_cliente, libro

IDS = [p for p in PROCESADORES if p not in datos_cliente.PROPIAS]
CELDA = r"'(D\d+_[^']+)'!([A-Z]+)(\d+)"
# Formas de un enlace: la celda, VALUE(celda) si el cliente entregó el número como texto, o
# IF(celda="",otra,celda) cuando la herramienta usa otro dato de la fila o un valor por defecto.
REF = re.compile(rf"^(?:{CELDA}|VALUE\({CELDA}\)|IF\({CELDA}=\"\",(?:{CELDA}|-?[\d.]+),{CELDA}\))$")


def _valor_de(datos, hoja, col, fila):
    return datos[hoja]["rows"][int(fila) - 5][column_index_from_string(col) - 1]


def _papel(pid):
    mod = PROCESADORES[pid]
    ds, par, corte = em.escenario(mod)
    run = mod.ejecutar(ds, par, corte)
    return mod, ds, mod.hojas(run), datos_cliente.con_datos(mod, run, ds)


def test_son_las_19_herramientas():
    assert len(IDS) == 19 and "perdidas_incurridas_s11" not in IDS


@pytest.mark.parametrize("pid", IDS)
def test_una_hoja_por_documento_entregado(pid):
    mod, ds, _, hojas = _papel(pid)
    datos = [h for h in hojas if re.match(r"D\d+_", h["name"])]
    entregados = [r["dataset"] for r in mod.definicion()["requests"] if r.get("dataset") and ds.get(r["dataset"])]
    assert [h["dataset"] for h in datos] == entregados
    for h in datos:
        assert len(h["name"]) <= 31 and h["label"].startswith("Datos del cliente · ")
        assert h["cols"][-1][0] == "Origen del dato" and h["guia"].startswith("Documento RQ-")
        assert len(h["rows"]) == len(ds[h["dataset"]])
        assert all(f[-1] and "fila" in f[-1] for f in h["rows"]), "cada fila dice de qué archivo, hoja y fila viene"
        assert libro._seccion(h) == 2, "va en la sección «Datos del cliente» del libro"


@pytest.mark.parametrize("pid", IDS)
def test_las_cedulas_leen_los_datos_del_cliente(pid):
    """Cada enlace apunta a una celda de una hoja de datos con el MISMO valor, y ninguna cifra cambia."""
    _, _, antes, despues = _papel(pid)
    datos = {h["name"]: h for h in despues if re.match(r"D\d+_", h["name"])}
    n = 0
    for h0, h in zip(antes, despues):
        assert h0["name"] == h["name"]
        for f0, f in zip(h0["rows"], h["rows"]):
            for a, b in zip(f0, f):
                if isinstance(b, dict) and not isinstance(a, dict):
                    m = REF.match(b["f"])
                    assert m, b["f"]
                    g = [x for x in m.groups()]
                    assert b["v"] == a
                    if g[0]:
                        celda = _valor_de(datos, *g[0:3])
                    elif g[3]:
                        celda = _valor_de(datos, *g[3:6])
                    else:
                        assert g[6:9] == g[12:15], b["f"]
                        celda = _valor_de(datos, *g[6:9])
                        if celda in (None, ""):
                            celda = _valor_de(datos, *g[9:12]) if g[9] else float(b["f"].split(",")[1])
                    assert datos_cliente._igual(a, celda), (h["name"], b["f"], a, celda)
                    n += 1
                else:
                    assert a == b, "una celda que no se enlaza no cambia"
    assert n >= 20, f"{pid}: solo {n} datos del cliente enlazados"


@pytest.mark.parametrize("pid", IDS)
def test_cada_columna_enlazada_se_explica(pid):
    _, _, _, hojas = _papel(pid)
    for h in hojas:
        for b in libro.como_se_calcula(h, hojas):
            assert libro.PLANTILLA_GENERICA not in b["explicacion"], (pid, h["name"], b["columna"])


def test_una_columna_con_un_calculo_que_a_veces_coincide_no_se_enlaza():
    datos = [{"name": "D1_X", "label": "Datos del cliente · X", "cols": [["Id", "t"], ["Saldo", "n"], ["Origen del dato", "t"]],
              "rows": [["A1", 100.0, "o"], ["A2", 50.0, "o"]]}]
    ced = [{"name": "03_Detalle", "label": "Detalle", "cols": [["Id", "t"], ["Saldo", "n"], ["Saldo ajustado", "n"]],
            "rows": [["A1", 100.0, 100.0], ["A2", 50.0, 45.0]]}]
    out, n = datos_cliente.enlazar(ced, datos)
    assert n == 2
    filas = out[0]["rows"]
    assert filas[0][1] == {"f": "'D1_X'!B5", "v": 100.0} and filas[1][1] == {"f": "'D1_X'!B6", "v": 50.0}
    assert filas[0][2] == 100.0 and filas[1][2] == 45.0, "«Saldo ajustado» es un cálculo: queda como estaba"


def test_dato_en_blanco_usa_otro_dato_de_la_fila_o_el_valor_por_defecto():
    datos = [{"name": "D1_X", "label": "Datos del cliente · X",
              "cols": [["Id", "t"], ["Fecha del acta", "d"], ["Fecha de registro", "d"], ["Pagos por año", "n"], ["Año", "t"],
                       ["Origen del dato", "t"]],
              "rows": [["A1", "2025-03-20", "2025-03-28", 2.0, "2019", "o"], ["A2", None, "2025-11-30", None, "2020", "o"]]}]
    ced = [{"name": "03_Detalle", "label": "Detalle",
            "cols": [["Id", "t"], ["Fecha efectiva (acta o registro)", "d"], ["Pagos por año", "i"], ["Año de origen", "i"]],
            "rows": [["A1", "2025-03-20", 2, 2019], ["A2", "2025-11-30", 1, 2020]]}]
    out, n = datos_cliente.enlazar(ced, datos)
    f = out[0]["rows"]
    assert n == 6
    assert f[1][1] == {"f": "IF('D1_X'!B6=\"\",'D1_X'!C6,'D1_X'!B6)", "v": "2025-11-30"}
    assert f[1][2] == {"f": "IF('D1_X'!D6=\"\",1,'D1_X'!D6)", "v": 1}
    assert f[0][3] == {"f": "VALUE('D1_X'!E5)", "v": 2019}


def test_sin_datos_no_cambia_nada():
    mod = PROCESADORES["cxc_cartera"]
    ds, par, corte = em.escenario(mod)
    run = mod.ejecutar(ds, par, corte)
    assert datos_cliente.con_datos(mod, run, {}) == mod.hojas(run)
    pi = PROCESADORES["perdidas_incurridas_s11"]
    ds, par, corte = em.escenario(pi)
    run = pi.ejecutar(ds, par, corte)
    assert datos_cliente.con_datos(pi, run, ds) == pi.hojas(run), "el piloto conserva sus propias hojas"


def test_html_y_word_muestran_la_guia():
    import io

    from docx import Document

    mod = PROCESADORES["nomina_beneficios"]
    d = mod.definicion()
    ds, par, corte = em.escenario(mod)
    reg = em._reg(d, mod, ds, par, corte)
    h = libro.html(d, reg, [], 1, "APROBADO").decode()
    assert h.count('<p class="guia"><b>¿De dónde saco este dato?</b>') >= 2
    doc = Document(io.BytesIO(libro.docx(d, reg, [], 1, "APROBADO")))
    assert sum(p.text.startswith("¿De dónde saco este dato?") for p in doc.paragraphs) >= 2


@pytest.mark.parametrize("pid", list(PROCESADORES))
def test_ninguna_cifra_ni_fecha_queda_pegada(pid):
    """Pedido del dueño (2026-09-25, «hazlo de todo»): en las cédulas no queda ningún importe ni fecha
    como valor fijo. Los datos del cliente son fórmulas a su hoja «Datos del cliente», los cálculos son
    fórmulas y los importes de «Problemas» remiten a su cédula. Solo son valores los parámetros del
    auditor (02_Parametros) y la carátula/documentación (00_…)."""
    mod = PROCESADORES[pid]
    d = mod.definicion()
    ds, par, corte = em.escenario(mod)
    fijos = []
    for h in libro.cedulas(d, em._reg(d, mod, ds, par, corte), [], 1, "APROBADO"):
        if re.match(r"(D\d+|00)_", h["name"]) or h["name"] == "02_Parametros":
            continue
        for i, fila in enumerate(h["rows"]):
            for j, v in enumerate(fila):
                if isinstance(v, (bool, dict)):
                    continue
                if (isinstance(v, (int, float)) and abs(v) > 1e-9) or (isinstance(v, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", v)):
                    fijos.append((h["name"], i + 5, h["cols"][j][0] if j < len(h["cols"]) else j, v))
    assert not fijos, fijos[:10]
