# -*- coding: utf-8 -*-
from backend.app.aud.niif.procesadores.nomina import rutas as _R
"""DO-8 Base imponible IESS vs libros (ERI). Formato: pestaña «DO8 Calculo Base imponible Apor» del papel de referencia.
Libros: Anexo RQ-002 y Mayor de gastos RQ-004. IESS: Consolidado RQ-003. Rol: DO-3.1."""
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.drawing.image import Image as XLImage

OUT = (_R.CTX.out + '/DO-8_Base_Imponible_IESS_vs_Libros.xlsx')
SRC = _R.CTX.papel
g = pd.read_pickle((_R.CTX.home + '/g3.pkl'))
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

NAVY = PatternFill('solid', fgColor='FF0F2341'); SUB = PatternFill('solid', fgColor='FFDDE6F3')
AR = Font(name='Arial', size=10); ARB = Font(name='Arial', size=10, bold=True)
WH = Font(name='Arial', size=10, bold=True, color='FFFFFFFF'); WH12 = Font(name='Arial', size=12, bold=True, color='FFFFFFFF')
BLUE = Font(name='Arial', size=10, color='FF0000FF'); GREEN = Font(name='Arial', size=10, color='FF008000')
RED = Font(name='Arial', size=10, bold=True, color='FFC00000'); RU = Font(name='Arial', size=10, bold=True, color='FFC00000', underline='single')
NAVYF = Font(name='Arial', size=10, bold=True, color='FF1F3864'); IT = Font(name='Arial', size=8, italic=True)
thin = Side(style='thin', color='FF000000'); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
N2 = '#,##0.00;(#,##0.00);"-"'; PC = '0.00%;(0.00%);"-"'
C = Alignment(horizontal='center', vertical='center', wrap_text=True)

def cell(ws, ref, v, font=AR, fmt=None, fill=None, al=None, box=False):
    c = ws[ref]; c.value = v; c.font = font
    if fmt: c.number_format = fmt
    if fill: c.fill = fill
    if al: c.alignment = al
    if box: c.border = BOX
    return c

def th(ws, row, col0, labels, height=30):
    for i, t in enumerate(labels):
        c = ws.cell(row, col0 + i, t); c.font = WH; c.fill = NAVY; c.alignment = C; c.border = BOX
    ws.row_dimensions[row].height = height

src = load_workbook(SRC, data_only=True)['DO8 Calculo Base imponible Apor']
ANEXO = {str(r[0]).strip(): abs(r[5]) for r in load_workbook(_R.CTX.anexo, data_only=True).active.iter_rows(min_row=4, values_only=True) if r[0] and isinstance(r[5], (int, float))}
ORANGE = Font(name='Arial', size=10, color='FFC65911')
GROUPS = [('SUE', 'Sueldos', 15, 34), ('HE', 'Horas extras', 36, 52), ('BON', 'Bono desempeño', 54, 73),
          ('COM', 'Comisiones', 75, 76), ('PRE', 'Premios', 78, 79)]
acc = {k: [(src.cell(r, 1).value, str(src.cell(r, 2).value).strip(), float(src.cell(r, 3).value or 0))
           for r in range(a, b + 1) if src.cell(r, 1).value] for k, _, a, b in GROUPS}
pas_acc = [(src.cell(r, 1).value, str(src.cell(r, 2).value).strip(), float(src.cell(r, 3).value or 0)) for r in range(84, 92) if src.cell(r, 1).value]

from backend.app.aud.niif.procesadores.nomina import mayores as MY
mon = {'F': MY.gasto_mes('SUE'), 'G': MY.gasto_mes('HE'), 'H': MY.gasto_mes('BON'), 'I': MY.gasto_mes('COM'), 'J': MY.gasto_mes('PRE'),
       'K': MY.pasivo_mes(MY.B, '5BS.21204.003', 'GOCES')}
pas_lib = MY.gasto_mes('EST')
acc = {k: [(cod, cta, MY.gasto_cta(str(cod).strip())) for cod, cta, _ in v] for k, v in acc.items()}
pas_acc = [(cod, cta, MY.gasto_cta(str(cod).strip())) for cod, cta, _ in pas_acc]

wb = Workbook()
wf = wb.active; wf.title = 'Ficha'
cell(wf, 'B2', 'FICHA DEL ENCARGO (encabezado de las cédulas)', ARB)
for i, (k, v) in enumerate([('Cliente', _R.CTX.cliente), ('Período terminado', pd.Timestamp(_R.CTX.corte).to_pydatetime()),
                            ('Preparado por', _R.CTX.preparado), ('Revisado por', _R.CTX.revisado), ('Fecha', '=TODAY()')]):
    cell(wf, f'B{4+i}', k, ARB, box=True); c = cell(wf, f'C{4+i}', v, BLUE if i < 4 else AR, box=True)
    if i in (1, 4): c.number_format = 'dd/mm/yyyy'
wf.column_dimensions['B'].width = 22; wf.column_dimensions['C'].width = 30

# ---- Insumos
wi = wb.create_sheet('Insumos mensuales')
cell(wi, 'B2', 'INSUMOS MENSUALES', ARB)
cell(wi, 'B3', 'Azul: Mayor de gastos RQ-004 (sueldos, horas extras, bonos, comisiones, premios, estipendio) y Mayor de pasivos RQ-004 (vacaciones tomadas = goces). '
               'Verde: Consolidado IESS (RQ-003) y rol «normal» (DO-3.1).', IT)
th(wi, 5, 2, ['Mes', 'Sueldos', 'Horas extras (incl. recargo nocturno)', 'Bonos', 'Comisiones y otros', 'Premios',
              'Vacaciones tomadas (rol)', 'Estipendio pasantes (libros)', 'Base IESS empleados', 'Base IESS pasantes', 'Base gravada rol'], 44)
for m in range(12):
    r = 6 + m; cell(wi, f'B{r}', MESES[m], AR, box=True)
    for j, col in enumerate('FGHIJK'): cell(wi, f'{chr(67+j)}{r}', mon[col][m], BLUE, N2, box=True)
    cell(wi, f'I{r}', pas_lib[m], BLUE, N2, box=True)
    cell(wi, f'J{r}', float(g.loc[float(m + 1), 'base_emp']), GREEN, N2, box=True)
    cell(wi, f'K{r}', float(g.loc[float(m + 1), 'base_pas']), GREEN, N2, box=True)
    cell(wi, f'L{r}', float(g.loc[float(m + 1), 'rol_base']), GREEN, N2, box=True)
cell(wi, 'B18', 'Σ', RED, box=True)
for col in 'CDEFGHIJKL': cell(wi, f'{col}18', f'=SUM({col}6:{col}17)', ARB, N2, box=True)
wi.column_dimensions['A'].width = 2; wi.column_dimensions['B'].width = 13
for col in 'CDEFGHIJKL': wi.column_dimensions[col].width = 15
wi.freeze_panes = 'C6'
IM = "'Insumos mensuales'"

# ---- DO-8
ws = wb.create_sheet('DO8 Base Imponible IESS', 0)
for r in range(1, 4):
    for col in range(1, 17): ws.cell(r, col).fill = NAVY
ws.row_dimensions[1].height = 34; ws.row_dimensions[2].height = 22
img = XLImage(_R.CTX.logo); img.height = 60; img.width = 160; ws.add_image(img, 'A1')
cell(ws, 'H1', 'OBLIGACIONES ACUMULADAS', WH12); cell(ws, 'H3', 'Base imponible IESS vs libros ERI', WH)
cell(ws, 'A4', 'Nombre del cliente:', ARB, box=True); cell(ws, 'B4', '=Ficha!C4', AR, box=True)
cell(ws, 'E4', 'Período terminado:', ARB, box=True); cell(ws, 'F4', '=Ficha!C5', AR, 'dd/mm/yyyy', box=True)
cell(ws, 'A5', 'Preparado por:', ARB, box=True); cell(ws, 'B5', '=Ficha!C6', AR, box=True)
cell(ws, 'C5', 'Revisado:', ARB, box=True); cell(ws, 'D5', '=Ficha!C7', AR, box=True)
cell(ws, 'E5', 'Fecha:', ARB, box=True); cell(ws, 'F5', '=Ficha!C8', AR, 'dd/mm/yyyy', box=True)
cell(ws, 'H5', 'Referencia de PT', ARB, box=True); cell(ws, 'I5', 'DO-8', RED, box=True)

ws.merge_cells('B6:Q6'); _b = ws['B6']; _b.value = ('Fuente de libros: Anexo RQ-002 (azul). En naranja: comisiones, premios y estipendio de pasantes, que el anexo no trae; '
    'el detalle mensual proviene del Mayor de gastos RQ-004, que coincide con el anexo en las cuentas comunes.'); _b.font = Font(name='Arial', size=9, bold=True, color='FF1F3864')
_b.fill = PatternFill('solid', fgColor='FFFFF2CC'); _b.alignment = Alignment(wrap_text=True, vertical='center'); ws.row_dimensions[6].height = 26
# Bloque izquierdo: base según planilla vs balance (EMPLEADOS)
cell(ws, 'B8', 'A. EMPLEADOS (rol «normal»)', NAVYF)
cell(ws, 'B9', 'BASE IMPONIBLE', ARB)
cell(ws, 'B10', 'SEGÚN PLANILLA IESS', WH, fill=NAVY); cell(ws, 'C10', f'={IM}!J18', WH, N2, NAVY); cell(ws, 'D10', '∏', RED)
cell(ws, 'B12', 'SEGÚN BALANCE AL 31/12/2025', ARB)
r = 13; subt = {}
for k, titulo, *_ in GROUPS:
    first = r
    for cod, cta, v in acc[k]:
        enA = cod in ANEXO
        cell(ws, f'A{r}', cod, AR); cell(ws, f'B{r}', cta, AR); cell(ws, f'C{r}', ANEXO[cod] if enA else v, BLUE, N2); r += 1
    cell(ws, f'B{r}', f'Subtotal {titulo.lower()}', ARB, fill=SUB); cell(ws, f'C{r}', f'=SUM(C{first}:C{r-1})', ARB, N2, SUB)
    subt[k] = r; r += 2
cell(ws, f'B{r}', 'Vacaciones tomadas (rol DO-3.1, cargadas al pasivo)', AR); cell(ws, f'C{r}', f'={IM}!H18', GREEN, N2); subt['VAC'] = r; r += 1
cell(ws, f'B{r}', 'Retroactivo', AR); cell(ws, f'C{r}', 0, BLUE, N2); subt['RET'] = r; r += 2
tot_e = r
cell(ws, f'B{r}', 'TOTAL SEGÚN LIBROS (empleados)', WH, fill=NAVY)
cell(ws, f'C{r}', '=' + '+'.join(f'C{subt[k]}' for k in ['SUE', 'HE', 'BON', 'COM', 'PRE', 'VAC', 'RET']), WH, N2, NAVY); cell(ws, f'D{r}', '√', RED)
r += 2; dif_e = r
cell(ws, f'B{r}', 'DIFERENCIA (planilla − libros)', ARB, box=True); cell(ws, f'C{r}', f'=C10-C{tot_e}', ARB, N2, box=True)
cell(ws, f'D{r}', f'=IF(C{tot_e}=0,0,C{r}/C{tot_e})', AR, PC, box=True); cell(ws, f'E{r}', '‡', RED)

# Pasantes
r += 3; p0 = r
cell(ws, f'B{r}', 'B. PASANTES (fuera del rol)', NAVYF); r += 1
cell(ws, f'B{r}', 'Base IESS pasantes (aportan sobre SBU)', AR); cell(ws, f'C{r}', f'={IM}!K18', GREEN, N2); cell(ws, f'D{r}', '∏', RED); pb = r; r += 1
first = r
for cod, cta, v in pas_acc:
    enA = cod in ANEXO
    cell(ws, f'A{r}', cod, AR); cell(ws, f'B{r}', cta, AR); cell(ws, f'C{r}', ANEXO[cod] if enA else v, BLUE, N2); r += 1
cell(ws, f'B{r}', 'Subtotal estipendio pasantes (libros)', ARB, fill=SUB); cell(ws, f'C{r}', f'=SUM(C{first}:C{r-1})', ARB, N2, SUB); ps = r; r += 1
cell(ws, f'B{r}', 'DIFERENCIA (IESS − libros)', ARB, box=True); cell(ws, f'C{r}', f'=C{pb}-C{ps}', ARB, N2, box=True); cell(ws, f'E{r}', '‡', RED); pd_ = r; r += 1
cell(ws, f'B{r}', 'El IESS registra a los pasantes sobre el SBU; el libro registra el estipendio pagado. La Ley de Pasantías (art. 7) exige el aporte íntegro de la empresa sobre el SBU: diferencia esperada, no es incumplimiento (ver DO-12 H-5).', IT)
ws.merge_cells(f'B{r}:E{r+1}'); ws[f'B{r}'].alignment = Alignment(wrap_text=True, vertical='top'); r += 3

# Conciliación con la cifra del papel anterior
cell(ws, f'B{r}', 'C. CONCILIACIÓN CON EL PAPEL ANTERIOR', NAVYF); r += 1
cc0 = r
items = [('Base IESS total (DO-3)', f'=C10+C{pb}'), ('(−) Diferencia de pasantes IESS vs libros', f'=-C{pd_}'),
         ('Base «según planilla» del papel anterior', f'=C{cc0}+C{cc0+1}'),
         ('Libros totales (empleados + pasantes)', f'=C{tot_e}+C{ps}'), ('Diferencia del papel anterior', f'=C{cc0+2}-C{cc0+3}')]
for i, (t, f) in enumerate(items):
    cell(ws, f'B{r}', t, ARB if i in (2, 4) else AR, box=True); cell(ws, f'C{r}', f, ARB if i in (2, 4) else AR, N2, box=True); r += 1
cell(ws, f'B{r}', '=IF(ABS(C'+str(cc0+4)+'-C'+str(dif_e)+')<0.01,"Igual a la diferencia de empleados: el papel anterior neteaba los pasantes ✓","Revisar")', IT); r += 2
last_left = r

# Bloque derecho: mensual empleados
cell(ws, 'F8', 'CRUCE MENSUAL — EMPLEADOS', NAVYF)
th(ws, 9, 6, ['Mes', 'Sueldos', 'Horas extras', 'Bonos', 'Comisiones y otros', 'Premios', 'Vac. tomadas', 'Total libros',
              'IESS', 'Diferencia (libros − IESS)', 'Base rol (DO-3.1)', 'Rol − IESS'], 44)
for m in range(12):
    rr = 10 + m; ir = 6 + m
    cell(ws, f'F{rr}', MESES[m], AR, box=True)
    for j, src_col in enumerate('CDEFGH'): cell(ws, f'{chr(71+j)}{rr}', f'={IM}!{src_col}{ir}', GREEN, N2, box=True)
    cell(ws, f'M{rr}', f'=SUM(G{rr}:L{rr})', AR, N2, box=True)
    cell(ws, f'N{rr}', f'={IM}!J{ir}', GREEN, N2, box=True)
    cell(ws, f'O{rr}', f'=M{rr}-N{rr}', ARB, N2, box=True)
    cell(ws, f'P{rr}', f'={IM}!L{ir}', GREEN, N2, box=True)
    cell(ws, f'Q{rr}', f'=P{rr}-N{rr}', AR, N2, box=True)
cell(ws, 'F22', 'Total', WH, fill=NAVY, box=True)
for col in 'GHIJKLMNOPQ': cell(ws, f'{col}22', f'=SUM({col}10:{col}21)', WH, N2, NAVY, box=True)
cell(ws, 'F23', '=IF(ABS(O22+C' + str(dif_e) + ')<0.01,"Total cuadra con la diferencia del bloque A ✓","Revisar")', IT)
cell(ws, 'F24', 'Rol − IESS: conceptos gravados en el rol no reportados al IESS (22 trabajadores, ver Cruce Rol vs IESS de DO-3.1).', IT)

# Mensual pasantes
cell(ws, 'F27', 'CRUCE MENSUAL — PASANTES', NAVYF)
th(ws, 28, 6, ['Mes', 'IESS', 'Libros', 'Diferencia'], 20)
for m in range(12):
    rr = 29 + m; ir = 6 + m
    cell(ws, f'F{rr}', MESES[m], AR, box=True)
    cell(ws, f'G{rr}', f'={IM}!K{ir}', GREEN, N2, box=True); cell(ws, f'H{rr}', f'={IM}!I{ir}', GREEN, N2, box=True)
    cell(ws, f'I{rr}', f'=G{rr}-H{rr}', AR, N2, box=True)
cell(ws, 'F41', 'Total', WH, fill=NAVY, box=True)
for col in 'GHI': cell(ws, f'{col}41', f'=SUM({col}29:{col}40)', WH, N2, NAVY, box=True)
cell(ws, 'F42', 'IESS ordenado por mes según el Consolidado (el papel anterior lo tenía desordenado; el total no cambia).', IT)

# Textos
t0 = max(last_left, 46)
txt = [(t0, 'Objetivo:', RU),
       (t0 + 1, 'Verificar que la base imponible declarada al IESS corresponda a los conceptos remunerativos registrados en libros (art. 11 de la Ley de Seguridad Social) y explicar las diferencias.', AR),
       (t0 + 3, 'Procedimiento:', RU),
       (t0 + 4, '1. Se tomó la base imponible del Consolidado IESS (RQ-003), separando empleados del rol y pasantes. 2. Se sumaron los conceptos remunerativos según el estado de resultados '
                '(sueldos, horas extras, bonos, comisiones, premios) más las vacaciones gozadas del rol. 3. Se comparó por mes y en total, y se cotejó con la base gravada del rol (DO-3.1).', AR),
       (t0 + 6, 'Marcas:', RED), (t0 + 7, '√  Verificado, comprobado, cotejado (con libros).', ARB),
       (t0 + 8, '∏  Verificado, comprobado, cotejado (con planillas).', ARB), (t0 + 9, '‡  Diferencia determinada.', ARB),
       (t0 + 11, 'Comentario de auditoría:', RED)]
for rr, t, f in txt:
    cell(ws, f'B{rr}', t, f)
    if f is AR: ws.merge_cells(f'B{rr}:Q{rr}'); ws[f'B{rr}'].alignment = Alignment(wrap_text=True, vertical='top'); ws.row_dimensions[rr].height = 30
cell(ws, f'B{t0+12}', f'="Empleados: diferencia planilla − libros "&TEXT(C{dif_e},"#,##0.00")&" ("&TEXT(D{dif_e},"0.00%")&"), razonable. Pasantes: el IESS aplica la base SBU ("&TEXT(C{pb},"#,##0.00")&") frente al estipendio en libros ("&TEXT(C{ps},"#,##0.00")&"), como exige la Ley de Pasantías art. 7 (aporte íntegro de la empresa). El rol grava "&TEXT(Q22,"#,##0.00")&" más que lo reportado al IESS (posible subdeclaración de aportes: ver DO-3.1)."', AR)
ws.merge_cells(f'B{t0+12}:Q{t0+13}'); ws[f'B{t0+12}'].alignment = Alignment(wrap_text=True, vertical='top'); ws[f'B{t0+12}'].border = BOX
ws.row_dimensions[t0 + 12].height = 30
for col, wd in zip('ABCDEFGHIJKLMNOPQ', [17, 38, 15, 9, 16, 12, 13, 12, 12, 12, 10, 12, 14, 14, 14, 14, 12]): ws.column_dimensions[col].width = wd
ws.sheet_view.showGridLines = False
ws.page_setup.orientation = 'landscape'; ws.sheet_properties.pageSetUpPr.fitToPage = True; ws.page_setup.fitToHeight = 0

# ---- Controles
wc = wb.create_sheet('Controles')
cell(wc, 'B2', 'CONTROLES DE INTEGRIDAD', ARB)
th(wc, 4, 2, ['Control', 'Valor A', 'Valor B', 'Diferencia', 'Estado'])
D8 = "'DO8 Base Imponible IESS'"
ctl = [('Sueldos: cuentas = mensual = DO-2', f'={D8}!C{subt["SUE"]}', f'={IM}!C18', 0.01),
       ('Horas extras: cuentas = mensual', f'={D8}!C{subt["HE"]}', f'={IM}!D18', 0.01),
       ('Bonos: cuentas = mensual = DO-2', f'={D8}!C{subt["BON"]}', f'={IM}!E18', 0.01),
       ('Comisiones: cuentas = mensual', f'={D8}!C{subt["COM"]}', f'={IM}!F18', 0.01),
       ('Premios: cuentas = mensual', f'={D8}!C{subt["PRE"]}', f'={IM}!G18', 0.01),
       ('Estipendio pasantes: cuentas = mensual', f'={D8}!C{ps}', f'={IM}!I18', 0.01),
       ('Base IESS total = DO-3', f'={IM}!J18+{IM}!K18', _R.CIFRAS['base_iess'], 0.01),
       ('Vacaciones tomadas = rol DO-3.1', f'={IM}!H18', _R.CIFRAS['vac_tomadas'], 0.01),
       ('Base gravada rol = DO-3.1', f'={IM}!L18', _R.CIFRAS['rol_base'], 0.01),
       ('Cruce mensual empleados = diferencia bloque A', f'={D8}!O22', f'=-{D8}!C{dif_e}', 0.01),
       ('Papel anterior reconciliado (249,46)', f'={D8}!C{cc0+4}', 249.46, 0.01)]
for i, (t, a, b, tol) in enumerate(ctl):
    rr = 5 + i
    cell(wc, f'B{rr}', t, AR, box=True); cell(wc, f'C{rr}', a, GREEN, N2, box=True); cell(wc, f'D{rr}', b, GREEN, N2, box=True)
    cell(wc, f'E{rr}', f'=ROUND(C{rr}-D{rr},2)', AR, N2, box=True)
    cell(wc, f'F{rr}', f'=IF(ABS(E{rr})<={tol},"OK","REVISAR")', ARB, box=True, al=Alignment(horizontal='center'))
n = len(ctl); cell(wc, f'B{6+n}', f'=COUNTIF(F5:F{4+n},"OK")&" de {n} controles OK"', ARB)
wc.column_dimensions['B'].width = 56
for col in 'CDEF': wc.column_dimensions[col].width = 18
wb.active = 0
_wf = wb['Ficha']
_r = max(_wf.max_row + 2, 14)
_wf.cell(_r, 2, 'Año auditado 2026. Cédula construida con datos de la plantilla 2025 (rol, IESS, anexo y comprobantes); se reemplazan con la información 2026 del cliente.').font = Font(name='Arial', size=8, italic=True, color='FFC00000')
wb.save(OUT); print('ok', OUT, 'dif_e', dif_e, 'pd', pd_, 'cc0', cc0)
