# -*- coding: utf-8 -*-
from backend.app.aud.niif.procesadores.nomina import rutas as _R
"""DO-4 Cruce Global del Pasivo de Beneficios + DO-5 Cruce Mensual del Pasivo.
Formato: papel de trabajo «DO - Pasivos Acumulados.xlsx» (pestañas DO4 Cruc Global / DO5 Cruce MensPasivo).
Auditoría: DO-4 v3 (Detalle RQ-003, con exclusiones) + rol DO-3.1. Libros: valores del papel de trabajo
(provisional, hasta automatizar con los mayores RQ-004)."""
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.drawing.image import Image as XLImage

OUT = (_R.CTX.out + '/DO-4C_DO-5_Cruce_Pasivo_Beneficios.xlsx')
g = pd.read_pickle((_R.CTX.home + '/g.pkl'))

from backend.app.aud.niif.procesadores.nomina import mayores as MY
rm = pd.read_pickle((_R.CTX.home + '/rol_mes.pkl'))
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
# Período auditado = enero … mes de corte (de la ficha). Diciembre (MC=12) = cierre calendario:
# comportamiento histórico. Otro mes = visita preliminar: el cruce de décimos se hace sobre el
# período transcurrido, no sobre diciembre/agosto-diciembre.
MC = _R.CTX.mes_corte if _R.CTX else 12
PRELIM = MC != 12
LP = 4 + MC                 # fila de «Insumo Auditoría» del mes de corte (meses en filas 5..16)
MES_CORTE_TXT = MESES[MC - 1]
_ANIO = _R.CTX.anio_corte if _R.CTX else 2025
_CC = _R.CTX.corte if (_R.CTX and _R.CTX.corte) else ''
_DIA = int(_CC[8:10]) if len(_CC) >= 10 and _CC[8:10].isdigit() else 31
FECHA_CORTE_TXT = f'{_DIA} de {MES_CORTE_TXT.lower()} de {_ANIO}'
PERIODO_TXT = f'enero a {MES_CORTE_TXT.lower()} de {_ANIO}'

NAVY = PatternFill('solid', fgColor='FF0F2341'); SUB = PatternFill('solid', fgColor='FFDDE6F3')
YEL = PatternFill('solid', fgColor='FFFFF2CC')
AR = Font(name='Arial', size=10); ARB = Font(name='Arial', size=10, bold=True)
WH = Font(name='Arial', size=10, bold=True, color='FFFFFFFF'); WH12 = Font(name='Arial', size=12, bold=True, color='FFFFFFFF')
BLUE = Font(name='Arial', size=10, color='FF0000FF'); GREEN = Font(name='Arial', size=10, color='FF008000')
RED = Font(name='Arial', size=10, bold=True, color='FFC00000'); RU = Font(name='Arial', size=10, bold=True, color='FFC00000', underline='single')
IT = Font(name='Arial', size=8, italic=True)
thin = Side(style='thin', color='FF000000'); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
N2 = '#,##0.00;(#,##0.00);"-"'; PC = '0.0%;(0.0%);"-"'
C = Alignment(horizontal='center', vertical='center', wrap_text=True)


def banner(ws, last_col, texto):
    ORANGE = Font(name='Arial', size=9, bold=True, color='FFC00000')
    ws.merge_cells(start_row=6, start_column=2, end_row=6, end_column=last_col)
    c = ws.cell(6, 2, texto); c.font = ORANGE; c.fill = PatternFill('solid', fgColor='FFFFF2CC')
    c.alignment = Alignment(wrap_text=True, vertical='center'); ws.row_dimensions[6].height = 26

wb = Workbook()

def cell(ws, ref, v, font=AR, fmt=None, fill=None, al=None, box=False):
    c = ws[ref]; c.value = v; c.font = font
    if fmt: c.number_format = fmt
    if fill: c.fill = fill
    if al: c.alignment = al
    if box: c.border = BOX
    return c

def header(ws, titulo, ref_pt, last_col):
    for r in range(1, 4):
        for col in range(2, last_col + 1):
            ws.cell(r, col).fill = NAVY
    ws.row_dimensions[1].height = 34; ws.row_dimensions[2].height = 22
    img = XLImage(_R.CTX.logo); img.height = 60; img.width = 160
    ws.add_image(img, 'B1')
    mid = chr(64 + (2 + last_col) // 2 + 1)
    cell(ws, f'{mid}1', 'OBLIGACIONES ACUMULADAS', WH12)
    cell(ws, f'{mid}3', titulo, WH)
    L = chr(64 + last_col)
    cell(ws, 'B4', 'Nombre del cliente:', ARB, box=True); cell(ws, 'C4', '=Ficha!C4', AR, box=True)
    cell(ws, 'F4', 'Período terminado:', ARB, box=True); cell(ws, 'G4', '=Ficha!C5', AR, 'dd/mm/yyyy', box=True)
    cell(ws, 'B5', 'Preparado por:', ARB, box=True); cell(ws, 'C5', '=Ficha!C6', AR, box=True)
    cell(ws, 'D5', 'Revisado:', ARB, box=True); cell(ws, 'E5', '=Ficha!C7', AR, box=True)
    cell(ws, 'F5', 'Fecha:', ARB, box=True); cell(ws, 'G5', '=Ficha!C8', AR, 'dd/mm/yyyy', box=True)
    cell(ws, f'{chr(64 + last_col - 1)}5', 'Referencia de PT', ARB, box=True)
    cell(ws, f'{L}5', ref_pt, RED, box=True)

def th(ws, row, col0, labels, height=30):
    for i, t in enumerate(labels):
        c = ws.cell(row, col0 + i, t); c.font = WH; c.fill = NAVY; c.alignment = C; c.border = BOX
    ws.row_dimensions[row].height = height

# ---------------------------------------------------------------- Ficha
wf = wb.active; wf.title = 'Ficha'
cell(wf, 'B2', 'FICHA DEL ENCARGO (encabezado de las cédulas)', ARB)
for i, (k, v) in enumerate([('Cliente', _R.CTX.cliente), ('Período terminado', pd.Timestamp(_R.CTX.corte).to_pydatetime()),
                            ('Preparado por', _R.CTX.preparado), ('Revisado por', _R.CTX.revisado), ('Fecha', None)]):
    cell(wf, f'B{4+i}', k, ARB, box=True); c = cell(wf, f'C{4+i}', v, BLUE, box=True)
    if i in (1, 4): c.number_format = 'dd/mm/yyyy'
wf['C8'] = '=TODAY()'; wf['C8'].font = AR
wf.column_dimensions['B'].width = 22; wf.column_dimensions['C'].width = 30
cell(wf, 'B10', 'Celdas en azul: insumo editable. En la integración al Command Center se alimentan desde la Ficha del encargo.', IT)

# ---------------------------------------------------------------- Libros
wl = wb.create_sheet('Libros')
cell(wl, 'B2', 'SALDOS Y PROVISIONES SEGÚN LIBROS — Anexo RQ-002 y Mayor de pasivos RQ-004', ARB)
cell(wl, 'B3', 'Saldos ESF y saldo inicial: Anexo de nómina RQ-002 (5BS.21204). Provisiones mensuales: créditos por provisión del Mayor de pasivos RQ-004 '
               '(concepto DECIMO 13 / DECIMO 14 S / VACACIONES).', IT)
th(wl, 5, 2, ['Código', 'Cuenta', 'Saldo ESF 31-dic-2025', 'Saldo inicial 31-dic-2024', 'Fuente'])
# Saldos del Anexo RQ-002 (MY.ANEXO[cta] = (saldo inicial con signo, saldo ESF con signo)); se toma el valor absoluto.
esf = [(cta, nom, round(abs(MY.ANEXO[cta][1]), 2), round(abs(MY.ANEXO[cta][0]), 2), 'RQ-002 Anexo de nómina')
       for cta, nom in [('5BS.21204.001', 'Décimo Tercer Sueldo'), ('5BS.21204.002', 'Décimo Cuarto Quito'),
                        ('5BS.21204.003', 'Vacaciones')]]
for i, (a, b, s, si, f) in enumerate(esf):
    r = 6 + i
    cell(wl, f'B{r}', a, AR, box=True); cell(wl, f'C{r}', b, AR, box=True)
    cell(wl, f'D{r}', s, BLUE, N2, box=True); cell(wl, f'E{r}', si, BLUE, N2, box=True); cell(wl, f'F{r}', f, IT, box=True)
cell(wl, 'B10', 'Mayor de pasivos RQ-004 · provisiones del mes (crédito)', Font(name='Arial', size=9, bold=True, color='FF1F3864'))
th(wl, 11, 2, ['Mes', 'Provisión D13 (libros)', 'Provisión D14 (libros)', 'Provisión vacaciones (libros)'])
_p13 = [-v for v in MY.pasivo_mes(MY.B, '5BS.21204.001', 'PROVISION')]; _p14 = [-v for v in MY.pasivo_mes(MY.B, '5BS.21204.002', 'PROVISION')]
lib13 = {12: _p13[11]} if not PRELIM else {m: _p13[m - 1] for m in range(1, MC + 1)}
lib14 = {m: _p14[m - 1] for m in range(8, 13)} if not PRELIM else {m: _p14[m - 1] for m in range(1, MC + 1)}
libv = [-v for v in MY.pasivo_mes(MY.B, '5BS.21204.003', 'PROVISION')]
for m in range(1, 13):
    r = 11 + m
    cell(wl, f'B{r}', MESES[m - 1], AR, box=True)
    cell(wl, f'C{r}', lib13.get(m), BLUE, N2, box=True); cell(wl, f'D{r}', lib14.get(m), BLUE, N2, box=True)
    cell(wl, f'E{r}', libv[m - 1], BLUE, N2, box=True)
cell(wl, 'B24', 'Σ', RED, box=True)
for col in 'CDE':
    cell(wl, f'{col}24', f'=SUM({col}12:{col}23)', ARB, N2, box=True)
cell(wl, 'B25', ('D13: se cruza diciembre (pasivo del período dic–nov). D14 Sierra: agosto a diciembre (período ago–jul). Vacaciones: enero a diciembre.'
                 if not PRELIM else
                 f'Visita preliminar — período auditado {PERIODO_TXT}: D13, D14 y vacaciones se cruzan por el devengado de ese período (no por el ciclo de cierre de diciembre).'), IT)
# --- Movimiento anual según Mayor RQ-004
cell(wl, 'B28', 'MOVIMIENTO DEL AÑO SEGÚN MAYOR DE PASIVOS RQ-004 (débito +, crédito −)', ARB)
th(wl, 29, 2, ['Cuenta', 'Saldo inicial (RQ-002)', 'Provisión', 'Pagos', 'Finiquitos (liquidaciones)', 'Goces (vacaciones tomadas)', 'Ajustes y otros', 'Saldo final calculado', 'Saldo ESF', 'Diferencia'], 40)
for i, (cta, nom) in enumerate([('5BS.21204.001', 'Décimo tercero'), ('5BS.21204.002', 'Décimo cuarto'), ('5BS.21204.003', 'Vacaciones')]):
    r = 30 + i
    cell(wl, f'B{r}', nom, AR, box=True); cell(wl, f'C{r}', MY.ANEXO[cta][0], BLUE, N2, box=True)
    for col, cl in zip('DEFGH', ['PROVISION', 'PAGOS', 'FINIQUITOS', 'GOCES', 'AJUSTES']):
        cell(wl, f'{col}{r}', MY.pasivo_tot(MY.B, cta, cl), BLUE, N2, box=True)
    cell(wl, f'I{r}', f'=SUM(C{r}:H{r})', ARB, N2, box=True); cell(wl, f'J{r}', MY.ANEXO[cta][1], BLUE, N2, box=True)
    cell(wl, f'K{r}', f'=ROUND(I{r}-J{r},2)', ARB, N2, box=True)
cell(wl, 'B34', 'COTEJO DE DÉBITOS DEL MAYOR CON EL ROL DE PAGOS (DO-3.1)', ARB)
th(wl, 35, 2, ['Concepto', 'Mayor RQ-004', 'Rol DO-3.1', 'Diferencia'], 24)
cot = [('Vacaciones tomadas (goces)', '=G32', float(rm['VAC TOMADAS'].sum())), ('Vacaciones de finiquito', '=F32', float(rm['VAC.FINIQUIT'].sum())),
       ('D13 de finiquitos (LIQ.DEC13)', '=F30', float(rm['LIQ.DEC13'].sum())), ('D14 de finiquitos (LIQ.DEC14S)', '=F31', float(rm['LIQ.DEC14S'].sum()))]
for i, (t, a, b) in enumerate(cot):
    r = 36 + i
    cell(wl, f'B{r}', t, AR, box=True); cell(wl, f'C{r}', a, GREEN, N2, box=True); cell(wl, f'D{r}', round(b, 2), GREEN, N2, box=True)
    cell(wl, f'E{r}', f'=ROUND(C{r}-D{r},2)', ARB, N2, box=True)
cell(wl, 'B41', 'Ajustes y otros — detalle: compensación de cuentas por cobrar a empleados (CIERRE.CXC.EMPLEADO), retenciones judiciales y reversos; '
               'ajustes de pago en D14; y en vacaciones un ajuste de actualización del sistema (débito al pasivo contra el gasto), reverso y redondeos.', IT)
for col, w in zip('GHIJK', [16, 16, 16, 16, 12]): wl.column_dimensions[col].width = w
for col, w in zip('ABCDEF', [2, 16, 26, 26, 28, 34]): wl.column_dimensions[col].width = w

# ---------------------------------------------------------------- Insumo Auditoría
wi = wb.create_sheet('Insumo Auditoría')
cell(wi, 'B2', 'INSUMO DE AUDITORÍA POR MES — DO-4 Reproceso v3 (Detalle RQ-003, con exclusiones del auditor) y rol DO-3.1', ARB)
cols = ['Mes', 'D13 devengado bruto', 'D13 pago mensual (rol)', 'D13 devengado salidos (finiquito)',
        'D14 devengado bruto (Sierra)', 'D14 pago mensual (rol)', 'D14 devengado salidos (finiquito)',
        'Vacaciones provisión', 'Vacaciones gozadas (rol)', 'Vacaciones de finiquito (rol)']
th(wi, 4, 2, cols, 44)
src = ['d13b', 'D13 mens. pagado (rol)', 'd13f', 'd14b', 'D14 mens. pagado (rol)', 'd14f', 'Vacaciones', 'Vac. gozadas (rol)', 'Vac. finiquito (rol)']
for m in range(1, 13):
    r = 4 + m
    cell(wi, f'B{r}', MESES[m - 1], AR, box=True)
    for j, s in enumerate(src):
        cell(wi, f'{chr(67 + j)}{r}', float(g.loc[float(m), s]), GREEN, N2, box=True)
cell(wi, 'B17', 'Σ', RED, box=True)
for j in range(9):
    col = chr(67 + j); cell(wi, f'{col}17', f'=SUM({col}5:{col}16)', ARB, N2, box=True)
notas = ['Fuente (verde = vínculo a otro papel de trabajo):',
         '• D13 bruto = base IESS / 12 de trabajadores con beneficio, sin exclusiones del auditor (incluye mensualizados).',
         '• D14 bruto = SBU 470 / 360 × días, región Sierra, sin exclusiones.',
         '• Pago mensual y vacaciones gozadas/finiquito: rol de pagos pestaña «normal» (DO-3.1).',
         '• Devengado de salidos: lo devengado en el período por trabajadores inactivos al 31-dic que acumulaban (se liquida en su finiquito).',
         '• Vacaciones provisión = base / 24, sin exclusiones.']
for k, t in enumerate(notas):
    cell(wi, f'B{19+k}', t, IT)
cell(wi, 'B26', 'Pasivo según DO-4 Reproceso v3 (control de cuadre)', ARB)
for k, (b, v) in enumerate([('Décimo tercero', _R.CIFRAS['pasivo_d13_rep']), ('Décimo cuarto', _R.CIFRAS['pasivo_d14_rep']), ('Vacaciones', _R.CIFRAS['vac_reproc'])]):
    cell(wi, f'B{27+k}', b, AR, box=True); cell(wi, f'C{27+k}', v, GREEN, N2, box=True)
wi.column_dimensions['A'].width = 2; wi.column_dimensions['B'].width = 14
for j in range(9): wi.column_dimensions[chr(67 + j)].width = 17
wi.freeze_panes = 'C5'

# ---------------------------------------------------------------- DO4 Cruce Global
w4 = wb.create_sheet('DO4 Cruce Global Pasivo', 0)
header(w4, 'Beneficios sociales Pasivos — Cruce global', 'DO-4C', 12)
_aviso_prelim = (f'VISITA PRELIMINAR · período auditado {PERIODO_TXT}. El cruce de décimos y vacaciones se hace sobre el devengado de ese período (no sobre el cierre calendario de diciembre). '
                 if PRELIM else '')
banner(w4, 12, _aviso_prelim + 'Fuente de libros: Anexo de nómina RQ-002 (saldos) conciliado con el Mayor de pasivos RQ-004. Partidas conciliatorias: rol DO-3.1, cotejado con los débitos del mayor.')
th(w4, 8, 2, ['Código', 'Cuenta', 'Según ESF', 'Según Auditoría', 'Diferencia', 'Liquidaciones', 'Ajuste',
              'Finiquito', 'Pago mensual', 'Total diferencia', '%'])
IA = "'Insumo Auditoría'"
# D13/D14 «según auditoría»: en cierre calendario se cruza diciembre (D13) y agosto–diciembre
# (D14 Sierra); en visita preliminar, el devengado del período auditado (enero…mes de corte).
if PRELIM:
    _c13 = (f'=SUM({IA}!C5:C{LP})', f'=SUM({IA}!E5:E{LP})', f'=SUM({IA}!D5:D{LP})')
    _c14 = (f'=SUM({IA}!F5:F{LP})', f'=SUM({IA}!H5:H{LP})', f'=SUM({IA}!G5:G{LP})')
else:
    _c13 = (f'={IA}!C16', f'={IA}!E16', f'={IA}!D16')
    _c14 = (f'=SUM({IA}!F12:F16)', f'=SUM({IA}!H12:H16)', f'=SUM({IA}!G12:G16)')
rows4 = [
    ('5BS.21204.001', 'Décimo Tercer Sueldo', '=Libros!D6', _c13[0], 0, '0', _c13[1], _c13[2]),
    ('5BS.21204.002', 'Décimo Cuarto Quito', '=Libros!D7', _c14[0], 0, '0', _c14[1], _c14[2]),
    ('5BS.21204.003', 'Vacaciones', '=Libros!D8', f'=Libros!E8+{IA}!I17', f'={IA}!K17', '0', 0, f'={IA}!J17'),
]
for i, (cod, cta, esf_f, aud, liq, aj, fin, pm) in enumerate(rows4):
    r = 9 + i
    cell(w4, f'B{r}', cod, AR, box=True); cell(w4, f'C{r}', '    ' + cta, AR, box=True)
    cell(w4, f'D{r}', esf_f, GREEN, N2, box=True)
    cell(w4, f'E{r}', aud, GREEN, N2, box=True)
    cell(w4, f'F{r}', f'=D{r}-E{r}', AR, N2, box=True)
    cell(w4, f'G{r}', liq, GREEN if isinstance(liq, str) else AR, N2, box=True)
    cell(w4, f'H{r}', 0, BLUE, N2, box=True, fill=YEL)
    cell(w4, f'I{r}', fin, GREEN if isinstance(fin, str) else AR, N2, box=True)
    cell(w4, f'J{r}', pm, GREEN, N2, box=True)
    cell(w4, f'K{r}', f'=F{r}+G{r}+H{r}+I{r}+J{r}', ARB, N2, box=True)
    cell(w4, f'L{r}', f'=IF(D{r}=0,0,K{r}/D{r})', AR, PC, box=True)
r = 12
cell(w4, f'B{r}', 'TOTAL', WH, fill=NAVY, box=True); w4.merge_cells('B12:C12'); w4['B12'].alignment = C
for col in 'DEFGHIJK':
    cell(w4, f'{col}{r}', f'=SUM({col}9:{col}11)', WH, N2, NAVY, box=True)
cell(w4, 'L12', '=IF(D12=0,0,K12/D12)', WH, PC, NAVY, box=True)
for col in 'DEK':
    cell(w4, f'{col}13', {'D': '√', 'E': 'a)', 'K': '‡'}[col], RED, al=Alignment(horizontal='center'))

cell(w4, 'B15', 'Conciliación con el pasivo de la DO-4 Reproceso v3', ARB)
th(w4, 16, 2, ['Cuenta', '', 'Neto auditoría (cruce)', 'Pasivo DO-4', 'Diferencia', 'Explicación'], 22)
expl = ['Mensualizados: D13 bruto (base/12) vs pago en rol',
        'Mensualizados D14: devengado vs pago en rol',
        'Debe ser cero']
for i, cta in enumerate(['Décimo tercero', 'Décimo cuarto', 'Vacaciones']):
    r = 17 + i
    cell(w4, f'B{r}', cta, AR, box=True); w4.merge_cells(f'B{r}:C{r}')
    cell(w4, f'D{r}', f'=E{9+i}-G{9+i}-H{9+i}-I{9+i}-J{9+i}', AR, N2, box=True)
    cell(w4, f'E{r}', f"={IA}!C{27+i}", GREEN, N2, box=True)
    cell(w4, f'F{r}', f'=ROUND(D{r}-E{r},2)', AR, N2, box=True)
    cell(w4, f'G{r}', expl[i], IT, box=True); w4.merge_cells(f'G{r}:L{r}')

txt = [
    (22, 'Objetivo:', RU),
    (23, 'Verificar que el saldo de las obligaciones acumuladas por beneficios sociales (décimo tercero, décimo cuarto y vacaciones) '
         f'presentado en el estado de situación financiera al {FECHA_CORTE_TXT} esté adecuadamente sustentado y valorado.', AR),
    (25, 'Procedimiento:', RU),
    (26, '1. Se tomó el saldo de cada cuenta según el ESF (cédula sumaria DO-2).', AR),
    (27, '2. Se determinó el pasivo bruto según auditoría con el reproceso DO-4 sobre el 100% del Consolidado IESS (RQ-003): '
         + ('D13 devengado de diciembre; D14 Sierra devengado de agosto a diciembre; vacaciones = saldo inicial + provisión del año.'
            if not PRELIM else
            f'devengado del período auditado ({PERIODO_TXT}) para D13, D14 y vacaciones (visita preliminar).'), AR),
    (28, '3. Se identificaron las partidas que reducen el pasivo según el rol de pagos (DO-3.1): vacaciones de finiquito (liquidaciones), '
         'devengado de trabajadores salidos (finiquito) y pagos mensuales (décimos mensualizados y vacaciones gozadas).', AR),
    (29, '4. Se aplicaron las exclusiones del auditor (RQ-003 Exclusiones) y se determinó la diferencia neta (Total diferencia).', AR),
    (30, '5. La columna Ajuste (amarilla) admite partidas con sustento documentado; por defecto es cero.', AR),
    (32, 'Marcas:', RED),
    (33, '√  Verificado, comprobado, cotejado (con libros).', ARB),
    (34, '‡  Diferencia determinada.', ARB),
    (35, 'a)  Recálculo de auditoría.', ARB),
    (37, 'Comentario de auditoría:', RED),
]
for r, t, f in txt:
    cell(w4, f'B{r}', t, f)
    if f is AR: w4.merge_cells(f'B{r}:L{r}'); w4[f'B{r}'].alignment = Alignment(wrap_text=True, vertical='top'); w4.row_dimensions[r].height = 28
cell(w4, 'B38', '=IF(ABS(K11)>ABS(D11)*0.05,"Vacaciones: el pasivo en libros excede el recálculo en "&TEXT(K11,"#,##0.00")&" ("&TEXT(L11,"0.0%")&"). '
                'Provisión del cliente a una tasa superior a 1/24 (4,17%): evaluar ajuste. D13 y D14: diferencias menores.","Diferencias dentro de lo razonable.")', AR)
w4.merge_cells('B38:L39'); w4['B38'].alignment = Alignment(wrap_text=True, vertical='top'); w4['B38'].border = BOX
for col, wd in zip('ABCDEFGHIJKL', [2, 16, 24, 14, 15, 14, 14, 11, 12, 14, 15, 8]): w4.column_dimensions[col].width = wd

# ---------------------------------------------------------------- DO5 Cruce Mensual
w5 = wb.create_sheet('DO5 Cruce Mensual Pasivo', 1)
header(w5, 'Conciliación mensual pasivo beneficios sociales', 'DO-5', 9)
banner(w5, 9, 'Fuente de libros: Mayor de pasivos RQ-004 (provisiones mensuales) y Anexo RQ-002 (saldos). El mayor se concilia con el anexo en la pestaña «Libros».')
D4 = "'DO4 Cruce Global Pasivo'"
_d13_meses = (lambda m: m <= MC) if PRELIM else (lambda m: m == 12)
_d14_meses = (lambda m: m <= MC) if PRELIM else (lambda m: m >= 8)
_nota13 = (f'Libros (enero–{MES_CORTE_TXT.lower()}) − neto de auditoría del período auditado.' if PRELIM
           else 'Libros (diciembre) − neto de auditoría; las salidas no generan pasivo en diciembre.')
blocks = [('Décimo tercer sueldo', 9, 'C', lambda m: f"={IA}!C{4+m}-{IA}!D{4+m}" if _d13_meses(m) else None, 9, _nota13),
          ('Décimo cuarto sueldo', 28, 'D', lambda m: f"={IA}!F{4+m}-{IA}!G{4+m}" if _d14_meses(m) else None, 10,
           'Libros registra la provisión bruta y descarga el finiquito al liquidar; la diferencia de cierre (col. G) es finiquito libros vs auditoría.'),
          ('Vacaciones', 47, 'E', lambda m: f"={IA}!I{4+m}", 11,
           'Se cruza la provisión mensual. La diferencia de cierre (col. G) son los débitos de la cuenta en libros vs goces y finiquitos del rol.')]
for titulo, r0, lcol, faud, krow, nota in blocks:
    cell(w5, f'B{r0}', titulo, ARB)
    th(w5, r0 + 1, 2, ['Mes', 'Libros', 'Auditoría', 'Diferencia'], 20)
    for m in range(1, 13):
        r = r0 + 1 + m
        cell(w5, f'B{r}', MESES[m - 1], AR, box=True)
        cell(w5, f'C{r}', f'=IF(Libros!{lcol}{11+m}="","",Libros!{lcol}{11+m})', GREEN, N2, box=True)
        a = faud(m); cell(w5, f'D{r}', a if a else '', GREEN, N2, box=True)
        cell(w5, f'E{r}', f'=N(C{r})-N(D{r})', AR, N2, box=True)
    rt = r0 + 14
    cell(w5, f'B{rt}', 'Total', WH, fill=NAVY, box=True)
    for col in 'CDE':
        cell(w5, f'{col}{rt}', f'=SUM({col}{r0+2}:{col}{rt-1})', WH, N2, NAVY, box=True)
    cell(w5, f'F{r0+1}', 'DO-4C Total dif.', WH, fill=NAVY, al=C, box=True)
    cell(w5, f'G{r0+1}', 'Por conciliar', WH, fill=NAVY, al=C, box=True)
    cell(w5, f'F{rt}', f'={D4}!K{krow}', GREEN, N2, box=True)
    cell(w5, f'G{rt}', f'=ROUND(E{rt}-F{rt},2)', ARB, N2, box=True)
    cell(w5, f'B{rt+1}', nota, IT); w5.merge_cells(f'B{rt+1}:I{rt+1}')

# Explicación de las partidas por conciliar
cell(w5, 'B66', 'EXPLICACIÓN DE LAS DIFERENCIAS POR CONCILIAR (col. G)', ARB)
th(w5, 67, 2, ['Concepto', '', '', 'Libros', 'Auditoría', 'Diferencia'], 20)
expl5 = [
    ('D14: finiquitos ago–dic (libros = provisión − saldo ESF)', '=C42-Libros!D7', f'={D4}!I10+{D4}!G10'),
    ('Vacaciones: débitos del año (libros = saldo inicial + provisión − saldo ESF)', '=Libros!E8+C61-Libros!D8', f'={D4}!J11+{D4}!G11'),
]
for i, (t, lb, au) in enumerate(expl5):
    r = 68 + i
    cell(w5, f'B{r}', t, AR, box=True); w5.merge_cells(f'B{r}:D{r}')
    cell(w5, f'E{r}', lb, AR, N2, box=True); cell(w5, f'F{r}', au, GREEN, N2, box=True)
    cell(w5, f'G{r}', f'=ROUND(E{r}-F{r},2)', ARB, N2, box=True)
cell(w5, 'H68', '=IF(ABS(G68-G42)<0.05,"Explica col. G D14 ✓","Revisar")', IT)
cell(w5, 'H69', '=IF(ABS(G69-G61)<0.05,"Explica col. G vacaciones ✓","Revisar")', IT)
cell(w5, 'B71', '="Mayor RQ-004: los débitos de vacaciones son goces "&TEXT(Libros!G32,"#,##0.00")&" + finiquitos "&TEXT(Libros!F32,"#,##0.00")&" (iguales al rol) + ajustes "&TEXT(Libros!H32,"#,##0.00")&"; los ajustes explican la diferencia de la col. G."', IT)
w5.merge_cells('B71:I71')

txt5 = [(74, 'Objetivo:', RU),
        (75, 'Verificar mes a mes la provisión registrada en libros por beneficios sociales contra el recálculo de auditoría y conciliar el cierre con el cruce global (DO-4C).', AR),
        (77, 'Procedimiento:', RU),
        (78, ('1. Se tomaron las provisiones mensuales según libros (D13: diciembre; D14 Sierra: agosto a diciembre; vacaciones: enero a diciembre).'
              if not PRELIM else
              f'1. Se tomaron las provisiones mensuales según libros del período auditado ({PERIODO_TXT}).'), AR),
        (79, '2. Se compararon con el recálculo mensual de auditoría neto de pagos mensualizados (DO-4 Reproceso y rol DO-3.1).', AR),
        (80, '3. El total de cada beneficio se concilia con el «Total diferencia» del cruce global; lo no conciliado se explica en el bloque de partidas por conciliar.', AR),
        (82, 'Marcas:', RED), (83, '√  Verificado, comprobado, cotejado (con libros).', ARB),
        (84, '‡  Diferencia determinada.', ARB), (85, 'a)  Recálculo de auditoría.', ARB),
        (87, 'Comentario de auditoría:', RED)]
for r, t, f in txt5:
    cell(w5, f'B{r}', t, f)
    if f is AR: w5.merge_cells(f'B{r}:I{r}'); w5[f'B{r}'].alignment = Alignment(wrap_text=True, vertical='top'); w5.row_dimensions[r].height = 28
w5.merge_cells('B88:I89'); w5['B88'].border = BOX
for col, wd in zip('ABCDEFGHI', [2, 16, 16, 16, 16, 16, 14, 26, 12]): w5.column_dimensions[col].width = wd

# ---------------------------------------------------------------- Controles
wc = wb.create_sheet('Controles')
cell(wc, 'B2', 'CONTROLES DE INTEGRIDAD', ARB)
th(wc, 4, 2, ['Control', 'Valor A', 'Valor B', 'Diferencia', 'Estado'])
ctl = [
    ('D13 neto del cruce = pasivo DO-4 (tolerancia mensualizados 0,05)', f'={D4}!D17', f'={D4}!E17', 0.05),
    ('D14 neto del cruce = pasivo DO-4 (tolerancia 0,10)', f'={D4}!D18', f'={D4}!E18', 0.10),
    ('Vacaciones neto del cruce = pasivo DO-4', f'={D4}!D19', f'={D4}!E19', 0.01),
    ('ESF del cruce = saldos DO-2', f'={D4}!D12', _R.CIFRAS['esf_do2'], 0.01),
    ('D13 mensual: cierre con cruce global', "='DO5 Cruce Mensual Pasivo'!G23", 0, 0.01),
    ('D14 mensual: col. G explicada por finiquitos', "='DO5 Cruce Mensual Pasivo'!G42", "='DO5 Cruce Mensual Pasivo'!G68", 0.05),
    ('Vacaciones mensual: col. G explicada por débitos del año', "='DO5 Cruce Mensual Pasivo'!G61", "='DO5 Cruce Mensual Pasivo'!G69", 0.05),
    ('Vacaciones provisión auditoría = DO-4', f"={IA}!I17", _R.CIFRAS['provision_vac_anual'], 0.05),
    ('Mayor RQ-004: saldo inicial + movimientos = ESF (3 cuentas)', '=SUM(Libros!K30:K32)', 0, 0.01),
    ('Mayor RQ-004: goces y finiquitos = rol (4 conceptos)', '=SUMPRODUCT(ABS(Libros!E36:E39))', 0, 0.01),
    ('D13 bruto anual = reproceso', f"={IA}!C17", _R.CIFRAS['d13_bruto'], 0.05),
]
for i, (t, a, b, tol) in enumerate(ctl):
    r = 5 + i
    cell(wc, f'B{r}', t, AR, box=True); cell(wc, f'C{r}', a, GREEN, N2, box=True); cell(wc, f'D{r}', b, GREEN, N2, box=True)
    cell(wc, f'E{r}', f'=ROUND(C{r}-D{r},2)', AR, N2, box=True)
    cell(wc, f'F{r}', f'=IF(ABS(E{r})<={tol},"OK","REVISAR")', ARB, box=True, al=Alignment(horizontal='center'))
cell(wc, f'B{6+len(ctl)}', f'=COUNTIF(F5:F{4+len(ctl)},"OK")&" de {len(ctl)} controles OK"', ARB)
wc.column_dimensions['B'].width = 62
for col in 'CDEF': wc.column_dimensions[col].width = 16

for ws in (w4, w5):
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = 'landscape'; ws.page_setup.fitToWidth = 1; ws.sheet_properties.pageSetUpPr.fitToPage = True
wb.active = 0
_wf = wb['Ficha']
_r = max(_wf.max_row + 2, 14)
_wf.cell(_r, 2, 'Año auditado 2026. Cédula construida con datos de la plantilla 2025 (rol, IESS, anexo y comprobantes); se reemplazan con la información 2026 del cliente.').font = Font(name='Arial', size=8, italic=True, color='FFC00000')
wb.save(OUT)
print('ok', OUT)
