"""HTML ejecutivo premium de las 20 herramientas NIIF (PR de ajustes).

1) «Cómo se calcula»: cada columna calculada trae una explicación HUMANA escrita en
   la definición de la cédula; falla si alguna coincide con la plantilla genérica.
2) «Ejemplo con números reales» de la primera fila con fórmula.
3/4) Cifras visibles en formato es-EC (punto de miles, coma decimal).
5) Ejercicio modelo con el ejemplo realista del manifiesto (6 clientes) en HTML,
   Excel, Word y PowerPoint — no el EJEMPLO mínimo.
6) Dashboard: temas, selectores, KPIs, gráficos SVG propios, sin CDN; PDF sin JS.
"""
import importlib.util
import io
import os
import re
import zipfile

import pytest

from backend.app.aud.niif import ejercicio_modelo as em
from backend.app.aud.niif.procesadores import PROCESADORES, base, graficos, graficos_svg, html_ejecutivo, libro

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("verificar_explicaciones",
                                               os.path.join(RAIZ, "scripts", "verificar_explicaciones.py"))
verificar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verificar)

EN_US = re.compile(r"\b\d{1,3}(?:,\d{3})+\.\d{2}\b")  # 1,234.56


def _reg(pid):
    mod = PROCESADORES[pid]
    d = mod.definicion()
    ds, par, corte = em.escenario(mod)
    return d, mod, em._reg(d, mod, ds, par, corte)


def _texto_visible(h: str) -> str:
    h = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)
    return re.sub(r"<[^>]+>", " ", h)  # solo nodos de texto (no coordenadas SVG)


@pytest.mark.parametrize("pid", list(PROCESADORES))
def test_explicaciones_humanas_en_todas_las_columnas(pid):
    pendientes = verificar.revisar(pid)
    assert not pendientes, f"{pid}:\n" + "\n".join(pendientes)


def test_sin_explicacion_cae_en_plantilla_generica_y_el_verificador_la_detecta():
    h = base.hoja("99_X", "Prueba", [("A", "n"), ("B", "n")],
                  [[1, {"f": "=A5*2", "v": 2}]])
    b = libro.como_se_calcula(h)[0]
    assert not b["escrita"] and libro.PLANTILLA_GENERICA in b["explicacion"]
    h2 = base.hoja("99_X", "Prueba", [("A", "n"), ("B", "n")],
                   [[1, {"f": "=A5*2", "v": 2}]], explica={"B": "Duplica el valor de la columna A de la misma fila."})
    b2 = libro.como_se_calcula(h2)[0]
    assert b2["escrita"] and libro.PLANTILLA_GENERICA not in b2["explicacion"]
    # Ejemplo con números reales, en es-EC
    assert b2["ejemplo"].startswith("Fila 1:") and "→" in b2["ejemplo"]


def test_ejemplo_traduce_rangos_y_columnas_completas_con_numeros():
    d, _, reg = _reg("perdidas_incurridas_s11")
    hojas = libro.cedulas(d, reg, [], 1, "APROBADO")
    ejemplos = [b["ejemplo"] for h in hojas for b in libro.como_se_calcula(h, hojas)]
    assert ejemplos and all(e.startswith("Fila ") and "→" in e for e in ejemplos)
    # Una referencia a columna completa ('Hoja'!$F:$F) se traduce a palabras.
    ev = base.hoja("03_X", "Evidencia", [["Tramo", "t"], ["Vivo", "n"]], [["A", 10.0]])
    mt = base.hoja("04_M", "Matriz", [["Tramo", "t"], ["Tasa", "n"]],
                   [["A", {"f": "SUMIF('03_X'!$A:$A,A5,'03_X'!$B:$B)", "v": 10.0}]], explica={"Tasa": "Suma lo vivo."})
    assert "columna completa" in libro.como_se_calcula(mt, [ev, mt])[0]["ejemplo"]
    # Sin direcciones de celda sin traducir (el texto entre comillas, como las claves de cruce, no cuenta).
    sin_textos = lambda e: re.sub(r'«[^»]*»|"[^"]*"', "", e.split("→")[0].split(":", 1)[1])  # noqa: E731
    assert not any(re.search(r"\$?[A-Z]{1,3}\$?\d+", sin_textos(e)) for e in ejemplos
                   if "!" not in e), "quedan referencias de celda sin traducir a números"


@pytest.mark.parametrize("pid", list(PROCESADORES))
def test_panel_resuelve_kpis_y_graficos(pid):
    mod = PROCESADORES[pid]
    ds, par, corte = em.escenario(mod)
    run = mod.ejecutar(ds, par, corte)
    p = graficos.panel(mod, run, mod.hojas(run))
    assert not p["faltan"], (pid, p["faltan"])


@pytest.mark.parametrize("pid", list(PROCESADORES))
def test_html_premium_autonomo_es_ec_y_con_selectores(pid):
    d, _, reg = _reg(pid)
    h = libro.html(d, reg, [], 1, "APROBADO").decode("utf-8")
    # Sin conexión: nada externo
    assert "http://" not in h and "https://" not in h and "<link" not in h and "@import" not in h, pid
    # Selectores de color, gráfico y vista con todas sus opciones
    for sel, opciones in (("t", html_ejecutivo.TEMAS), ("g", html_ejecutivo.GRAFICOS), ("v", html_ejecutivo.VISTAS)):
        assert f'id="sel-{sel}"' in h, pid
        for o in opciones:
            assert f'value="{o}"' in h, (pid, sel, o)
    # KPIs, pestañas, gráficos SVG propios y «Guardar como PDF»
    assert h.count('class="kpi ') >= 4 and 'class="tab' in h and 'class="graficos"' in h, pid
    assert h.count('<svg class="grafico"') >= 2 and "Guardar como PDF" in h, pid
    # Cifras visibles en es-EC
    visibles = _texto_visible(h)
    assert not EN_US.findall(visibles), (pid, EN_US.findall(visibles)[:5])


def test_html_para_pdf_estatico_en_tema_claro():
    d, _, reg = _reg("perdidas_incurridas_s11")
    h = libro.html(d, reg, [], 1, "APROBADO", para_pdf=True).decode("utf-8")
    assert "<script" not in h and "var(--" not in h.split("<body", 1)[1].split("<style", 1)[0]
    assert "t-claro" in h and 'id="sel-t"' not in h


def test_formato_es_ec_de_las_cifras():
    assert graficos_svg.es_ec(178259.63) == "178.259,63"
    assert graficos_svg.es_ec(0) == "0,00"
    assert graficos_svg.es_ec(-150).endswith("150,00") and graficos_svg.es_ec(-150)[0] in "-−"
    assert graficos_svg.corto(14932.98) == "14,9 mil"
    assert graficos_svg.corto(1500000) == "1,50 M"
    assert graficos_svg.corto(-240000) == "−240 mil" and graficos_svg.corto(99_960) == "100 mil"
    assert graficos_svg.pct(0.386) == "38,6 %"


def test_dona_y_barras_3d():
    items = [("A", 60.0), ("B", 30.0), ("C", 10.0)]
    dona = graficos_svg.dona(items, "Composición")
    assert dona.count("<path") == 3 and "60,0 %" in dona
    barras = graficos_svg.columnas(items, "barras", ["s1", "s2", "s3"], "Comparativo")
    assert barras.count("<polygon") >= 6  # cara superior y lateral de cada barra (relieve)


def test_ejercicio_modelo_usa_el_ejemplo_realista_del_manifiesto_en_todos_los_formatos():
    d, _, reg = _reg("perdidas_incurridas_s11")
    clientes = ("Vialidad Norte", "Minera Austral", "Agroexport del Litoral")
    for fn in ("xlsx", "docx", "pptx"):
        z = zipfile.ZipFile(io.BytesIO(getattr(libro, fn)(d, reg, [], 1, "APROBADO")))
        xml = "".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))
        assert all(c in xml for c in clientes), fn
        assert "Cliente A" not in xml, fn
    h = libro.html(d, reg, [], 1, "APROBADO").decode("utf-8")
    assert "Vialidad Norte" in h and "Cliente A" not in _texto_visible(h)
    ds, _, _ = em.escenario(PROCESADORES["perdidas_incurridas_s11"])
    assert len({r["cliente"] for filas in ds.values() for r in filas if r.get("cliente")}) == 6
