# -*- coding: utf-8 -*-
from backend.app.aud.niif.procesadores.nomina import rutas as _R
"""DO-6 Cruce Global del Gasto de Beneficios + DO-7 Cruce Mensual del Gasto.
Formato: papel «DO - Pasivos Acumulados.xlsx» (DO6 Cruce Gsto Benefi. / DO7 Cruce Mens Gasto Beneficios).
Libros: valores del papel (provisional hasta los mayores RQ-004). Auditoría: DO-4 v3 + Consolidado IESS + rol DO-3.1."""
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.drawing.image import Image as XLImage

OUT = (_R.CTX.out + '/DO-6_DO-7_Cruce_Gasto_Beneficios.xlsx')
SRC = _R.CTX.papel
g = pd.read_pickle((_R.CTX.home + '/g2.pkl'))
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

NAVY = PatternFill('solid', fgColor='FF0F2341'); SUB = PatternFill('solid', fgColor='FFDDE6F3'); YEL = PatternFill('solid', fgColor='FFFFF2CC')
AR = Font(name='Arial', size=10); ARB = Font(name='Arial', size=10, bold=True)
WH = Font(name='Arial', size=10, bold=True, color='FFFFFFFF'); WH12 = Font(name='Arial', size=12, bold=True, color='FFFFFFFF')
BLUE = Font(name='Arial', size=10, color='FF0000FF'); GREEN = Font(name='Arial', size=10, color='FF008000')
RED = Font(name='Arial', size=10, bold=True, color='FFC00000'); RU = Font(name='Arial', size=10, bold=True, color='FFC00000', underline='single')
IT = Font(name='Arial', size=8, italic=True)
thin = Side(style='thin', color='FF000000'); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
N2 = '#,##0.00;(#,##0.00);"-"'; PC = '0.0%;(0.0%);"-"'
C = Alignment(horizontal='center', vertical='center', wrap_text=True)

def cell(ws, ref, v, font=AR, fmt=None, fill=None, al=None, box=False):
    c = ws[ref]; c.value = v; c.font = font
    if fmt: c.number_format = fmt
    if fill: c.fill = fill
    if al: c.alignment = al
    if box: c.border = BOX
    return c

def header(ws, titulo, ref_pt, last_col):
    for r in range(1, 4):
        for col in range(2, last_col + 1): ws.cell(r, col).fill = NAVY
    ws.row_dimensions[1].height = 34; ws.row_dimensions[2].height = 22
    img = XLImage(_R.CTX.logo); img.height = 60; img.width = 160; ws.add_image(img, 'B1')
    mid = chr(64 + (2 + last_col) // 2 + 1)
    cell(ws, f'{mid}1', 'OBLIGACIONES ACUMULADAS', WH12); cell(ws, f'{mid}3', titulo, WH)
    cell(ws, 'B4', 'Nombre del cliente:', ARB, box=True); cell(ws, 'C4', '=Ficha!C4', AR, box=True)
    cell(ws, 'F4', 'Período terminado:', ARB, box=True); cell(ws, 'G4', '=Ficha!C5', AR, 'dd/mm/yyyy', box=True)
    cell(ws, 'B5', 'Preparado por:', ARB, box=True); cell(ws, 'C5', '=Ficha!C6', AR, box=True)
    cell(ws, 'D5', 'Revisado:', ARB, box=True); cell(ws, 'E5', '=Ficha!C7', AR, box=True)
    cell(ws, 'F5', 'Fecha:', ARB, box=True); cell(ws, 'G5', '=Ficha!C8', AR, 'dd/mm/yyyy', box=True)
    cell(ws, f'{chr(64 + last_col - 1)}5', 'Referencia de PT', ARB, box=True); cell(ws, f'{chr(64 + last_col)}5', ref_pt, RED, box=True)

def th(ws, row, col0, labels, height=30):
    for i, t in enumerate(labels):
        c = ws.cell(row, col0 + i, t); c.font = WH; c.fill = NAVY; c.alignment = C; c.border = BOX
    ws.row_dimensions[row].height = height

def texts(ws, items, last):
    for r, t, f in items:
        cell(ws, f'B{r}', t, f)
        if f is AR:
            ws.merge_cells(f'B{r}:{last}{r}'); ws[f'B{r}'].alignment = Alignment(wrap_text=True, vertical='top'); ws.row_dimensions[r].height = 28

# --------------------------- datos del papel de trabajo (libros)
src = load_workbook(SRC, data_only=True)
ANEXO = {str(r[0]).strip(): abs(r[5]) for r in load_workbook(_R.CTX.anexo, data_only=True).active.iter_rows(min_row=4, values_only=True) if r[0] and isinstance(r[5], (int, float))}
ORANGE = Font(name='Arial', size=10, color='FFC65911')
s6 = src['DO6 Cruce Gsto Benefi.']; s7 = src['DO7 Cruce Mens Gasto Beneficios']
GROUPS = [('D13', 'Décimo tercer sueldo', 10, 31), ('D14', 'Décimo cuarto sueldo', 33, 51), ('APO', 'Aporte patronal', 53, 74),
          ('FR', 'Fondos de reserva', 77, 99), ('VAC', 'Vacaciones', 102, 124), ('PAS', 'Aporte patronal pasantes', 126, 132)]
accounts = {k: [(s6.cell(r, 2).value, str(s6.cell(r, 3).value).strip(), float(s6.cell(r, 4).value or 0))
                for r in range(a, b + 1) if s6.cell(r, 2).value] for k, _, a, b in GROUPS}
mon_rows = {'APO': ('B', 9), 'PAS': ('I', 9), 'D13': ('B', 26), 'D14': ('B', 43), 'FR': ('B', 62), 'VAC': ('B', 80)}

from backend.app.aud.niif.procesadores.nomina import mayores as MY
monthly = {k: MY.gasto_mes(k) for k in mon_rows}
accounts = {k: [(cod, cta, MY.gasto_cta(str(cod).strip())) for cod, cta, _ in v] for k, v in accounts.items()}


def banner(ws, last_col, texto):
    ORANGE = Font(name='Arial', size=9, bold=True, color='FFC00000')
    ws.merge_cells(start_row=6, start_column=2, end_row=6, end_column=last_col)
    c = ws.cell(6, 2, texto); c.font = ORANGE; c.fill = PatternFill('solid', fgColor='FFFFF2CC')
    c.alignment = Alignment(wrap_text=True, vertical='center'); ws.row_dimensions[6].height = 26

wb = Workbook()
# --------------------------- Ficha
wf = wb.active; wf.title = 'Ficha'
cell(wf, 'B2', 'FICHA DEL ENCARGO (encabezado de las cédulas)', ARB)
for i, (k, v) in enumerate([('Cliente', _R.CTX.cliente), ('Período terminado', pd.Timestamp(_R.CTX.corte).to_pydatetime()),
                            ('Preparado por', _R.CTX.preparado), ('Revisado por', _R.CTX.revisado), ('Fecha', '=TODAY()')]):
    cell(wf, f'B{4+i}', k, ARB, box=True); c = cell(wf, f'C{4+i}', v, BLUE if i < 4 else AR, box=True)
    if i in (1, 4): c.number_format = 'dd/mm/yyyy'
wf.column_dimensions['B'].width = 22; wf.column_dimensions['C'].width = 30

# --------------------------- Libros mensuales
wl = wb.create_sheet('Libros mensuales')
cell(wl, 'B2', 'GASTO MENSUAL SEGÚN LIBROS — Mayor de gastos RQ-004', ARB)
cell(wl, 'B3', 'Fuente: Mayor de gastos RQ-004 (LM_GASTO), suma mensual por concepto de todas las cuentas y centros de costo, incluidas las cuentas MQLA de diciembre.', Font(name='Arial', size=9, bold=True, color='FF1F3864'))
LCOL = {'APO': 'C', 'PAS': 'D', 'D13': 'E', 'D14': 'F', 'FR': 'G', 'VAC': 'H'}
th(wl, 5, 2, ['Mes', 'Aporte patronal', 'Aporte pasantes', 'Décimo tercero', 'Décimo cuarto', 'Fondos de reserva', 'Vacaciones'])
for m in range(12):
    r = 6 + m; cell(wl, f'B{r}', MESES[m], AR, box=True)
    for k, col in LCOL.items(): cell(wl, f'{col}{r}', monthly[k][m], BLUE, N2, box=True)
cell(wl, 'B18', 'Σ', RED, box=True)
for col in 'CDEFGH': cell(wl, f'{col}18', f'=SUM({col}6:{col}17)', ARB, N2, box=True)
for col, w in zip('ABCDEFGH', [2, 14, 16, 16, 16, 16, 18, 16]): wl.column_dimensions[col].width = w

# --------------------------- Insumo auditoría
wi = wb.create_sheet('Insumo Auditoría')
cell(wi, 'B2', 'GASTO DEVENGADO SEGÚN AUDITORÍA POR MES — DO-4 Reproceso v3 (con exclusiones), Consolidado IESS y rol DO-3.1', ARB)
ICOL = {'APO': ('C', 'pat_emp'), 'PAS': ('D', 'pas_aporte'), 'D13': ('E', 'd13b'), 'D14': ('F', 'd14b'), 'FR': ('G', 'Fondos de reserva'),
        'VAC': ('H', 'Vacaciones'), 'FRX': ('I', 'FR excluido'), 'FRR': ('J', 'FR pagado en rol'), 'FRI': ('K', 'FR a depositar IESS')}
th(wi, 4, 2, ['Mes', 'Aporte patronal + CCC (empleados)', 'Aporte pasantes (IESS)', 'D13 devengado', 'D14 devengado (Sierra)',
              'FR devengado', 'Vacaciones devengadas', 'FR excluido (auditor)', 'FR pagado en rol', 'FR depositado IESS'], 44)
for m in range(1, 13):
    r = 4 + m; cell(wi, f'B{r}', MESES[m - 1], AR, box=True)
    for k, (col, s) in ICOL.items(): cell(wi, f'{col}{r}', float(g.loc[float(m), s]), GREEN, N2, box=True)
cell(wi, 'B17', 'Σ', RED, box=True)
for col in 'CDEFGHIJK': cell(wi, f'{col}17', f'=SUM({col}5:{col}16)', ARB, N2, box=True)
for k, t in enumerate(['Fuente (verde = vínculo a otro papel de trabajo):',
                       '• Aporte patronal: Consolidado IESS (RQ-003), patronal + CCC de trabajadores del rol «normal» (sin pasantes).',
                       '• Aporte pasantes: Consolidado IESS, registros de pasantes (fuera del rol).',
                       '• D13 = base/12; D14 = SBU 470/360 × días; vacaciones = base/24; FR = 8,33% desde el mes 13. Todos sin exclusiones del auditor.',
                       '• FR excluido: representantes legales (RQ-003 Exclusiones). FR pagado en rol y depositado en IESS: rol DO-3.1 / DO-4.']):
    cell(wi, f'B{19+k}', t, IT)
wi.column_dimensions['A'].width = 2; wi.column_dimensions['B'].width = 14
for col in 'CDEFGHIJK': wi.column_dimensions[col].width = 16
wi.freeze_panes = 'C5'
IA = "'Insumo Auditoría'"

# --------------------------- DO-6 Cruce global del gasto
w6 = wb.create_sheet('DO6 Cruce Global Gasto', 0)
header(w6, 'Beneficios sociales gasto — Cruce global', 'DO-6', 8)
banner(w6, 8, 'Fuente de libros: Anexo de nómina RQ-002 (azul) y, para las cuentas que el anexo no trae (vacaciones), Mayor de gastos RQ-004 (azul subrayado en la columna de comentario). El mayor coincide con el anexo en las 143 cuentas comunes.')
th(w6, 9, 2, ['Código', 'Cuenta', 'Según ESF', 'Según Auditoría', 'Diferencia', '%', 'Comentario'])
COMENT = {'D13': 'Diferencia menor.', 'D14': 'Sobreprovisión menor (ver DO-7: enero 614,44).',
          'APO': 'Diferencia de base rol vs IESS (DO-3.1).', 'FR': 'Incluye FR de representantes legales excluidos (ver análisis).',
          'VAC': 'Provisión ≈5,25% de la base vs 1/24 (4,17%).', 'PAS': 'Cuadra.'}
r = 10; group_rows = {}
for k, titulo, _, _ in GROUPS:
    first = r
    for cod, cta, val in accounts[k]:
        enA = cod in ANEXO
        cell(w6, f'B{r}', cod, AR, box=True); cell(w6, f'C{r}', cta, AR, box=True); cell(w6, f'D{r}', ANEXO[cod] if enA else val, BLUE, N2, box=True)
        for col in 'EFGH': w6[f'{col}{r}'].border = BOX
        r += 1
    last = r - 1; group_rows[k] = (first, last)
    cell(w6, f'E{first}', f'={IA}!{ICOL[k][0]}17', GREEN, N2, box=True)
    cell(w6, f'F{first}', f'=ROUND(SUM(D{first}:D{last})-E{first},2)', ARB, N2, box=True)
    cell(w6, f'G{first}', f'=IF(E{first}=0,0,F{first}/E{first})', AR, PC, box=True)
    cell(w6, f'H{first}', COMENT[k], IT, box=True, al=Alignment(wrap_text=True, vertical='top'))
    for col in 'EFGH':
        w6.merge_cells(f'{col}{first}:{col}{last}'); w6[f'{col}{first}'].alignment = Alignment(horizontal='center' if col != 'H' else 'left', vertical='center', wrap_text=True)
    # subtotal
    cell(w6, f'C{r}', f'Subtotal {titulo}', ARB, fill=SUB, box=True); cell(w6, f'D{r}', f'=SUM(D{first}:D{last})', ARB, N2, SUB, box=True)
    cell(w6, f'B{r}', None, fill=SUB, box=True)
    for col in 'EFGH': cell(w6, f'{col}{r}', None, fill=SUB, box=True)
    r += 2
tot = r
cell(w6, f'B{tot}', 'TOTAL', WH, fill=NAVY, box=True); w6.merge_cells(f'B{tot}:C{tot}'); w6[f'B{tot}'].alignment = C
subs = [group_rows[k] for k, *_ in GROUPS]
cell(w6, f'D{tot}', '=' + '+'.join(f'SUM(D{a}:D{b})' for a, b in subs), WH, N2, NAVY, box=True)
cell(w6, f'E{tot}', '=' + '+'.join(f'E{a}' for a, _ in subs), WH, N2, NAVY, box=True)
cell(w6, f'F{tot}', '=' + '+'.join(f'F{a}' for a, _ in subs), WH, N2, NAVY, box=True)
cell(w6, f'G{tot}', f'=IF(E{tot}=0,0,F{tot}/E{tot})', WH, PC, NAVY, box=True); cell(w6, f'H{tot}', None, fill=NAVY, box=True)
for col, mk in (('D', '√'), ('E', 'a)'), ('F', '‡')): cell(w6, f'{col}{tot+1}', mk, RED, al=Alignment(horizontal='center'))

# Análisis FR
a0 = tot + 3; fr1 = group_rows['FR'][0]
cell(w6, f'B{a0}', 'ANÁLISIS DE LA DIFERENCIA DE FONDOS DE RESERVA', ARB)
th(w6, a0 + 1, 2, ['Concepto', '', 'Importe', 'Fuente'], 22)
fr_items = [('FR devengado según auditoría (con exclusiones)', f'={IA}!G17', 'DO-4 v3'),
            ('(+) FR de representantes legales excluidos', f'={IA}!I17', 'RQ-003 Exclusiones · hallazgo V11'),
            ('FR devengado sin exclusiones', f'=D{a0+2}+D{a0+3}', 'Subtotal'),
            ('FR pagado: en rol + depositado en IESS', f'={IA}!J17+{IA}!K17', 'Rol DO-3.1 / Consolidado IESS'),
            ('Pagado en exceso del devengado', f'=D{a0+5}-D{a0+4}', 'Mes de aniversario y prorrateos: revisar por trabajador'),
            ('FR según libros', f'=SUM(D{group_rows["FR"][0]}:D{group_rows["FR"][1]})', 'ESF / DO-6'),
            ('Libros vs pagado', f'=D{a0+7}-D{a0+5}', _R.SUJETOS.get('v04_nombres','') + ': FR pagado con base IESS 0 (V04)'),
            ('Diferencia total DO-6 (debe igualar la columna Diferencia)', f'=D{a0+3}+D{a0+6}+D{a0+8}', f'=IF(ABS(D{a0+9}-F{fr1})<0.05,"Cuadra ✓","Revisar")')]
for i, (t, f, s) in enumerate(fr_items):
    rr = a0 + 2 + i
    cell(w6, f'B{rr}', t, ARB if i in (2, 7) else AR, box=True); w6.merge_cells(f'B{rr}:C{rr}')
    cell(w6, f'D{rr}', f, GREEN if '!' in f else ARB, N2, box=True)
    cell(w6, f'E{rr}', s, IT, box=True); w6.merge_cells(f'E{rr}:H{rr}')

t0 = a0 + 12
texts(w6, [(t0, 'Objetivo:', RU),
           (t0 + 1, 'Verificar que el gasto por beneficios sociales y aportes patronales registrado en resultados del ejercicio 2025 esté adecuadamente '
                    'calculado y registrado, conforme al Código del Trabajo y la Ley de Seguridad Social.', AR),
           (t0 + 3, 'Procedimiento:', RU),
           (t0 + 4, '1. Se agruparon las cuentas de gasto por beneficio y centro de costo según el estado de resultados (anexo de nómina RQ-002).', AR),
           (t0 + 5, '2. Se recalculó el gasto devengado del año sobre el 100% del Consolidado IESS (RQ-003) con el reproceso DO-4 y el rol de pagos (DO-3.1), aplicando las exclusiones del auditor.', AR),
           (t0 + 6, '3. Se determinó la diferencia por beneficio y se analizó su origen; la apertura mensual se presenta en la DO-7.', AR),
           (t0 + 8, 'Marcas:', RED), (t0 + 9, '√  Verificado, comprobado, cotejado (con libros).', ARB),
           (t0 + 10, '‡  Diferencia determinada.', ARB), (t0 + 11, 'a)  Recálculo de auditoría.', ARB),
           (t0 + 13, 'Comentario de auditoría:', RED)], 'H')
cell(w6, f'B{t0+14}', f'="Diferencia total "&TEXT(F{tot},"#,##0.00")&". Principales: vacaciones "&TEXT(F{group_rows["VAC"][0]},"#,##0.00")&" (provisión en exceso) y fondos de reserva "&TEXT(F{fr1},"#,##0.00")&", de los cuales "&TEXT(D{a0+3},"#,##0.00")&" corresponden a FR pagado a representantes legales sin derecho (evaluar ajuste o reclasificación)."', AR)
w6.merge_cells(f'B{t0+14}:H{t0+15}'); w6[f'B{t0+14}'].alignment = Alignment(wrap_text=True, vertical='top'); w6[f'B{t0+14}'].border = BOX
w6.row_dimensions[t0 + 14].height = 30
for col, wd in zip('ABCDEFGH', [2, 18, 30, 14, 16, 14, 12, 34]): w6.column_dimensions[col].width = wd
w6.freeze_panes = 'D10'

# --------------------------- DO-7 Cruce mensual del gasto
w7 = wb.create_sheet('DO7 Cruce Mensual Gasto', 1)
header(w7, 'Beneficios sociales gasto — Cruce mensual', 'DO-7', 11)
banner(w7, 11, 'Fuente de libros: Mayor de gastos RQ-004, gasto mensual por concepto (pestaña «Libros mensuales»).')
D6 = "'DO6 Cruce Global Gasto'"
def block(ws, r0, c0, titulo, k):
    cols = [chr(64 + c0 + i) for i in range(4)]
    cell(ws, f'{cols[1]}{r0}', titulo, ARB)
    th(ws, r0 + 1, c0, ['Mes', 'Libros', 'Auditoría', 'Diferencia'], 20)
    for m in range(12):
        rr = r0 + 2 + m
        cell(ws, f'{cols[0]}{rr}', MESES[m], AR, box=True)
        cell(ws, f'{cols[1]}{rr}', f"='Libros mensuales'!{LCOL[k]}{6+m}", GREEN, N2, box=True)
        cell(ws, f'{cols[2]}{rr}', f'={IA}!{ICOL[k][0]}{5+m}', GREEN, N2, box=True)
        cell(ws, f'{cols[3]}{rr}', f'={cols[1]}{rr}-{cols[2]}{rr}', AR, N2, box=True)
    rt = r0 + 14
    cell(ws, f'{cols[0]}{rt}', 'Total', WH, fill=NAVY, box=True)
    for col in cols[1:]: cell(ws, f'{col}{rt}', f'=SUM({col}{r0+2}:{col}{rt-1})', WH, N2, NAVY, box=True)
    cell(ws, f'{cols[0]}{rt+1}', 'Cuadre con DO-6:', IT)
    cell(ws, f'{cols[2]}{rt+1}', f'={D6}!F{group_rows[k][0]}', GREEN, N2)
    cell(ws, f'{cols[3]}{rt+1}', f'=IF(ABS({cols[3]}{rt}-{cols[2]}{rt+1})<0.05,"✓","Revisar")', IT)
    return rt
BL = {}
BL['APO'] = block(w7, 7, 2, 'Aporte patronal', 'APO'); BL['PAS'] = block(w7, 7, 8, 'Aporte pasantes', 'PAS')
BL['D13'] = block(w7, 25, 2, 'Décimo tercer sueldo', 'D13'); BL['D14'] = block(w7, 25, 8, 'Décimo cuarto sueldo', 'D14')
BL['FR'] = block(w7, 43, 2, 'Fondos de reserva', 'FR'); BL['VAC'] = block(w7, 43, 8, 'Vacaciones', 'VAC')
cell(w7, 'H60', 'FR excluido por mes (auditor)', IT)
cell(w7, 'B61', 'Fondos de reserva: la diferencia mensual incluye el FR pagado a representantes legales excluidos (ver análisis DO-6).', IT)
w7.merge_cells('B61:K61')
cell(w7, 'B62', 'Vacaciones: el gasto en libros (DO-7) difiere de la provisión acreditada al pasivo (DO-5): ver control de coherencia en la hoja Controles.', IT)
w7.merge_cells('B62:K62')
w7['H60'].value = None
texts(w7, [(65, 'Objetivo:', RU),
           (66, 'Verificar mes a mes el gasto por beneficios sociales y aportes registrado en libros contra el recálculo de auditoría y explicar las diferencias.', AR),
           (68, 'Procedimiento:', RU),
           (69, '1. Se tomó el gasto mensual por beneficio según libros. 2. Se comparó con el devengado mensual de auditoría (Consolidado IESS, DO-4 y rol DO-3.1). '
                '3. El total de cada beneficio se cuadra con la DO-6.', AR),
           (71, 'Marcas:', RED), (72, '√  Verificado, comprobado, cotejado (con libros).', ARB), (73, '‡  Diferencia determinada.', ARB),
           (74, 'a)  Recálculo de auditoría.', ARB), (76, 'Comentario de auditoría:', RED)], 'K')
w7.merge_cells('B77:K78'); w7['B77'].border = BOX
cell(w7, 'B77', 'Aporte pasantes: con el Consolidado IESS ordenado por mes, cada mes cuadra con libros (el papel anterior tenía la columna de auditoría desordenada). '
                'D14: la mayor diferencia es enero (614,44). Vacaciones: exceso sistemático mensual por tasa de provisión.', AR)
w7['B77'].alignment = Alignment(wrap_text=True, vertical='top')
for col, wd in zip('ABCDEFGHIJK', [2, 13, 15, 15, 14, 12, 12, 13, 15, 15, 14]): w7.column_dimensions[col].width = wd

# --------------------------- Controles
wc = wb.create_sheet('Controles')
cell(wc, 'B2', 'CONTROLES DE INTEGRIDAD', ARB)
th(wc, 4, 2, ['Control', 'Valor A', 'Valor B', 'Diferencia', 'Estado'])
ctl = []
for k, titulo, *_ in GROUPS:
    a, b = group_rows[k]
    ctl.append((f'{titulo}: libros DO-6 (cuentas) = libros mensuales DO-7', f'=SUM({D6}!D{a}:D{b})', f"='Libros mensuales'!{LCOL[k]}18", 0.05))
ctl += [('Gasto DO-2: D13', f'=SUM({D6}!D{group_rows["D13"][0]}:D{group_rows["D13"][1]})', _R.CIFRAS['d13_gasto'], 0.01),
        ('Gasto DO-2: D14', f'=SUM({D6}!D{group_rows["D14"][0]}:D{group_rows["D14"][1]})', _R.CIFRAS['d14_gasto_rq002'], 0.01),
        ('Gasto DO-2: FR', f'=SUM({D6}!D{group_rows["FR"][0]}:D{group_rows["FR"][1]})', _R.CIFRAS['fr_gasto_libros'], 0.01),
        ('Gasto DO-2: aporte patronal total', f'=SUM({D6}!D{group_rows["APO"][0]}:D{group_rows["APO"][1]})+SUM({D6}!D{group_rows["PAS"][0]}:D{group_rows["PAS"][1]})', _R.CIFRAS['aporte_patronal_total'], 0.01),
        ('Aporte patronal + CCC auditoría = DO-3', f'={IA}!C17', _R.CIFRAS['aporte_ccc_aud'], 0.01),
        ('Aporte pasantes auditoría = IESS pasantes', f'={IA}!D17', _R.CIFRAS['pasantes_aporte'], 0.01),
        ('Vacaciones devengadas = DO-4', f'={IA}!H17', _R.CIFRAS['provision_vac_anual'], 0.05),
        ('Análisis FR explica la diferencia DO-6', f'={D6}!D{a0+9}', f'={D6}!F{fr1}', 0.05)]
for i, (t, a, b, tol) in enumerate(ctl):
    rr = 5 + i
    cell(wc, f'B{rr}', t, AR, box=True); cell(wc, f'C{rr}', a, GREEN, N2, box=True); cell(wc, f'D{rr}', b, GREEN, N2, box=True)
    cell(wc, f'E{rr}', f'=ROUND(C{rr}-D{rr},2)', AR, N2, box=True)
    cell(wc, f'F{rr}', f'=IF(ABS(E{rr})<={tol},"OK","REVISAR")', ARB, box=True, al=Alignment(horizontal='center'))
n = len(ctl); cell(wc, f'B{6+n}', f'=COUNTIF(F5:F{4+n},"OK")&" de {n} controles OK"', ARB)
cell(wc, f'B{8+n}', 'Coherencia gasto vs pasivo (informativo)', ARB)
cell(wc, f'B{9+n}', 'Vacaciones: gasto en libros (DO-7) − provisión acreditada al pasivo en libros (DO-5)', AR, box=True)
cell(wc, f'C{9+n}', "='Libros mensuales'!H18", GREEN, N2, box=True); cell(wc, f'D{9+n}', -MY.pasivo_tot(MY.B, '5BS.21204.003', 'PROVISION'), BLUE, N2, box=True)
cell(wc, f'E{9+n}', f'=ROUND(C{9+n}-D{9+n},2)', ARB, N2, box=True)
cell(wc, f'F{9+n}', 'Mayor RQ-004: ajuste de actualización + reverso (débito al pasivo contra el gasto)', IT, box=True)
wc.column_dimensions['B'].width = 66
for col in 'CDEF': wc.column_dimensions[col].width = 18

for ws in (w6, w7):
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = 'landscape'; ws.sheet_properties.pageSetUpPr.fitToPage = True; ws.page_setup.fitToHeight = 0
wb.active = 0
_wf = wb['Ficha']
_r = max(_wf.max_row + 2, 14)
_wf.cell(_r, 2, 'Año auditado 2026. Cédula construida con datos de la plantilla 2025 (rol, IESS, anexo y comprobantes); se reemplazan con la información 2026 del cliente.').font = Font(name='Arial', size=8, italic=True, color='FFC00000')
wb.save(OUT); print('ok', OUT, 'filas DO-6 total', tot)
