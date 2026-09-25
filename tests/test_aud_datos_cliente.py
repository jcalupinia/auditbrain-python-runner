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
REF = re.compile(r"^'(D\d+_[^']+)'!([A-Z]+)(\d+)$")


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
                    celda = datos[m.group(1)]["rows"][int(m.group(3)) - 5][column_index_from_string(m.group(2)) - 1]
                    assert b["v"] == a and datos_cliente._igual(a, celda), (h["name"], b["f"], a, celda)
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
