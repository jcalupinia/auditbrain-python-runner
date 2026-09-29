# -*- coding: utf-8 -*-
"""Papel de trabajo FORMULADO de «Efectivo y equivalentes» (formato Audit Consulting).

Construye un libro Excel con las cédulas del papel de bancos, con FÓRMULAS VIVAS
y auditables enlazadas entre pestañas (no valores pegados), a partir de datos
estructurados que en producción provienen del Libro Mayor subido + la tabla de
conciliación (partidas) transcrita del estado de cuenta / conciliación en PDF.

No incluye la cédula de «Procedimientos»: el programa de auditoría ya vive en el
flujo de la app. Las hojas son:

  DA-1 Sumaria · DA-2 Movimiento · DA-3 Conciliaciones Bancos (con Sobregiro/ajustes)
  DA-4 Partidas conciliatorias · DA-5 Arqueo de caja · DA-6 Hallazgos · Libro Mayor (fuente)

Contrato de entrada (dict), todo con datos revisados por el auditor::

    {
      "engagement": {"client","period","cutoff","preparer","reviewer"},
      "cuentas": [{"cuenta","descripcion","saldo_anterior","saldo_actual",
                   "ncuenta","extracto"}],
      "partidas": [{"fecha","banco","documento","beneficiario","valor",
                    "observacion", "categoria"?}],   # categoria opcional: se deduce
      "arqueo":   [{"denominacion","cantidad","valor_unitario"}],   # opcional
      "hallazgos":[{"observacion","criterio","efecto","ref","recomendacion"}],  # opcional
    }

`construir(papel) -> bytes` devuelve el .xlsx. Las categorías de partida que suman
las columnas conciliatorias de DA-3 (por SUMIFS) son las de `CATEGORIAS`.
"""
from __future__ import annotations

import datetime
import io
import unicodedata

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# Categorías conciliatorias (deben coincidir con los literales de los SUMIFS de DA-3).
CONSIGNACION = "Consignación no registrada"
SOBREGIRO = "Sobregiro/ajuste"
CHEQUE = "Cheque sin cobrar"
ND_TRANSITO = "Nota débito en tránsito"
NC_PENDIENTE = "NC pendiente contabilizar"
OTRA = "Otra partida"
CATEGORIAS = (CONSIGNACION, SOBREGIRO, CHEQUE, ND_TRANSITO, NC_PENDIENTE, OTRA)

_MONEY = "#,##0.00;[Red](#,##0.00)"
_DATE = "yyyy-mm-dd"
_NAVY = "FF1F3B5B"
_ACC = "FF2E7D32"
_LIGHT = "FFEDF1F7"


def _norm(s) -> str:
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().upper()


def _num(v) -> float:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def clasificar(documento, beneficiario="") -> str:
    """Deduce la categoría conciliatoria desde el texto del documento/beneficiario."""
    d = _norm(documento) + " " + _norm(beneficiario)
    if "SOBREGIRO" in d or "AJUSTE" in d:
        return SOBREGIRO
    if "CHEQUE" in d:
        return CHEQUE
    if "DEPOSITO" in d or "CONSIGNAC" in d:
        return CONSIGNACION
    if "NOTA DE DEBITO" in d:
        return ND_TRANSITO
    if "NOTA DE CREDITO" in d:
        return NC_PENDIENTE
    return OTRA


def _fecha(v):
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v if isinstance(v, datetime.date) else v.date()
    try:
        return datetime.date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


class _Estilo:
    def __init__(self):
        self.title = Font(bold=True, size=13, color=_NAVY)
        self.sub = Font(bold=True, size=11, color=_ACC)
        self.hdr = Font(bold=True, color="FFFFFFFF", size=10)
        self.hf = PatternFill("solid", fgColor=_NAVY)
        self.tot = Font(bold=True)
        self.it = Font(italic=True, color="FF666666", size=9)
        thin = Side(style="thin", color="FFBBBBBB")
        self.box = Border(left=thin, right=thin, top=thin, bottom=thin)
        self.center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        self.left = Alignment(horizontal="left", vertical="top", wrap_text=True)


def _encabezado(ws, st: _Estilo, ref: str, subtitulo: str, eng: dict):
    ws["B1"] = "EFECTIVO Y EQUIVALENTES DE EFECTIVO"
    ws["B1"].font = st.title
    ws["A3"] = subtitulo
    ws["A3"].font = st.sub
    ws["A4"] = "Cliente:"
    ws["B4"] = eng.get("client", "")
    ws["D4"] = "Período terminado:"
    ws["E4"] = eng.get("period", "")
    ws["A5"] = "Preparado por:"
    ws["B5"] = eng.get("preparer", "")
    ws["D5"] = "Revisado por:"
    ws["E5"] = eng.get("reviewer", "")
    ws["F4"] = "Ref. PT:"
    ws["G4"] = ref
    ws["G4"].font = st.tot
    for c in ("A4", "D4", "A5", "D5", "F4"):
        ws[c].font = st.it


def _tabla_encabezados(ws, st, fila, columnas):
    for c, t in enumerate(columnas, 1):
        cell = ws.cell(fila, c, t)
        cell.font = st.hdr
        cell.fill = st.hf
        cell.alignment = st.center
        cell.border = st.box


def construir(papel: dict) -> bytes:
    """Arma el papel de trabajo formulado y devuelve los bytes del .xlsx."""
    st = _Estilo()
    eng = papel.get("engagement") or {}
    cuentas = papel.get("cuentas") or []
    corte = _fecha(eng.get("cutoff")) or datetime.date.today()
    try:
        dias_presc = int(papel.get("dias_prescripcion") or 390)
    except (TypeError, ValueError):
        dias_presc = 390

    # Normaliza partidas: deduce categoría si no viene, y ata el banco al nombre de la cuenta.
    nombres = [c.get("descripcion", "") for c in cuentas]

    def banco_key(nombre):
        for n in nombres:
            base = _norm(n).replace("BANCO ", "")
            if base and base in _norm(nombre):
                return n
        return nombre

    partidas = []
    for p in papel.get("partidas") or []:
        cat = p.get("categoria") or clasificar(p.get("documento"), p.get("beneficiario"))
        partidas.append({
            "fecha": _fecha(p.get("fecha")),
            "banco": banco_key(p.get("banco")),
            "categoria": cat,
            "documento": p.get("documento") or "",
            "beneficiario": p.get("beneficiario") or "",
            "valor": _num(p.get("valor")),
            "observacion": p.get("observacion") or "",
        })

    wb = Workbook()
    wb.remove(wb.active)

    # ===== DA-1 Sumaria =====
    ws = wb.create_sheet("Sumaria")
    _encabezado(ws, st, "DA-1", "Sumaria", eng)
    r = 8
    _tabla_encabezados(ws, st, r, ["Cuenta", "Descripción", "Saldo año anterior",
                                   "Variación", "Saldo actual s/registros", "Ref."])
    first = r + 1
    for a in cuentas:
        r += 1
        ws.cell(r, 1, a.get("cuenta")).border = st.box
        ws.cell(r, 2, a.get("descripcion")).border = st.box
        ws.cell(r, 3, _num(a.get("saldo_anterior"))).border = st.box
        ws.cell(r, 3).number_format = _MONEY
        ws.cell(r, 4, f"=E{r}-C{r}").border = st.box            # Variación = actual - anterior
        ws.cell(r, 4).number_format = _MONEY
        ws.cell(r, 5, _num(a.get("saldo_actual"))).border = st.box
        ws.cell(r, 5).number_format = _MONEY
        ws.cell(r, 6, "DA-3").border = st.box
    last = r
    r += 1
    ws.cell(r, 2, "TOTAL EFECTIVO Y EQUIVALENTES").font = st.tot
    for col in (3, 4, 5):
        L = get_column_letter(col)
        cell = ws.cell(r, col, f"=SUM({L}{first}:{L}{last})")
        cell.font = st.tot
        cell.number_format = _MONEY
        cell.border = st.box
    for col, w in zip("ABCDEF", (12, 34, 20, 16, 22, 10)):
        ws.column_dimensions[col].width = w
    sum_row = {a.get("descripcion"): first + i for i, a in enumerate(cuentas)}

    # ===== DA-2 Movimiento =====
    ws = wb.create_sheet("Movimiento")
    _encabezado(ws, st, "DA-2", "Movimiento de bancos", eng)
    r = 8
    _tabla_encabezados(ws, st, r, ["Código", "Cuenta", "Saldo inicial", "Débitos del período",
                                   "Créditos del período", "Saldo final", "Cuadre s/Sumaria"])
    for a in cuentas:
        r += 1
        # Débitos/créditos del período: reales si vienen del Libro Mayor (RQ-009);
        # si no, se estiman del neto (saldo actual − anterior).
        if a.get("debitos") is not None or a.get("creditos") is not None:
            debitos, creditos = _num(a.get("debitos")), _num(a.get("creditos"))
        else:
            mov = _num(a.get("saldo_actual")) - _num(a.get("saldo_anterior"))
            debitos, creditos = max(mov, 0.0), -min(mov, 0.0)
        ws.cell(r, 1, a.get("cuenta")).border = st.box
        ws.cell(r, 2, a.get("descripcion")).border = st.box
        ws.cell(r, 3, _num(a.get("saldo_anterior"))).border = st.box
        ws.cell(r, 3).number_format = _MONEY
        ws.cell(r, 4, debitos).border = st.box
        ws.cell(r, 4).number_format = _MONEY
        ws.cell(r, 5, creditos).border = st.box
        ws.cell(r, 5).number_format = _MONEY
        ws.cell(r, 6, f"=C{r}+D{r}-E{r}").border = st.box       # saldo final = inicial + débitos - créditos
        ws.cell(r, 6).number_format = _MONEY
        ws.cell(r, 7, f"=F{r}-Sumaria!E{sum_row[a.get('descripcion')]}").border = st.box  # cuadre
        ws.cell(r, 7).number_format = _MONEY
    for col, w in zip("ABCDEFG", (12, 30, 18, 18, 18, 18, 18)):
        ws.column_dimensions[col].width = w

    # ===== DA-4 Partidas conciliatorias (antes de DA-3: DA-3 la referencia) =====
    ws = wb.create_sheet("Partidas conciliatorias")
    _encabezado(ws, st, "DA-4", "Partidas conciliatorias", eng)
    ws["A7"] = "Fecha de corte:"
    ws["A7"].font = st.it
    ws["B7"] = corte
    ws["B7"].number_format = _DATE
    r = 9
    _tabla_encabezados(ws, st, r, ["Fecha", "Banco", "Tipo conciliatorio", "Documento",
                                   "Beneficiario", "Valor", "Días vencidos",
                                   "Fecha prescripción", "Observación"])
    pfirst = r + 1
    for p in partidas:
        r += 1
        f = p["fecha"]
        ws.cell(r, 1, f or "").border = st.box
        if f:
            ws.cell(r, 1).number_format = _DATE
        ws.cell(r, 2, p["banco"]).border = st.box
        ws.cell(r, 3, p["categoria"]).border = st.box
        ws.cell(r, 4, p["documento"]).border = st.box
        ws.cell(r, 5, p["beneficiario"]).border = st.box
        ws.cell(r, 6, p["valor"]).border = st.box
        ws.cell(r, 6).number_format = _MONEY
        ws.cell(r, 7, f"=$B$7-A{r}").border = st.box            # días vencidos = corte - fecha
        ws.cell(r, 8, f"=A{r}+{dias_presc}").border = st.box    # prescripción = fecha + diasPrescripcion (def. 360 + 30)
        ws.cell(r, 8).number_format = _DATE
        ws.cell(r, 9, p["observacion"]).border = st.box
        ws.cell(r, 9).alignment = st.left
    plast = max(r, pfirst)   # rango válido aun sin partidas
    for col, w in zip("ABCDEFGHI", (12, 20, 22, 16, 30, 14, 13, 15, 40)):
        ws.column_dimensions[col].width = w

    # ===== DA-3 Conciliaciones Bancos (con Sobregiro/ajustes) =====
    ws = wb.create_sheet("Conciliaciones Bancos")
    _encabezado(ws, st, "DA-3", "Conciliaciones bancarias", eng)
    r = 8
    _tabla_encabezados(ws, st, r, [
        "Banco", "N° cuenta", "Saldo extracto", "(+) Consig. no registradas",
        "(−) Sobregiro/ajustes", "(−) Cheques sin cobrar", "(−) ND en tránsito",
        "(−) NC pendiente", "Saldo s/auditoría", "Saldo s/registros", "Diferencia"])
    pb = f"'Partidas conciliatorias'!$B${pfirst}:$B${plast}"
    pt = f"'Partidas conciliatorias'!$C${pfirst}:$C${plast}"
    pv = f"'Partidas conciliatorias'!$F${pfirst}:$F${plast}"
    ext = {c.get("descripcion"): c for c in cuentas}
    cfirst = r + 1
    for a in cuentas:
        r += 1
        b = a.get("descripcion")
        ws.cell(r, 1, b).border = st.box
        ws.cell(r, 2, a.get("ncuenta")).border = st.box
        ws.cell(r, 3, _num(a.get("extracto"))).border = st.box
        ws.cell(r, 3).number_format = _MONEY
        ws.cell(r, 4, f'=SUMIFS({pv},{pb},A{r},{pt},"{CONSIGNACION}")').border = st.box
        ws.cell(r, 5, f'=SUMIFS({pv},{pb},A{r},{pt},"{SOBREGIRO}")').border = st.box
        ws.cell(r, 6, f'=SUMIFS({pv},{pb},A{r},{pt},"{CHEQUE}")').border = st.box
        ws.cell(r, 7, f'=SUMIFS({pv},{pb},A{r},{pt},"{ND_TRANSITO}")').border = st.box
        ws.cell(r, 8, f'=SUMIFS({pv},{pb},A{r},{pt},"{NC_PENDIENTE}")').border = st.box
        for col in (4, 5, 6, 7, 8):
            ws.cell(r, col).number_format = _MONEY
        # Saldo s/auditoría = extracto + consignaciones - sobregiro - cheques - ND - NC
        ws.cell(r, 9, f"=C{r}+D{r}-E{r}-F{r}-G{r}-H{r}").border = st.box
        ws.cell(r, 9).number_format = _MONEY
        ws.cell(r, 10, f"=Sumaria!E{sum_row[b]}").border = st.box
        ws.cell(r, 10).number_format = _MONEY
        ws.cell(r, 11, f"=I{r}-J{r}").border = st.box          # diferencia = s/auditoría - s/registros
        ws.cell(r, 11).number_format = _MONEY
    clast = r
    r += 1
    ws.cell(r, 1, "TOTAL").font = st.tot
    for col in (3, 9, 10, 11):
        L = get_column_letter(col)
        cell = ws.cell(r, col, f"=SUM({L}{cfirst}:{L}{clast})")
        cell.font = st.tot
        cell.number_format = _MONEY
        cell.border = st.box
    for col, w in zip("ABCDEFGHIJK", (20, 16, 15, 18, 16, 16, 15, 15, 16, 16, 13)):
        ws.column_dimensions[col].width = w

    # ===== DA-5 Arqueo de caja =====
    ws = wb.create_sheet("Arqueo Caja")
    _encabezado(ws, st, "DA-5", "Arqueo de caja", eng)
    r = 8
    _tabla_encabezados(ws, st, r, ["Denominación", "Cantidad", "Valor unitario", "Total"])
    arqueo = papel.get("arqueo") or [
        {"denominacion": f"Billete/moneda {d}", "cantidad": 0, "valor_unitario": d}
        for d in (100, 50, 20, 10, 5, 1, 0.5, 0.25, 0.10, 0.05, 0.01)
    ]
    afirst = r + 1
    for it in arqueo:
        r += 1
        ws.cell(r, 1, it.get("denominacion")).border = st.box
        ws.cell(r, 2, _num(it.get("cantidad"))).border = st.box
        ws.cell(r, 3, _num(it.get("valor_unitario"))).border = st.box
        ws.cell(r, 3).number_format = _MONEY
        ws.cell(r, 4, f"=B{r}*C{r}").border = st.box
        ws.cell(r, 4).number_format = _MONEY
    alast = r
    r += 1
    ws.cell(r, 1, "TOTAL ARQUEO").font = st.tot
    tcell = ws.cell(r, 4, f"=SUM(D{afirst}:D{alast})")
    tcell.font = st.tot
    tcell.number_format = _MONEY
    tcell.border = st.box
    ws.cell(r + 1, 1, "Saldo s/registros caja")
    ws.cell(r + 1, 4, 0).number_format = _MONEY
    ws.cell(r + 2, 1, "Diferencia").font = st.tot
    dcell = ws.cell(r + 2, 4, f"=D{r}-D{r + 1}")
    dcell.font = st.tot
    dcell.number_format = _MONEY
    for col, w in zip("ABCD", (24, 12, 16, 16)):
        ws.column_dimensions[col].width = w

    # ===== DA-6 Hallazgos =====
    ws = wb.create_sheet("Hallazgos")
    _encabezado(ws, st, "DA-6", "Hoja de hallazgos", eng)
    r = 8
    _tabla_encabezados(ws, st, r, ["N°", "Observación (condición)", "Criterio",
                                   "Efecto", "Ref. PT", "Recomendación"])
    hallazgos = papel.get("hallazgos") or []
    for i, h in enumerate(hallazgos, 1):
        r += 1
        for c, v in enumerate([i, h.get("observacion"), h.get("criterio"),
                               h.get("efecto"), h.get("ref"), h.get("recomendacion")], 1):
            cell = ws.cell(r, c, v)
            cell.border = st.box
            cell.alignment = st.left
    for col, w in zip("ABCDEF", (6, 40, 26, 26, 10, 40)):
        ws.column_dimensions[col].width = w

    # ===== Libro Mayor (fuente) =====
    ws = wb.create_sheet("Libro Mayor")
    ws["A1"] = "LIBRO MAYOR (fuente subida)"
    ws["A1"].font = st.title
    _tabla_encabezados(ws, st, 3, ["Cuenta", "Descripción", "Año", "Mes", "Fecha",
                                   "Comprobante", "Detalle", "Tercero", "Débitos", "Créditos"])
    for i, fila in enumerate(papel.get("libro_mayor") or [], 4):
        for c, v in enumerate(fila, 1):
            ws.cell(i, c, v)
    for col, w in zip("ABCDEFGHIJ", (12, 26, 8, 6, 12, 14, 34, 24, 14, 14)):
        ws.column_dimensions[col].width = w

    for hoja in wb.worksheets:
        hoja.sheet_view.showGridLines = False
        if hoja.title != "Libro Mayor":
            hoja.freeze_panes = "A9"
    wb.calculation.fullCalcOnLoad = True

    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()
