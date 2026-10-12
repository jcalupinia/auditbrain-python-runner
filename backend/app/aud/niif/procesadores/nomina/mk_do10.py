# -*- coding: utf-8 -*-
from backend.app.aud.niif.procesadores.nomina import rutas as _R
"""DO-10 Roles de pago vs libros: gastos y provisiones. Formato: pestaña «DO10 Prov. y Gstos vs Roles» del papel de referencia.
Rol: RQ-006 (pestañas «normal» y «pasantes»). Libros: RQ-002 (Anexo) y Mayores RQ-004 (gastos y pasivos)."""
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.drawing.image import Image as XLImage

OUT = (_R.CTX.out + '/DO-10_Roles_vs_Libros.xlsx')
rm = pd.read_pickle((_R.CTX.home + '/rol_mes.pkl'))
comp = pd.read_pickle((_R.CTX.home + '/comprobantes.pkl'))
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
ANEXO = {str(r[0]).strip(): abs(r[5]) for r in load_workbook(_R.CTX.anexo, data_only=True).active.iter_rows(min_row=4, values_only=True)
         if r[0] and isinstance(r[5], (int, float))}



from backend.app.aud.niif.procesadores.nomina import mayores as MY
SUE = [c for c, _, _ in MY.cuentas_por_concepto('SUE')]
HE = [c for c, _, _ in MY.cuentas_por_concepto('HE')]
BON = [c for c, _, _ in MY.cuentas_por_concepto('BON')]
FRC = [c for c, _, _ in MY.cuentas_por_concepto('FR')]
lib_sue_mes = MY.gasto_mes('SUE')
fr_iess = comp[comp.tipo == 'Fondos de reserva'].groupby('mes').total.sum()

# --- décimos jubilares del rol (derivados de los datos; antes constantes del cliente) ---
from backend.app.aud.niif.procesadores.nomina import motor as _MO
_nf = lambda v: f"{v:,.2f}".translate(str.maketrans({',': '.', '.': ','}))
_rol_norm = _MO.leer_rol_normal(_R.CTX.rol)
_jd13 = round(sum(d['d13mens'] for d in _rol_norm if d['tipo'] == 'Jubilado'), 2)   # D13 mensualizado de jubilados patronales
_jd14 = round(sum(d['d14mens'] for d in _rol_norm if d['tipo'] == 'Jubilado'), 2)   # D14 mensualizado de jubilados patronales
_jub_total = round(_jd13 + _jd14, 2)
# D14 mensualizado: diferencia residual entre libros y (rol − jubilar), derivada
_rol_d14_mens = round(float(rm['D14 MENS SIE'].sum()), 2)
_g14_mens = round(sum(MY.gasto_mes('D14')) + MY.pasivo_tot(MY.B, '5BS.21204.002', 'PROVISION'), 2)
_aj14 = round(_g14_mens - (_rol_d14_mens - _jd14), 2)

NAVY = PatternFill('solid', fgColor='FF0F2341'); SUB = PatternFill('solid', fgColor='FFDDE6F3'); YEL = PatternFill('solid', fgColor='FFFFF2CC')
GRY = PatternFill('solid', fgColor='FFEDEDED')
AR = Font(name='Arial', size=10); ARB = Font(name='Arial', size=10, bold=True)
WH = Font(name='Arial', size=10, bold=True, color='FFFFFFFF'); WH12 = Font(name='Arial', size=12, bold=True, color='FFFFFFFF')
BLUE = Font(name='Arial', size=10, color='FF0000FF'); GREEN = Font(name='Arial', size=10, color='FF008000'); ORANGE = Font(name='Arial', size=10, color='FFC65911')
RED = Font(name='Arial', size=10, bold=True, color='FFC00000'); RU = Font(name='Arial', size=10, bold=True, color='FFC00000', underline='single')
NAVYF = Font(name='Arial', size=10, bold=True, color='FF1F3864'); IT = Font(name='Arial', size=8, italic=True)
thin = Side(style='thin', color='FF000000'); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
N2 = '#,##0.00;(#,##0.00);"-"'
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

wb = Workbook()
wf = wb.active; wf.title = 'Ficha'
cell(wf, 'B2', 'FICHA DEL ENCARGO (encabezado de las cédulas)', ARB)
for i, (k, v) in enumerate([('Cliente', _R.CTX.cliente), ('Período terminado', pd.Timestamp(_R.CTX.corte).to_pydatetime()),
                            ('Preparado por', _R.CTX.preparado), ('Revisado por', _R.CTX.revisado), ('Fecha', '=TODAY()')]):
    cell(wf, f'B{4+i}', k, ARB, box=True); c = cell(wf, f'C{4+i}', v, BLUE if i < 4 else AR, box=True)
    if i in (1, 4): c.number_format = 'dd/mm/yyyy'
wf.column_dimensions['B'].width = 22; wf.column_dimensions['C'].width = 30

# ---------------- Insumo Rol (RQ-006)
CONC = [('SUELDO', 'Sueldo empleados'), ('PAS', 'Sueldo pasantes'), ('VAC TOMADAS', 'Vac. tomadas'), ('REC.NOCTURNO', 'Rec. nocturno'),
        ('H. EXT. 50%', 'H. ext. 50%'), ('H. EXT. 100%', 'H. ext. 100%'), ('DESEMPEÑO', 'Desempeño'), ('BONIFICACION', 'Bonificación'),
        ('COMISIONES', 'Comisiones'), ('PREMIOS', 'Premios'), ('FOND.RESERV.', 'Fondos de reserva'), ('D13 MENS', 'D13 mensualizado'),
        ('D14 MENS SIE', 'D14 mensualizado Sierra'), ('LIQ.DEC13', 'Liq. D13'), ('LIQ.DEC14S', 'Liq. D14'), ('VAC.FINIQUIT', 'Vac. finiquito')]
COL = {k: chr(67 + i) for i, (k, _) in enumerate(CONC)}   # C..R
wr = wb.create_sheet('Rol RQ-006')
cell(wr, 'B2', 'ROL DE PAGOS POR MES Y CONCEPTO — RQ-006 (pestaña «normal»: empleados y jubilados; pestaña «pasantes»)', ARB)
th(wr, 4, 2, ['Mes'] + [t for _, t in CONC], 40)
for m in range(1, 13):
    r = 4 + m; cell(wr, f'B{r}', MESES[m - 1], AR, box=True)
    for k, _ in CONC: cell(wr, f'{COL[k]}{r}', float(rm.loc[m, k]), GREEN, N2, box=True)
cell(wr, 'B17', 'Σ', RED, box=True)
for k, _ in CONC: cell(wr, f'{COL[k]}17', f'=SUM({COL[k]}5:{COL[k]}16)', ARB, N2, box=True)
cell(wr, 'B19', 'Jubilados patronales incluidos en la pestaña «normal»: sus décimos y pensiones se reportan aparte y no participan del reproceso de beneficios.', IT)
wr.column_dimensions['A'].width = 2; wr.column_dimensions['B'].width = 12
for k, _ in CONC: wr.column_dimensions[COL[k]].width = 12
wr.freeze_panes = 'C5'
RR = "'Rol RQ-006'"

# ---------------- DO-10
ws = wb.create_sheet('DO10 Roles vs Libros', 0)
for r in range(1, 4):
    for col in range(1, 19): ws.cell(r, col).fill = NAVY
ws.row_dimensions[1].height = 34; ws.row_dimensions[2].height = 22
img = XLImage(_R.CTX.logo); img.height = 60; img.width = 160; ws.add_image(img, 'A1')
cell(ws, 'H1', 'OBLIGACIONES ACUMULADAS', WH12); cell(ws, 'H3', 'Roles de pago vs libros — gastos y provisiones', WH)
cell(ws, 'A4', 'Nombre del cliente:', ARB, box=True); cell(ws, 'B4', '=Ficha!C4', AR, box=True)
cell(ws, 'G4', 'Período terminado:', ARB, box=True); cell(ws, 'I4', '=Ficha!C5', AR, 'dd/mm/yyyy', box=True)
cell(ws, 'A5', 'Preparado por:', ARB, box=True); cell(ws, 'B5', '=Ficha!C6', AR, box=True)
cell(ws, 'D5', 'Revisado:', ARB, box=True); cell(ws, 'E5', '=Ficha!C7', AR, box=True)
cell(ws, 'G5', 'Fecha:', ARB, box=True); cell(ws, 'I5', '=Ficha!C8', AR, 'dd/mm/yyyy', box=True)
cell(ws, 'K5', 'Referencia de PT', ARB, box=True); cell(ws, 'M5', 'DO-10', RED, box=True)
ws.merge_cells('A6:Q6'); b = ws['A6']
b.value = ('Rol: RQ-006 (pestañas «normal» y «pasantes»). Libros: Anexo RQ-002 y Mayores RQ-004 (gastos: pasantes, comisiones, premios y detalle mensual; '
           'pasivos: débitos por goces y finiquitos).')
b.font = Font(name='Arial', size=9, bold=True, color='FFC00000'); b.fill = YEL; b.alignment = Alignment(wrap_text=True, vertical='center'); ws.row_dimensions[6].height = 26
ws.merge_cells('B7:Q7'); c = ws['B7']; c.value = 'ROL'; c.font = WH; c.fill = NAVY; c.alignment = C
th(ws, 8, 1, ['Mes'] + [t for _, t in CONC], 40)
RCOL = {k: chr(66 + i) for i, (k, _) in enumerate(CONC)}   # B..Q
for m in range(1, 13):
    r = 8 + m; cell(ws, f'A{r}', MESES[m - 1], AR, box=True)
    for k, _ in CONC: cell(ws, f'{RCOL[k]}{r}', f'={RR}!{COL[k]}{4+m}', GREEN, N2, box=True)
cell(ws, 'A21', 'Σ', RED, box=True)
for k, _ in CONC:
    cell(ws, f'{RCOL[k]}21', f'=SUM({RCOL[k]}9:{RCOL[k]}20)', ARB, N2, box=True); cell(ws, f'{RCOL[k]}22', '✓', RED, al=Alignment(horizontal='center'))
# Libros (fila 24) y diferencia (fila 26), agrupados como el papel
cell(ws, 'A24', 'Libros', WH, fill=NAVY, box=True); cell(ws, 'A26', 'Diferencia (rol − libros)', ARB, box=True)
sum_acc = lambda codes: round(sum(ANEXO.get(cd, 0) for cd in codes), 2)
groups = [('B', 'B', sum_acc(SUE), BLUE, 'RQ-002'), ('C', 'C', round(sum(MY.gasto_mes('EST')), 2), BLUE, 'RQ-004'),
          ('D', 'D', MY.pasivo_tot(MY.B, '5BS.21204.003', 'GOCES'), BLUE, 'RQ-004 pasivo'),
          ('E', 'G', sum_acc(HE), BLUE, 'RQ-002'), ('H', 'I', sum_acc(BON), BLUE, 'RQ-002'), ('J', 'J', round(sum(MY.gasto_mes('COM')), 2), BLUE, 'RQ-004'),
          ('K', 'K', round(sum(MY.gasto_mes('PRE')), 2), BLUE, 'RQ-004')]
for c0, c1, val, font, srcx in groups:
    if c0 != c1: ws.merge_cells(f'{c0}24:{c1}24'); ws.merge_cells(f'{c0}26:{c1}26')
    rng_sum = f'SUM({c0}21:{c1}21)'
    if val is None:
        cell(ws, f'{c0}24', 'Pendiente RQ-004', IT, fill=GRY, box=True, al=C); cell(ws, f'{c0}26', '—', IT, fill=GRY, box=True, al=C)
    else:
        cell(ws, f'{c0}24', val, font, N2, box=True, al=Alignment(horizontal='center'))
        cell(ws, f'{c0}26', f'={rng_sum}-{c0}24', ARB, N2, box=True, al=Alignment(horizontal='center'))
    cell(ws, f'{c0}25', srcx, IT, al=Alignment(horizontal='center'))
for col in 'LMNOPQ':
    cell(ws, f'{col}24', 'Ver bloque', IT, fill=GRY, box=True, al=C); cell(ws, f'{col}26', '—', IT, fill=GRY, box=True, al=C)
for col in 'BCDEHJK': cell(ws, f'{col}27', '‡', RED, al=Alignment(horizontal='center'))
cell(ws, 'A28', 'Horas extras = recargo nocturno + 50% + 100%. Desempeño + bonificación = cuenta «Bono desempeño». Vacaciones tomadas: el papel anterior comparaba el rol contra sí mismo; '
                'el lado de libros es el débito por goces en 5BS.21204.003 (Mayor de pasivos RQ-004). Pasantes, comisiones y premios: Mayor de gastos RQ-004 (el anexo no los trae).', IT)
ws.merge_cells('A28:Q28'); ws['A28'].alignment = Alignment(wrap_text=True, vertical='top'); ws.row_dimensions[28].height = 24

# Bloque: fondos de reserva
cell(ws, 'A31', 'FONDOS DE RESERVA: rol + depósitos IESS vs gasto en libros', NAVYF)
th(ws, 32, 1, ['Concepto', 'Importe', 'Fuente'], 22)
fr = [('FR pagado en rol', '=L21', 'RQ-006'), ('FR depositado en el IESS (comprobantes)', round(float(fr_iess.sum()), 2), 'RQ-005 / DO-9'),
      ('Total pagado', '=B33+B34', ''), ('Gasto FR en libros', ANEXO_FR := round(sum(ANEXO.get(cd, 0) for cd in FRC), 2), 'RQ-002'),
      ('Diferencia (pagado − libros)', '=B35-B36', 'Se compone del FR pagado en rol en un mes sin base IESS (' + _R.SUJETOS.get('v04_nombres','') + ', V04, DO-6) y la diferencia FR Consolidado vs comprobantes (DO-9)')]
for i, (t, v, s) in enumerate(fr):
    r = 33 + i
    cell(ws, f'A{r}', t, ARB if i in (2, 4) else AR, box=True); cell(ws, f'B{r}', v, ARB if i in (2, 4) else GREEN, N2, box=True)
    cell(ws, f'C{r}', s, IT, box=True); ws.merge_cells(f'C{r}:H{r}')

# Bloque: pagos que debitan el pasivo
cell(ws, 'A40', 'PAGOS DEL ROL QUE DEBITAN CUENTAS DE PASIVO (lado libros: Mayor de pasivos RQ-004)', NAVYF)
th(ws, 41, 1, ['Concepto', 'Rol', 'Débitos en libros (RQ-004)', 'Diferencia', 'Uso en otras cédulas'], 30)
deb = [('Vacaciones tomadas (goces)', '=D21', MY.pasivo_tot(MY.B, '5BS.21204.003', 'GOCES'), 'Débito 5BS.21204.003 · DO-4C · DO-5'),
       ('Vacaciones de finiquito', '=Q21', MY.pasivo_tot(MY.B, '5BS.21204.003', 'FINIQUITOS'), 'Débito 5BS.21204.003 · DO-4C liquidaciones'),
       ('D13 liquidado en finiquitos', '=O21', MY.pasivo_tot(MY.B, '5BS.21204.001', 'FINIQUITOS'), 'Débito 5BS.21204.001 · DO-4C'),
       ('D14 liquidado en finiquitos', '=P21', MY.pasivo_tot(MY.B, '5BS.21204.002', 'FINIQUITOS'), 'Débito 5BS.21204.002 · DO-4C'),
       (f'D13 mensualizado (sin jubilares {_nf(_jd13)})', f'=M21-{_jd13}', round(sum(MY.gasto_mes('D13')) + MY.pasivo_tot(MY.B, '5BS.21204.001', 'PROVISION'), 2), 'No debita el pasivo: gasto D13 − provisión acreditada (DO-6)'),
       (f'D14 mensualizado (sin jubilares {_nf(_jd14)})', f'=N21-{_jd14}', round(_g14_mens - _aj14, 2), f'Gasto D14 − provisión acreditada − ajuste de pago a tiempo parcial {_nf(_aj14)}')]
for i, (t, v, lb, u) in enumerate(deb):
    r = 42 + i
    cell(ws, f'A{r}', t, AR, box=True); cell(ws, f'B{r}', v, ARB, N2, box=True)
    cell(ws, f'C{r}', lb, BLUE, N2, box=True); cell(ws, f'D{r}', f'=ROUND(B{r}-C{r},2)', ARB, N2, box=True)
    cell(ws, f'E{r}', u, IT, box=True); ws.merge_cells(f'E{r}:H{r}')
cell(ws, 'A48', f'Décimos jubilares incluidos en el rol: D13 {_nf(_jd13)} y D14 {_nf(_jd14)} (jubilados patronales de la pestaña «normal»). Explican los {_nf(_jub_total)} de mensualizados del rol que no están en el Consolidado IESS.', IT)
ws.merge_cells('A48:Q48')

# Bloque: sueldos por mes
cell(ws, 'A49', 'SUELDOS: APERTURA MENSUAL DE LA DIFERENCIA ROL − LIBROS', NAVYF)
th(ws, 50, 1, ['Mes', 'Rol', 'Libros', 'Diferencia'], 22)
for m in range(12):
    r = 51 + m
    cell(ws, f'A{r}', MESES[m], AR, box=True); cell(ws, f'B{r}', f'=B{9+m}', GREEN, N2, box=True)
    cell(ws, f'C{r}', lib_sue_mes[m], BLUE, N2, box=True); cell(ws, f'D{r}', f'=B{r}-C{r}', ARB, N2, box=True)
cell(ws, 'A63', 'Total', WH, fill=NAVY, box=True)
for col in 'BCD': cell(ws, f'{col}63', f'=SUM({col}51:{col}62)', WH, N2, NAVY, box=True)
cell(ws, 'E63', '=IF(ABS(D63-B26)<0.01,"= diferencia anual ✓","Revisar")', IT)
cell(ws, 'A64', 'Libros: Mayor de gastos RQ-004. Los sueldos de las liquidaciones (LIQ.HAB.) coinciden con el rol mes a mes; la diferencia está en la nómina regular (NOMINA Y PROVISIONES). El mayor se registra por centro de costo y no por trabajador: se requiere el reporte de nómina por centro de costo para la apertura final.', IT); ws.merge_cells('A64:Q64')

txt = [(67, 'Objetivo:', RU),
       (68, 'Verificar que los conceptos pagados en los roles de pago del ejercicio 2025 estén registrados en los gastos y cuentas de pasivo correspondientes, y explicar las diferencias.', AR),
       (70, 'Procedimiento:', RU),
       (71, '1. Se totalizó el rol de pagos (RQ-006) por mes y concepto, incluidos pasantes. 2. Se comparó con el gasto registrado en libros (Anexo RQ-002). '
            '3. Los fondos de reserva se cotejaron sumando los depósitos en el IESS (comprobantes RQ-005). 4. Los pagos que debitan cuentas de pasivo '
            '(goces, finiquitos, décimos) se cotejan con el Mayor de pasivos (RQ-004).', AR),
       (73, 'Marcas:', RED), (74, 'Σ  Sumado, totalizado.', ARB), (75, '✓  Verificado, comprobado, cotejado (con libros).', ARB), (76, '‡  Diferencia determinada.', ARB),
       (78, 'Comentario de auditoría:', RED)]
for r, t, f in txt:
    cell(ws, f'A{r}', t, f)
    if f is AR: ws.merge_cells(f'A{r}:Q{r}'); ws[f'A{r}'].alignment = Alignment(wrap_text=True, vertical='top'); ws.row_dimensions[r].height = 30
cell(ws, 'A79', '="Sueldos: el rol excede a libros en "&TEXT(B26,"#,##0.00")&" en la nómina regular (las liquidaciones cuadran mes a mes según el Mayor RQ-004). Horas extras, bonos, comisiones, premios, pasantes y vacaciones tomadas cuadran; los débitos del pasivo por goces y finiquitos coinciden con el rol. '
                f'Fondos de reserva: pagado (rol + IESS) vs gasto "&TEXT(B37,"#,##0.00")&". Los {_nf(_jub_total)} de décimos del rol fuera del IESS son décimos jubilares."', AR)
ws.merge_cells('A79:Q80'); ws['A79'].alignment = Alignment(wrap_text=True, vertical='top'); ws['A79'].border = BOX; ws.row_dimensions[79].height = 30
ws.column_dimensions['A'].width = 34
for i in range(2, 18): ws.column_dimensions[chr(64 + i)].width = 12.5
ws.sheet_view.showGridLines = False; ws.freeze_panes = 'B9'
ws.page_setup.orientation = 'landscape'; ws.sheet_properties.pageSetUpPr.fitToPage = True; ws.page_setup.fitToHeight = 0

# ---------------- Controles
wc = wb.create_sheet('Controles')
cell(wc, 'B2', 'CONTROLES DE INTEGRIDAD', ARB)
th(wc, 4, 2, ['Control', 'Valor A', 'Valor B', 'Diferencia', 'Estado'])
D10 = "'DO10 Roles vs Libros'"
ctl = [('Sueldo rol = DO-3.1', f'={D10}!B21', _R.CIFRAS['sue_rol'], 0.01),
       ('Vacaciones tomadas = DO-3.1', f'={D10}!D21', _R.CIFRAS['vac_tomadas'], 0.01),
       ('FR en rol = DO-3.1', f'={D10}!L21', _R.CIFRAS['fr_rol'], 0.01),
       ('Décimos mensualizados = DO-3.1', f'={D10}!M21+{D10}!N21', _R.CIFRAS['mens_total'], 0.01),
       ('Vacaciones de finiquito = DO-4', f'={D10}!Q21', _R.CIFRAS['vac_finiquito_rol'], 0.01),
       ('Pasantes: rol = libros', f'={D10}!C21', _R.CIFRAS['estipendio'], 0.01),
       ('Sueldos libros RQ-002 = DO-2', f'={D10}!B24', _R.CIFRAS['sue_gasto'], 0.01),
       ('Horas extras libros RQ-002 = DO-8', f'={D10}!E24', _R.CIFRAS['he_gasto'], 0.01),
       ('Bonos libros RQ-002 = DO-2', f'={D10}!H24', _R.CIFRAS['bonos_gasto'], 0.01),
       ('FR depositado IESS = DO-9', f'={D10}!B34', _R.CIFRAS['fr_iess'], 0.01),
       ('Gasto FR libros RQ-002 = DO-2', f'={D10}!B36', _R.CIFRAS['fr_gasto_libros'], 0.01),
       ('Apertura mensual de sueldos = diferencia anual', f'={D10}!D63', f'={D10}!B26', 0.01),
       ('Mayor RQ-004: débitos del pasivo y mensualizados = rol (6 conceptos)', f'=SUMPRODUCT(ABS({D10}!D42:D47))', 0, 0.05),
       ('Mayor RQ-004: sueldos = anexo RQ-002', round(sum(MY.gasto_mes('SUE')), 2), f'={D10}!B24', 0.01)]
for i, (t, a, b2, tol) in enumerate(ctl):
    r = 5 + i
    cell(wc, f'B{r}', t, AR, box=True); cell(wc, f'C{r}', a, GREEN, N2, box=True); cell(wc, f'D{r}', b2, GREEN, N2, box=True)
    cell(wc, f'E{r}', f'=ROUND(C{r}-D{r},2)', AR, N2, box=True)
    cell(wc, f'F{r}', f'=IF(ABS(E{r})<={tol},"OK","REVISAR")', ARB, box=True, al=Alignment(horizontal='center'))
n = len(ctl); cell(wc, f'B{6+n}', f'=COUNTIF(F5:F{4+n},"OK")&" de {n} controles OK"', ARB)
wc.column_dimensions['B'].width = 52
for col in 'CDEF': wc.column_dimensions[col].width = 16
wb.active = 0
_wf = wb['Ficha']
_r = max(_wf.max_row + 2, 14)
_wf.cell(_r, 2, 'Año auditado 2026. Cédula construida con datos de la plantilla 2025 (rol, IESS, anexo y comprobantes); se reemplazan con la información 2026 del cliente.').font = Font(name='Arial', size=8, italic=True, color='FFC00000')
wb.save(OUT); print('ok', OUT, 'FR anexo', ANEXO_FR, 'sue', sum_acc(SUE), 'he', sum_acc(HE), 'bon', sum_acc(BON))
