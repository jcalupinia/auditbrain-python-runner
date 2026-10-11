# -*- coding: utf-8 -*-
from backend.app.aud.niif.procesadores.nomina import rutas as _R
"""Modelo de archivo RQ-004 Mayores de Nómina (pasivos y gastos)."""
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

OUT = (_R.CTX.out + '/RQ-004_Mayores_Nomina.xlsx')
NAVY = PatternFill('solid', fgColor='FF0F2341'); SUB = PatternFill('solid', fgColor='FFDDE6F3'); BAND = PatternFill('solid', fgColor='FF0B1F3A')
AR = Font(name='Arial', size=10); ARB = Font(name='Arial', size=10, bold=True)
WH = Font(name='Arial', size=10, bold=True, color='FFFFFFFF'); BLUE = Font(name='Arial', size=10, color='FF0000FF')
GREEN = Font(name='Arial', size=10, color='FF008000'); GRAY = Font(name='Arial', size=9, italic=True, color='FF808080')
IT = Font(name='Arial', size=9, italic=True)
thin = Side(style='thin', color='FFBFBFBF'); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
N2 = '#,##0.00;(#,##0.00);"-"'
C = Alignment(horizontal='center', vertical='center', wrap_text=True)
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

def th(ws, row, col0, labels, h=32):
    for i, t in enumerate(labels):
        c = ws.cell(row, col0 + i, t); c.font = WH; c.fill = NAVY; c.alignment = C; c.border = BOX
    ws.row_dimensions[row].height = h

def band(ws, title, ncol):
    for j in range(1, ncol + 1): ws.cell(1, j).fill = BAND
    ws.row_dimensions[1].height = 28
    c = ws.cell(1, 2, title); c.font = Font(name='Arial', size=12, bold=True, color='FFFFFFFF')

# --- catálogo: anexo RQ-002 + cuentas del papel no incluidas en el anexo
anexo = {}
for r in load_workbook(_R.CTX.anexo, data_only=True).active.iter_rows(min_row=4, values_only=True):
    if r[0]: anexo[str(r[0]).strip()] = (str(r[1]).strip(), r[5])
from backend.app.aud.niif.procesadores.nomina import mayores as MY
_vistas = set(); papel = []
for _k in MY.GKEY:
    for _c, _n, _ in MY.cuentas_por_concepto(_k):
        if _c not in _vistas:
            _vistas.add(_c); papel.append((_c, _n))

def concepto(nombre):
    n = nombre.lower()
    for key, cod in [('tercer', 'D13'), ('cuarto', 'D14'), ('vacacion', 'VAC'), ('fondos', 'FR'), ('pasantes', 'PAS' if 'aporte' in n else 'EST'),
                     ('aporte patronal', 'APO'), ('aporte individual', 'AIN'), ('quirograf', 'PQU'), ('hipotec', 'PHI'), ('sueldos por pagar', 'SXP'),
                     ('liquid', 'LIQ'), ('sueldo', 'SUE'), ('horas extras', 'HE'), ('bono', 'BON'), ('comision', 'COM'), ('premio', 'PRE')]:
        if key in n: return cod
    return 'OTR'
USO = {'D13': 'DO-4C, DO-5, DO-6, DO-7', 'D14': 'DO-4C, DO-5, DO-6, DO-7', 'VAC': 'DO-4C, DO-5, DO-6, DO-7', 'FR': 'DO-6, DO-7, DO-9',
       'APO': 'DO-6, DO-7, DO-9', 'PAS': 'DO-6, DO-7', 'EST': 'DO-8', 'SUE': 'DO-8, DO-10', 'HE': 'DO-8, DO-10', 'BON': 'DO-8, DO-10',
       'COM': 'DO-8, DO-10', 'PRE': 'DO-8, DO-10', 'AIN': 'DO-9', 'PQU': 'DO-9', 'PHI': 'DO-9', 'SXP': 'DO-9', 'LIQ': 'DO-4C, DO-10', 'OTR': '—'}
cat = {}
for cod, (nom, sal) in anexo.items():
    if cod.startswith('5BS.212') or cod in dict(papel): cat[cod] = (nom, sal, 'RQ-002')
for cod, nom in papel:
    if cod not in cat: cat[cod] = (nom, None, 'No está en RQ-002')
pasivos = sorted([k for k in cat if k.startswith('5BS')]); gastos = [c for c, _ in papel if not c.startswith('5BS')]
seen = set(); gastos = [c for c in gastos if not (c in seen or seen.add(c))]

wb = Workbook()
# --- Instrucciones
wi = wb.active; wi.title = 'Instrucciones'; band(wi, 'RQ-004 · MAYORES DE NÓMINA (PASIVOS Y GASTOS) — modelo de carga', 8)
lines = [('Para qué sirve', ARB),
         ('Alimenta los valores en libros de las cédulas DO-4C, DO-5, DO-6, DO-7, DO-8, DO-9 y DO-10, que hoy usan valores provisionales del papel del equipo.', AR),
         ('', AR), ('Cómo llenarlo', ARB),
         ('1. «Mayor pasivos»: copie el mayor contable del año de las cuentas 5BS.21203 y 5BS.21204 (una fila por asiento). '
          'La columna «Tipo de movimiento» es opcional para el cliente: el auditor la completa (provisión, pago, finiquito, goce, ajuste).', AR),
         ('2. «Mayor gastos»: registre el saldo de cada mes por cuenta de gasto y centro de costo. Las cuentas ya vienen precargadas; '
          'agregue al final las que falten.', AR),
         ('3. «Catálogo»: relaciona cada cuenta con su concepto (D13, D14, VAC, FR, APO…) y con las cédulas que la consumen. No requiere edición salvo cuentas nuevas.', AR),
         ('', AR), ('Controles automáticos', ARB),
         ('• Mayor gastos: el total anual de cada cuenta se compara con el saldo del Anexo RQ-002; las diferencias se marcan.', AR),
         ('• Mayor pasivos: el saldo final por cuenta (saldo inicial + créditos − débitos) se compara con el Anexo RQ-002.', AR),
         ('', AR), ('Celdas en azul: datos del cliente. Celdas en verde: vínculos y controles. Formato aceptado: .xlsx o .csv con las mismas columnas.', IT)]
for i, (t, f) in enumerate(lines):
    c = wi.cell(3 + i, 2, t); c.font = f; c.alignment = Alignment(wrap_text=True, vertical='top')
    wi.merge_cells(start_row=3 + i, start_column=2, end_row=3 + i, end_column=8)
    if f is AR and t: wi.row_dimensions[3 + i].height = 30
wi.column_dimensions['A'].width = 2
for col in 'BCDEFGH': wi.column_dimensions[col].width = 16

# --- Catálogo
wc = wb.create_sheet('Catálogo'); band(wc, 'CATÁLOGO DE CUENTAS DE NÓMINA', 7)
th(wc, 3, 2, ['Cuenta', 'Nombre', 'Concepto', 'Cédulas que la usan', 'Saldo RQ-002 al 31-dic-2025', 'Origen del saldo'])
order = pasivos + gastos
for i, cod in enumerate(order):
    r = 4 + i; nom, sal, ori = cat[cod]; cp = concepto(nom)
    for j, v in enumerate([cod, nom, cp, USO[cp], (abs(sal) if isinstance(sal, (int, float)) else None), ori]):
        c = wc.cell(r, 2 + j, v); c.font = AR; c.border = BOX
    wc.cell(r, 6).number_format = N2
    if ori != 'RQ-002': wc.cell(r, 7).font = Font(name='Arial', size=10, color='FFC65911')
CAT_LAST = 3 + len(order)
for col, w in zip('ABCDEFG', [2, 18, 34, 10, 26, 18, 20]): wc.column_dimensions[col].width = w
wc.freeze_panes = 'C4'; wc.auto_filter.ref = f'B3:G{CAT_LAST}'
CATR = lambda col: f'Catálogo!${col}$4:${col}${CAT_LAST}'

# --- Mayor pasivos
wp = wb.create_sheet('Mayor pasivos'); band(wp, 'MAYOR DE PASIVOS (5BS.21203 / 5BS.21204) — una fila por asiento', 10)
th(wp, 3, 2, ['Cuenta', 'Nombre cuenta', 'Fecha', 'Nº asiento', 'Concepto / glosa', 'Débito', 'Crédito', 'Tipo de movimiento (auditor)', 'Concepto'])
dv = DataValidation(type='list', formula1='"Saldo inicial,Provisión,Pago,Finiquito / liquidación,Goce de vacaciones,Ajuste,Reclasificación"', allow_blank=True)
wp.add_data_validation(dv)
ex = ['5BS.21204.003', 'Vacaciones', '2025-01-31', 'CD-0001', '[ejemplo] Provisión de vacaciones enero', 0, 10078.58, 'Provisión']
for j, v in enumerate(ex): c = wp.cell(4, 2 + j, v); c.font = GRAY; c.border = BOX
for r in range(4, 3004):
    for j in range(2, 10):
        c = wp.cell(r, j); c.border = BOX
        if r > 4: c.font = BLUE
    wp.cell(r, 7).number_format = N2; wp.cell(r, 8).number_format = N2
    wp.cell(r, 10, f'=IF(B{r}="","",IFERROR(INDEX({CATR("D")},MATCH(B{r},{CATR("B")},0)),"Sin catálogo"))').font = GREEN
dv.add('I5:I3003')
for col, w in zip('ABCDEFGHIJ', [2, 16, 26, 12, 12, 40, 14, 14, 24, 12]): wp.column_dimensions[col].width = w
wp.freeze_panes = 'B4'
# control de saldos
wp['L3'] = 'Control de saldos por cuenta'; wp['L3'].font = ARB
th(wp, 4, 12, ['Cuenta', 'Saldo inicial', 'Créditos', 'Débitos', 'Saldo final', 'RQ-002', 'Diferencia'], 22)
for i, cod in enumerate(pasivos):
    r = 5 + i
    wp.cell(r, 12, cod).font = AR
    wp.cell(r, 13, f'=SUMIFS($H$5:$H$3003,$B$5:$B$3003,L{r},$I$5:$I$3003,"Saldo inicial")-SUMIFS($G$5:$G$3003,$B$5:$B$3003,L{r},$I$5:$I$3003,"Saldo inicial")')
    wp.cell(r, 14, f'=SUMIFS($H$5:$H$3003,$B$5:$B$3003,L{r},$I$5:$I$3003,"<>Saldo inicial")')
    wp.cell(r, 15, f'=SUMIFS($G$5:$G$3003,$B$5:$B$3003,L{r},$I$5:$I$3003,"<>Saldo inicial")')
    wp.cell(r, 16, f'=M{r}+N{r}-O{r}')
    wp.cell(r, 17, f'=IFERROR(INDEX({CATR("F")},MATCH(L{r},{CATR("B")},0)),0)')
    wp.cell(r, 18, f'=ROUND(P{r}-Q{r},2)')
    for j in range(13, 19): wp.cell(r, j).number_format = N2; wp.cell(r, j).font = GREEN; wp.cell(r, j).border = BOX
    wp.cell(r, 12).border = BOX
for col in 'LMNOPQR': wp.column_dimensions[col].width = 15

# --- Mayor gastos
wg = wb.create_sheet('Mayor gastos'); band(wg, 'MAYOR DE GASTOS — saldo mensual por cuenta y centro de costo', 20)
th(wg, 3, 2, ['Cuenta', 'Nombre', 'Concepto'] + MESES + ['Total anual', 'RQ-002', 'Diferencia'])
for i, cod in enumerate(gastos + [None] * 15):
    r = 4 + i
    if cod:
        wg.cell(r, 2, cod).font = AR; wg.cell(r, 3, cat[cod][0]).font = AR
    else:
        wg.cell(r, 2).font = BLUE; wg.cell(r, 3).font = BLUE
    wg.cell(r, 4, f'=IF(B{r}="","",IFERROR(INDEX({CATR("D")},MATCH(B{r},{CATR("B")},0)),"Sin catálogo"))').font = GREEN
    for m in range(12):
        c = wg.cell(r, 5 + m); c.font = BLUE; c.number_format = N2
    wg.cell(r, 17, f'=IF(B{r}="","",SUM(E{r}:P{r}))').font = ARB
    wg.cell(r, 18, f'=IF(B{r}="","",IFERROR(INDEX({CATR("F")},MATCH(B{r},{CATR("B")},0)),""))').font = GREEN
    wg.cell(r, 19, f'=IF(OR(B{r}="",R{r}=""),"",ROUND(Q{r}-R{r},2))').font = GREEN
    for j in range(2, 20):
        wg.cell(r, j).border = BOX
        if j >= 17: wg.cell(r, j).number_format = N2
last = 3 + len(gastos) + 15
wg.cell(last + 2, 2, 'Total por concepto').font = ARB
for k, cp in enumerate(['SUE', 'HE', 'BON', 'COM', 'PRE', 'EST', 'D13', 'D14', 'VAC', 'FR', 'APO', 'PAS']):
    r = last + 3 + k
    wg.cell(r, 2, cp).font = AR
    for m in range(12):
        colL = chr(69 + m)
        c = wg.cell(r, 5 + m, f'=SUMIFS({colL}$4:{colL}${last},$D$4:$D${last},$B{r})'); c.font = GREEN; c.number_format = N2
    c = wg.cell(r, 17, f'=SUM(E{r}:P{r})'); c.font = ARB; c.number_format = N2
wg.cell(last + 16, 2, 'Este resumen por concepto es el que leen las cédulas DO-5 a DO-8 en lugar de los valores provisionales.').font = IT
for col, w in zip(['A', 'B', 'C', 'D'], [2, 18, 30, 10]): wg.column_dimensions[col].width = w
for j in range(5, 20): wg.column_dimensions[chr(64 + j)].width = 12
wg.freeze_panes = 'E4'
wb.save(OUT)
print('ok', OUT, 'pasivos', len(pasivos), 'gastos', len(gastos), 'sin RQ-002', sum(1 for c in order if cat[c][2] != 'RQ-002'))
