"""Papel de trabajo EJECUTIVO (Excel) — identidad SIGMANSERVICE, panel de inicio,
navegación, semáforo y bitácora en español, con las fórmulas intactas.

El verificador celda a celda contra Excel real (scripts/verificar_formulas_pi.py)
usa win32com (solo Windows); aquí se prueba, sin Excel, que cada fórmula de la
definición de la cédula se escribe EXACTA en su celda (layout intacto) y que el
libro abre sin «reparar».
"""
import io

from openpyxl import load_workbook

from backend.app.aud.niif.procesadores import estilo_ejecutivo as est
from backend.app.aud.niif.procesadores import libro
from backend.app.aud.niif.procesadores import PROCESADORES
from backend.app.aud.niif.ciclo import reglas


def _reg(pid):
    mod = PROCESADORES[pid]
    d = mod.definicion()
    esc = getattr(mod, "ESCENARIOS", None)
    if esc:
        _, datasets, param, corte = esc[0]
    else:
        E = mod.EJEMPLO
        datasets, param, corte = E["datasets"], E.get("parametros", {}), E["corte"]
    run = mod.ejecutar(datasets, param, corte)
    run["hojas"] = mod.hojas(run)
    reg = {"run": run, "engagement": {"client": "Cliente de muestra S.A.", "ruc": "1790000000001",
           "cutoff": corte, "framework": (param.get("_marco") or d["frameworks"][0]),
           "firm": "AuditConsulting Auditores Cía. Ltda.", "preparer": "AA", "reviewer": "BB"},
           "program": [{**x, "reference": x.get("source", "")} for x in d["program"]], "sources": []}
    return d, mod, reg


def test_excel_ejecutivo_panel_navegacion_y_formatos():
    d, mod, reg = _reg("perdidas_incurridas_s11")
    eventos = [{"fecha": "2026-01-15T10:00:00", "accion": "create", "estado_anterior": None,
                "estado_nuevo": "PRUEBA_SELECCIONADA", "actor": "aa@x", "comentario": ""},
               {"fecha": "2026-01-15T11:00:00", "accion": "execute", "estado_anterior": "METODOLOGIA_APROBADA",
                "estado_nuevo": "PRUEBA_EJECUTADA", "actor": "aa@x", "comentario": ""}]
    wb = load_workbook(io.BytesIO(libro.xlsx(d, mod, reg, eventos, 1, "APROBADO") if False else libro.xlsx(d, reg, eventos, 1, "APROBADO")))
    assert wb.sheetnames[0] == "00_Inicio"
    ini = wb["00_Inicio"]
    assert ini.sheet_view.showGridLines is False
    # navegación por hipervínculo interno a cada cédula
    destinos = [c.hyperlink.target for row in ini.iter_rows() for c in row if c.hyperlink]
    assert len(destinos) >= 10 and all(t.startswith("#'") for t in destinos)
    # impresión horizontal, ajustar a ancho
    detalle = wb[wb.sheetnames[1]]
    assert detalle.page_setup.orientation == "landscape" and detalle.page_setup.fitToWidth == 1
    # bitácora en español, sin códigos crudos
    ctrl = wb[next(n for n in wb.sheetnames if "Control" in n)]
    vals = [c.value for row in ctrl.iter_rows() for c in row]
    assert "Prueba creada" in vals and "Prueba ejecutada" in vals
    assert "PRUEBA_EJECUTADA" not in vals


def test_formulas_intactas_en_su_celda():
    d, mod, reg = _reg("perdidas_incurridas_s11")
    hojas = libro.cedulas(d, reg, [], 1, "APROBADO")
    titulos = libro._titulos_unicos(hojas)
    wb = load_workbook(io.BytesIO(libro.xlsx(d, reg, [], 1, "APROBADO")))
    total = comprobadas = 0
    for h, t in zip(hojas, titulos):
        ws = wb[t]
        filas = h["rows"] + ([h["total"]] if h.get("total") else [])
        for i, fila in enumerate(filas):
            for j, v in enumerate(fila):
                if isinstance(v, dict) and "f" in v:
                    total += 1
                    if ws.cell(row=5 + i, column=1 + j).value == "=" + v["f"]:
                        comprobadas += 1
    assert total > 0 and comprobadas == total


def test_todas_las_herramientas_generan_excel_que_abre_sin_reparar():
    for pid, mod in PROCESADORES.items():
        if not getattr(mod, "RUBRO", None):
            continue
        d, _, reg = _reg(pid)
        wb = load_workbook(io.BytesIO(libro.xlsx(d, reg, [], 1, "APROBADO")))  # abre sin reparar
        assert wb.sheetnames[0] == "00_Inicio", pid


def test_como_se_calcula_una_fila_por_columna_con_formula():
    d, mod, reg = _reg("perdidas_incurridas_s11")
    hojas = libro.cedulas(d, reg, [], 1, "APROBADO")
    detalle = next(h for h in hojas if "Detalle" in h["name"])
    bloque = libro.como_se_calcula(detalle)
    # Hay una fila por CADA columna con fórmula, y ninguna por las columnas de datos.
    cols_con_formula = [c[0] for j, c in enumerate(detalle["cols"])
                        if detalle["rows"] and isinstance(detalle["rows"][0][j], dict) and "f" in detalle["rows"][0][j]]
    assert [b["columna"] for b in bloque] == cols_con_formula
    for b in bloque:
        assert b["formula"].startswith("=") and b["explicacion"] and b["ejemplo"] and b["origen"]


def test_como_se_calcula_ejemplo_coincide_con_el_valor_de_la_fila_1():
    d, mod, reg = _reg("perdidas_incurridas_s11")
    hojas = libro.cedulas(d, reg, [], 1, "APROBADO")
    for h in hojas:
        cols = [c[0] for c in h["cols"]]
        for b in libro.como_se_calcula(h):
            j = cols.index(b["columna"])
            v0 = h["rows"][0][j]
            esperado = libro._fmt_num(libro._valor(v0), h["cols"][j][1])
            assert b["ejemplo"].rstrip().endswith(esperado), (h["name"], b["columna"], b["ejemplo"], esperado)


def test_bloque_como_se_calcula_no_rompe_ninguna_herramienta():
    for pid, mod in PROCESADORES.items():
        if not getattr(mod, "RUBRO", None):
            continue
        d, _, reg = _reg(pid)
        wb = load_workbook(io.BytesIO(libro.xlsx(d, reg, [], 1, "APROBADO")))  # abre sin reparar con el bloque
        assert wb.sheetnames[0] == "00_Inicio", pid


def test_todos_los_formatos_se_generan_en_las_18():
    import zipfile

    for pid, mod in PROCESADORES.items():
        if not getattr(mod, "RUBRO", None):
            continue
        d, _, reg = _reg(pid)
        docx = libro.docx(d, reg, [], 1, "APROBADO")
        pptx = libro.pptx(d, reg, [], 1, "APROBADO")
        html = libro.html(d, reg, [], 1, "APROBADO")
        czip = libro.csv_zip(d, reg, [], 1, "APROBADO")
        assert docx[:2] == b"PK" and pptx[:2] == b"PK", pid
        assert html.startswith(b"<!doctype html") and b"http://" not in html, pid  # HTML sin conexión
        z = zipfile.ZipFile(io.BytesIO(czip))
        assert z.namelist() and all(n.endswith(".csv") for n in z.namelist()), pid
        assert z.read(z.namelist()[0]).startswith("﻿".encode("utf-8")), pid  # UTF-8 con BOM


def test_html_trae_kpis_pestanas_y_ver_calculo():
    d, mod, reg = _reg("perdidas_incurridas_s11")
    html = libro.html(d, reg, [], 1, "APROBADO").decode("utf-8")
    assert 'class="kpi"' in html and 'class="tab' in html and "Ver cálculo" in html
    assert "CSV (ZIP)" in html and "Guardar como PDF" in html


def test_pdf_ejecutivo_se_genera_en_el_servidor():
    d, mod, reg = _reg("perdidas_incurridas_s11")
    pdf = libro.pdf(d, reg, [], 1, "APROBADO")
    assert pdf[:5] == b"%PDF-" and len(pdf) > 5000
    # El HTML estático del PDF trae el bloque «Cómo se calcula» visible y sin JS/descargas.
    est_html = libro.html(d, reg, [], 1, "APROBADO", para_pdf=True).decode("utf-8")
    assert "<script>" not in est_html and 'class="descargas"' not in est_html
    assert "Cómo se calcula esta hoja" in est_html


def test_tokens_y_etiquetas_cubren_el_vocabulario():
    for e in reglas.ESTADOS:
        assert est.estado_es(e) != e, e  # todos traducidos
    for a in ("create", "execute", "approve_program", "approve"):
        assert est.accion_es(a)
    assert est.color_semaforo(0) == est.GREEN
    assert est.color_semaforo(2) == est.AMBER
    assert est.color_semaforo(9) == est.RED
