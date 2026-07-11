# backend/app/client_portal/flujo/generador.py
"""Generador del Excel de la Herramienta Flujo de Efectivo.

Corre los 8 motores (homologación, ESF, ERI, flujo, patrimonio, F-101,
indicadores, no-efectivo) sobre dos balanzas (año anterior / año actual) y
produce un ``.xlsx`` (openpyxl) con 9 hojas presentadas profesionalmente
(bordes, fuentes Calibri, formato numérico, identidad visual AUDIT-IA).

El archivo es un papel de trabajo auditable: los valores son numéricos ya
calculados (no fórmulas vivas), pero la hoja ``Homologación`` deja el rastro
de cada saldo y la hoja ``RESUMEN`` muestra las cuadraturas de forma explícita.
"""
from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from . import (
    catalogos,
    motor,
    motor_er,
    motor_f101,
    motor_flujo,
    motor_indicadores,
    motor_no_efectivo,
    motor_patrimonio,
)

# ----------------------------------------------------------------------------
# Identidad visual (CLAUDE.md): Gold #C7A83C / Navy #0A2342.
# ----------------------------------------------------------------------------
GOLD = "C7A83C"
NAVY = "0A2342"
AZUL_CLARO = "DCE6F1"   # fondo filas TOTAL
VERDE = "C6EFCE"        # semáforo cuadra
VERDE_TXT = "006100"
ROJO = "FFC7CE"         # semáforo no cuadra
ROJO_TXT = "9C0006"
BLANCO = "FFFFFF"
GRIS = "6B7280"

NUM_FMT = "#,##0.00"

_thin = Side(style="thin", color="BFBFBF")
_double = Side(style="double", color="000000")
BORDE_THIN = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
BORDE_TOTAL = Border(left=_thin, right=_thin, top=_double, bottom=_double)

FONT_DATA = Font(name="Calibri", size=9)
FONT_TOTAL = Font(name="Calibri", size=10, bold=True)
FONT_BLOQUE = Font(name="Calibri", size=11, bold=True)
FONT_HEADER = Font(name="Calibri", size=10, bold=True, color=BLANCO)
FONT_TITULO = Font(name="Calibri", size=16, bold=True, color=NAVY)
FONT_MARCA = Font(name="Calibri", size=9, italic=True, color=GRIS)

FILL_HEADER = PatternFill("solid", fgColor=NAVY)
FILL_TOTAL = PatternFill("solid", fgColor=AZUL_CLARO)
FILL_GOLD = PatternFill("solid", fgColor=GOLD)

AL_IZQ = Alignment(horizontal="left", vertical="center", wrap_text=False)
AL_DER = Alignment(horizontal="right", vertical="center")
AL_CEN = Alignment(horizontal="center", vertical="center")

MARCA = "AuditConsulting Auditores Cía. Ltda."
PLATAFORMA = "AUDIT-IA"


# ----------------------------------------------------------------------------
# Helpers de escritura segura
# ----------------------------------------------------------------------------
def _safe_text(v) -> str:
    """Evita que Excel interprete un texto como fórmula (cuadro "Reparaciones").

    Antepone un apóstrofo lógico prefijando con espacio de ancho cero NO — mejor:
    si el texto empieza con =, +, - o @, se prefija un apóstrofo real que
    openpyxl trata como texto literal sin mostrarlo. Para máxima compatibilidad
    simplemente anteponemos un espacio fino solo cuando haga falta.
    """
    s = "" if v is None else str(v)
    if s[:1] in ("=", "+", "-", "@"):
        return "'" + s
    return s


def _celda_texto(ws: Worksheet, row: int, col: int, valor, *, font=FONT_DATA,
                 al=AL_IZQ, fill=None, borde=BORDE_THIN):
    c = ws.cell(row=row, column=col, value=_safe_text(valor))
    c.font = font
    c.alignment = al
    c.border = borde
    if fill is not None:
        c.fill = fill
    return c


def _celda_num(ws: Worksheet, row: int, col: int, valor, *, font=FONT_DATA,
               fill=None, borde=BORDE_THIN):
    try:
        num = round(float(valor), 2)
    except (TypeError, ValueError):
        num = 0.0
    c = ws.cell(row=row, column=col, value=num)
    c.number_format = NUM_FMT
    c.font = font
    c.alignment = AL_DER
    c.border = borde
    if fill is not None:
        c.fill = fill
    return c


def _encabezados(ws: Worksheet, row: int, titulos: list[str], anchos: list[int]):
    for i, (t, w) in enumerate(zip(titulos, anchos), start=1):
        c = ws.cell(row=row, column=i, value=_safe_text(t))
        c.font = FONT_HEADER
        c.fill = FILL_HEADER
        c.alignment = AL_CEN
        c.border = BORDE_THIN
        ws.column_dimensions[get_column_letter(i)].width = w


def _bloque(ws: Worksheet, row: int, texto: str, ncols: int):
    c = ws.cell(row=row, column=1, value=_safe_text(texto))
    c.font = FONT_BLOQUE
    c.alignment = AL_IZQ
    for i in range(1, ncols + 1):
        ws.cell(row=row, column=i).fill = FILL_GOLD


def _titulo_hoja(ws: Worksheet, titulo: str, ncols: int) -> int:
    """Escribe el título + marca en las primeras filas. Devuelve la fila
    donde empezar a escribir el contenido."""
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(ncols, 2))
    t = ws.cell(row=1, column=1, value=_safe_text(titulo))
    t.font = FONT_TITULO
    t.alignment = AL_IZQ
    m = ws.cell(row=2, column=1, value=_safe_text(f"{MARCA} · {PLATAFORMA}"))
    m.font = FONT_MARCA
    m.alignment = AL_IZQ
    return 4


# ----------------------------------------------------------------------------
# Hojas
# ----------------------------------------------------------------------------
def _hoja_resumen(wb: Workbook, ctx: dict):
    ws = wb.create_sheet("RESUMEN")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 42
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 18

    tt = ws.cell(row=2, column=2, value=_safe_text("Estado de Flujo de Efectivo"))
    tt.font = FONT_TITULO
    st = ws.cell(row=3, column=2, value=_safe_text("Papel de trabajo · Método indirecto"))
    st.font = Font(name="Calibri", size=11, color=GOLD, bold=True)
    mk = ws.cell(row=4, column=2, value=_safe_text(f"{MARCA} · {PLATAFORMA}"))
    mk.font = FONT_MARCA

    # Semáforos de cuadratura
    _encabezados_resumen(ws, 6)
    fila = 7
    cuad_esf = ctx["cuadre_esf"]
    cuad_af = ctx["flujo"]
    filas_sem = [
        ("Cuadre ESF (Activo = Pasivo + Patrimonio)", cuad_esf["diferencia"],
         cuad_esf["cuadra"], "Diferencia debe ser 0.00"),
        ("Cuadre Flujo de Efectivo (AF)", cuad_af["cuadre_af"],
         cuad_af["cuadra"], "Efectivo final calc. − real"),
    ]
    for nombre, dif, cuadra, nota in filas_sem:
        _celda_texto(ws, fila, 2, nombre, font=FONT_DATA)
        _celda_num(ws, fila, 3, dif)
        estado = ws.cell(row=fila, column=4,
                         value=_safe_text("CUADRA" if cuadra else "NO CUADRA"))
        estado.font = Font(name="Calibri", size=9, bold=True,
                           color=VERDE_TXT if cuadra else ROJO_TXT)
        estado.fill = PatternFill("solid", fgColor=VERDE if cuadra else ROJO)
        estado.alignment = AL_CEN
        estado.border = BORDE_THIN
        _celda_texto(ws, fila, 2, nombre)
        ws.cell(row=fila, column=2).border = BORDE_THIN
        ws.cell(row=fila, column=3).border = BORDE_THIN
        # nota
        n = ws.cell(row=fila, column=5, value=_safe_text(nota))
        n.font = FONT_MARCA
        fila += 1

    # Utilidad neta (informativa, no semáforo)
    _celda_texto(ws, fila, 2, "Utilidad neta del ejercicio")
    _celda_num(ws, fila, 3, ctx["cascada"]["utilidad_neta"])
    ws.cell(row=fila, column=4, value="").border = BORDE_THIN
    fila += 1
    _celda_texto(ws, fila, 2, "Resultado integral del ejercicio")
    _celda_num(ws, fila, 3, ctx["cascada"]["resultado_integral"])
    ws.cell(row=fila, column=4, value="").border = BORDE_THIN
    fila += 2

    # Nota al pie
    pie = ws.cell(row=fila + 1, column=2,
                  value=_safe_text("Semáforo verde = cuadra (diferencia ≤ 1.00). "
                                   "Rojo = requiere revisión del auditor."))
    pie.font = FONT_MARCA


def _encabezados_resumen(ws: Worksheet, row: int):
    for col, t in ((2, "Verificación"), (3, "Diferencia"), (4, "Estado")):
        c = ws.cell(row=row, column=col, value=_safe_text(t))
        c.font = FONT_HEADER
        c.fill = FILL_HEADER
        c.alignment = AL_CEN
        c.border = BORDE_THIN


def _hoja_homologacion(wb: Workbook, ctx: dict):
    ws = wb.create_sheet("Homologación")
    ws.sheet_view.showGridLines = False
    inicio = _titulo_hoja(ws, "Homologación — rastro de auditoría", 4)
    titulos = ["Cuenta", "Cód. Super Cías", "Cód. SRI", "Saldo"]
    anchos = [46, 18, 14, 18]

    fila = inicio
    for etiqueta, balanza in (("AÑO ANTERIOR", ctx["bal_ant"]),
                              ("AÑO ACTUAL", ctx["bal_act"])):
        _bloque(ws, fila, etiqueta, 4)
        fila += 1
        _encabezados(ws, fila, titulos, anchos)
        fila += 1
        total = 0.0
        for f in balanza:
            _celda_texto(ws, fila, 1, f.get("cuenta", ""))
            _celda_texto(ws, fila, 2, f.get("super_cias", ""), al=AL_CEN)
            _celda_texto(ws, fila, 3, f.get("sri", ""), al=AL_CEN)
            _celda_num(ws, fila, 4, f.get("saldo", 0.0))
            total += float(f.get("saldo", 0.0) or 0.0)
            fila += 1
        _celda_texto(ws, fila, 1, "TOTAL (control ≈ 0)", font=FONT_TOTAL,
                     fill=FILL_TOTAL, borde=BORDE_TOTAL)
        for col in (2, 3):
            _celda_texto(ws, fila, col, "", fill=FILL_TOTAL, borde=BORDE_TOTAL)
        _celda_num(ws, fila, 4, total, font=FONT_TOTAL, fill=FILL_TOTAL,
                   borde=BORDE_TOTAL)
        fila += 2


def _hoja_estructura(wb: Workbook, nombre: str, titulo: str, estructura,
                     tot_ant: dict, tot_act: dict, subtotales: list | None = None):
    ws = wb.create_sheet(nombre)
    ws.sheet_view.showGridLines = False
    inicio = _titulo_hoja(ws, titulo, 5)
    titulos = ["Código", "Etiqueta", "Saldo Anterior", "Saldo Actual", "Variación"]
    anchos = [16, 50, 18, 18, 16]
    _encabezados(ws, inicio, titulos, anchos)
    fila = inicio + 1
    for n in estructura:
        ant = round(float(tot_ant.get(n.codigo, 0.0)), 2)
        act = round(float(tot_act.get(n.codigo, 0.0)), 2)
        es_seccion = len(n.codigo) <= 1
        font = FONT_TOTAL if es_seccion else FONT_DATA
        fill = FILL_TOTAL if es_seccion else None
        _celda_texto(ws, fila, 1, n.codigo, al=AL_CEN, font=font, fill=fill)
        _celda_texto(ws, fila, 2, n.etiqueta, font=font, fill=fill)
        _celda_num(ws, fila, 3, ant, font=font, fill=fill)
        _celda_num(ws, fila, 4, act, font=font, fill=fill)
        _celda_num(ws, fila, 5, round(act - ant, 2), font=font, fill=fill)
        fila += 1

    if subtotales:
        fila += 1
        _bloque(ws, fila, "SUBTOTALES DE LA CASCADA (año actual)", 5)
        fila += 1
        for etiqueta, valor in subtotales:
            _celda_texto(ws, fila, 1, "", font=FONT_TOTAL, fill=FILL_TOTAL,
                         borde=BORDE_TOTAL)
            _celda_texto(ws, fila, 2, etiqueta, font=FONT_TOTAL, fill=FILL_TOTAL,
                         borde=BORDE_TOTAL)
            _celda_texto(ws, fila, 3, "", font=FONT_TOTAL, fill=FILL_TOTAL,
                         borde=BORDE_TOTAL)
            _celda_num(ws, fila, 4, valor, font=FONT_TOTAL, fill=FILL_TOTAL,
                       borde=BORDE_TOTAL)
            _celda_texto(ws, fila, 5, "", font=FONT_TOTAL, fill=FILL_TOTAL,
                         borde=BORDE_TOTAL)
            fila += 1


def _hoja_flujo(wb: Workbook, ctx: dict):
    ws = wb.create_sheet("Flujo de Efectivo")
    ws.sheet_view.showGridLines = False
    inicio = _titulo_hoja(ws, "Estado de Flujo de Efectivo — método indirecto", 2)
    _encabezados(ws, inicio, ["Concepto", "Valor"], [46, 20])
    fila = inicio + 1
    f = ctx["flujo"]
    filas = [
        ("Flujo de actividades de OPERACIÓN", f["operacion"], False),
        ("Flujo de actividades de INVERSIÓN", f["inversion"], False),
        ("Flujo de actividades de FINANCIAMIENTO", f["financiamiento"], False),
        ("Incremento neto de efectivo", f["incremento_neto"], True),
        ("Efectivo al inicio del período", f["efectivo_inicial"], False),
        ("Efectivo al final (calculado)", f["efectivo_final_calculado"], True),
        ("Efectivo al final (real balance)", f["efectivo_final_real"], False),
        ("AF — cuadre (calc. − real, debe ser 0.00)", f["cuadre_af"], True),
    ]
    for etiqueta, valor, total in filas:
        font = FONT_TOTAL if total else FONT_DATA
        fill = FILL_TOTAL if total else None
        borde = BORDE_TOTAL if total else BORDE_THIN
        _celda_texto(ws, fila, 1, etiqueta, font=font, fill=fill, borde=borde)
        _celda_num(ws, fila, 2, valor, font=font, fill=fill, borde=borde)
        fila += 1


def _hoja_patrimonio(wb: Workbook, ctx: dict):
    ws = wb.create_sheet("Evolución del Patrimonio")
    ws.sheet_view.showGridLines = False
    inicio = _titulo_hoja(ws, "Estado de Evolución del Patrimonio", 5)
    _encabezados(ws, inicio,
                 ["Código", "Componente", "Saldo Inicial", "Variación", "Saldo Final"],
                 [12, 40, 18, 16, 18])
    fila = inicio + 1
    evo = ctx["patrimonio"]
    orden = ["capital", "aportes_socios", "prima_emision", "reservas",
             "otros_resultados_integrales", "resultados_acumulados",
             "resultado_ejercicio"]
    etiquetas = {
        "capital": "Capital",
        "aportes_socios": "Aportes de socios para futura capitalización",
        "prima_emision": "Prima por emisión de acciones",
        "reservas": "Reservas",
        "otros_resultados_integrales": "Otros resultados integrales",
        "resultados_acumulados": "Resultados acumulados",
        "resultado_ejercicio": "Resultado del ejercicio",
    }
    for k in orden:
        comp = evo[k]
        _celda_texto(ws, fila, 1, comp["codigo"], al=AL_CEN)
        _celda_texto(ws, fila, 2, etiquetas[k])
        _celda_num(ws, fila, 3, comp["saldo_inicial"])
        _celda_num(ws, fila, 4, comp["variacion"])
        _celda_num(ws, fila, 5, comp["saldo_final"])
        fila += 1
    tot = evo["total_patrimonio"]
    _celda_texto(ws, fila, 1, tot["codigo"], al=AL_CEN, font=FONT_TOTAL,
                 fill=FILL_TOTAL, borde=BORDE_TOTAL)
    _celda_texto(ws, fila, 2, "TOTAL PATRIMONIO", font=FONT_TOTAL,
                 fill=FILL_TOTAL, borde=BORDE_TOTAL)
    _celda_num(ws, fila, 3, tot["saldo_inicial"], font=FONT_TOTAL,
               fill=FILL_TOTAL, borde=BORDE_TOTAL)
    _celda_num(ws, fila, 4, tot["variacion"], font=FONT_TOTAL, fill=FILL_TOTAL,
               borde=BORDE_TOTAL)
    _celda_num(ws, fila, 5, tot["saldo_final"], font=FONT_TOTAL, fill=FILL_TOTAL,
               borde=BORDE_TOTAL)


def _hoja_no_efectivo(wb: Workbook, ctx: dict):
    ws = wb.create_sheet("Movimiento no Efectivo")
    ws.sheet_view.showGridLines = False
    inicio = _titulo_hoja(ws, "Movimientos que no son efectivo (add-backs)", 2)
    ne = ctx["no_efectivo"]
    _encabezados(ws, inicio, ["Categoría", "Monto"], [40, 20])
    fila = inicio + 1
    for cat in motor_no_efectivo.CATEGORIAS:
        _celda_texto(ws, fila, 1, cat)
        _celda_num(ws, fila, 2, ne.get(cat, 0.0))
        fila += 1
    # otras categorías fuera del set canónico
    for k, v in ne.items():
        if k in motor_no_efectivo.CATEGORIAS or k in ("total", "detalle"):
            continue
        _celda_texto(ws, fila, 1, str(k))
        _celda_num(ws, fila, 2, v)
        fila += 1
    _celda_texto(ws, fila, 1, "TOTAL no efectivo", font=FONT_TOTAL,
                 fill=FILL_TOTAL, borde=BORDE_TOTAL)
    _celda_num(ws, fila, 2, ne.get("total", 0.0), font=FONT_TOTAL,
               fill=FILL_TOTAL, borde=BORDE_TOTAL)
    fila += 2

    detalle = ne.get("detalle", {})
    if detalle:
        _bloque(ws, fila, "DETALLE POR CÓDIGO ERI", 2)
        fila += 1
        _encabezados(ws, fila, ["Código ERI", "Monto"], [40, 20])
        fila += 1
        for cod in sorted(detalle):
            _celda_texto(ws, fila, 1, cod, al=AL_CEN)
            _celda_num(ws, fila, 2, detalle[cod])
            fila += 1


def _hoja_f101(wb: Workbook, ctx: dict):
    ws = wb.create_sheet("Formulario 101")
    ws.sheet_view.showGridLines = False
    inicio = _titulo_hoja(ws, "Formulario 101 — casilleros (año actual)", 2)
    _encabezados(ws, inicio, ["Casillero", "Valor"], [18, 22])
    fila = inicio + 1
    cas = ctx["f101"]
    for cod in sorted(cas, key=lambda c: int(c) if str(c).isdigit() else 0):
        valor = cas[cod]
        if round(float(valor), 2) == 0.0:
            continue
        _celda_texto(ws, fila, 1, str(cod), al=AL_CEN)
        _celda_num(ws, fila, 2, valor)
        fila += 1


def _hoja_indicadores(wb: Workbook, ctx: dict):
    ws = wb.create_sheet("Indicadores")
    ws.sheet_view.showGridLines = False
    inicio = _titulo_hoja(ws, "Indicadores financieros", 2)
    _encabezados(ws, inicio, ["Indicador", "Valor"], [42, 22])
    fila = inicio + 1
    ind = ctx["indicadores"]
    etiquetas = {
        "activo_total": ("Activo total", False),
        "activo_corriente": ("Activo corriente", False),
        "pasivo_total": ("Pasivo total", False),
        "pasivo_corriente": ("Pasivo corriente", False),
        "patrimonio": ("Patrimonio", False),
        "capital_trabajo": ("Capital de trabajo", False),
        "razon_corriente": ("Razón corriente", True),
        "endeudamiento_total": ("Endeudamiento total", True),
        "apalancamiento": ("Apalancamiento", True),
        "margen_neto": ("Margen neto", True),
        "roa": ("ROA", True),
        "roe": ("ROE", True),
    }
    for clave, (nombre, es_ratio) in etiquetas.items():
        _celda_texto(ws, fila, 1, nombre)
        c = ws.cell(row=fila, column=2, value=round(float(ind.get(clave, 0.0)), 4))
        c.number_format = "0.0000" if es_ratio else NUM_FMT
        c.font = FONT_DATA
        c.alignment = AL_DER
        c.border = BORDE_THIN
        fila += 1


# ----------------------------------------------------------------------------
# API pública
# ----------------------------------------------------------------------------
def generar_excel(balanza_anterior: list[dict], balanza_actual: list[dict]) -> bytes:
    """Corre los 8 motores y devuelve los bytes de un ``.xlsx`` con 9 hojas.

    Args:
        balanza_anterior: filas ``{"cuenta","super_cias","sri","saldo"}`` del
            año anterior (salida de ``parser.parse_balanza``).
        balanza_actual: idem para el año actual.

    Returns:
        Los bytes del libro Excel (openpyxl), listo para escribir a disco o
        enviar al cliente.
    """
    # --- Catálogos (se cargan una vez) ---
    est_esf = catalogos.cargar_estructura("esf")
    est_eri = catalogos.cargar_estructura("eri")
    clasificacion = catalogos.cargar_clasificacion_flujo()
    agregados = catalogos.cargar_agregados_f101()
    cat_no_efectivo = catalogos.cargar_no_efectivo()

    # --- Homologación (SUMIF por Super Cías) ---
    saldos_ant, _sin_ant = motor.homologar_balanza(balanza_anterior)
    saldos_act, _sin_act = motor.homologar_balanza(balanza_actual)

    # --- Totales por código con rollup ---
    tot_esf_ant = motor.totales_por_codigo(est_esf, saldos_ant)
    tot_esf_act = motor.totales_por_codigo(est_esf, saldos_act)
    tot_eri_ant = motor.totales_por_codigo(est_eri, saldos_ant)
    tot_eri_act = motor.totales_por_codigo(est_eri, saldos_act)

    # --- Motores ---
    cuadre_esf = motor.cuadre(tot_esf_act)
    flujo = motor_flujo.flujo_efectivo(tot_esf_ant, tot_esf_act, clasificacion)
    cascada = motor_er.cascada_resultados(tot_eri_act)
    patrimonio = motor_patrimonio.evolucion(tot_esf_ant, tot_esf_act)
    no_efectivo = motor_no_efectivo.gastos_no_efectivo(tot_eri_act, cat_no_efectivo)
    ori885 = motor_f101.ori_del_periodo(balanza_anterior, balanza_actual)
    f101 = motor_f101.casilleros_completos(balanza_actual, agregados,
                                           extras={"885": ori885})
    # motor_indicadores usa la clave interna "_ingresos_totales" para el margen
    eri_para_ind = dict(cascada)
    eri_para_ind["_ingresos_totales"] = round(
        cascada["ingresos_ordinarios"] + cascada["otros_ingresos"], 2)
    indicadores = motor_indicadores.indicadores(tot_esf_act, eri_para_ind)

    ctx = {
        "bal_ant": balanza_anterior,
        "bal_act": balanza_actual,
        "cuadre_esf": cuadre_esf,
        "flujo": flujo,
        "cascada": cascada,
        "patrimonio": patrimonio,
        "no_efectivo": no_efectivo,
        "f101": f101,
        "indicadores": indicadores,
    }

    # --- Construcción del libro (orden de hojas exigido) ---
    wb = Workbook()
    wb.remove(wb.active)  # elimina la hoja por defecto

    _hoja_resumen(wb, ctx)
    _hoja_homologacion(wb, ctx)
    _hoja_estructura(wb, "ESF", "Estado de Situación Financiera", est_esf,
                     tot_esf_ant, tot_esf_act)
    subtotales_eri = [
        ("Ganancia bruta", cascada["ganancia_bruta"]),
        ("Utilidad operativa", cascada["utilidad_operativa"]),
        ("Utilidad antes de impuestos", cascada["utilidad_antes_ir"]),
        ("Utilidad neta", cascada["utilidad_neta"]),
        ("Resultado integral", cascada["resultado_integral"]),
    ]
    _hoja_estructura(wb, "ERI", "Estado de Resultados Integral", est_eri,
                     tot_eri_ant, tot_eri_act, subtotales=subtotales_eri)
    _hoja_flujo(wb, ctx)
    _hoja_patrimonio(wb, ctx)
    _hoja_no_efectivo(wb, ctx)
    _hoja_f101(wb, ctx)
    _hoja_indicadores(wb, ctx)

    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()
