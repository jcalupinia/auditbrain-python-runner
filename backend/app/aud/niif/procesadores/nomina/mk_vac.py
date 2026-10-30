# -*- coding: utf-8 -*-
from backend.app.aud.niif.procesadores.nomina import rutas as _R
"""VAC — Calculadora de vacaciones no gozadas (liquidación hipotética al corte) y RQ-008 Kárdex de vacaciones.
Población: trabajadores activos al corte con derecho a beneficios (DO-4 Detalle RQ-003 / DO-3.1 maestro).
Sin kárdex: estado «NO SOPORTADO» → observación automática (visita preliminar).
Con kárdex: pasivo exigible = (días devengados desde el ingreso − días gozados o pagados) × remuneración de corte / 30;
ajuste total = pasivo − libros, separado en gasto del año auditado y resultados acumulados (NIC 8, años anteriores).
Uso: python3 mk_vac.py            → entregables
     python3 mk_vac.py DEMO <out> → copia de prueba con kárdex sintético (solo verificación)"""
import sys, random
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.drawing.image import Image as XLImage
from openpyxl.worksheet.datavalidation import DataValidation

DEMO = False  # pipeline integrado: siempre papel real
OUT = sys.argv[2] if DEMO else (_R.CTX.out + '/VAC_Calculadora_Vacaciones_No_Gozadas.xlsx')
OUT_RQ = (_R.CTX.out + '/RQ-008_Kardex_Vacaciones.xlsx')
cal = pd.read_pickle((_R.CTX.home + '/cal_base.pkl')).sort_values('Nombre').reset_index(drop=True)
N = len(cal)

NAVY = PatternFill('solid', fgColor='FF0F2341'); YEL = PatternFill('solid', fgColor='FFFFF2CC'); INP = PatternFill('solid', fgColor='FFFFFFE0')
AR = Font(name='Arial', size=10); ARB = Font(name='Arial', size=10, bold=True)
WH = Font(name='Arial', size=10, bold=True, color='FFFFFFFF'); WH12 = Font(name='Arial', size=12, bold=True, color='FFFFFFFF')
BLUE = Font(name='Arial', size=10, color='FF0000FF'); GREEN = Font(name='Arial', size=10, color='FF008000'); ORANGE = Font(name='Arial', size=10, color='FFC65911')
RED = Font(name='Arial', size=10, bold=True, color='FFC00000'); IT = Font(name='Arial', size=8, italic=True)
thin = Side(style='thin', color='FF000000'); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
N2 = '#,##0.00;(#,##0.00);"-"'; D2 = '0.00;(0.00);"-"'; DT = 'dd/mm/yyyy'
C = Alignment(horizontal='center', vertical='center', wrap_text=True); W = Alignment(wrap_text=True, vertical='top')

def cell(ws, ref, v, font=AR, fmt=None, fill=None, al=None, box=False):
    c = ws[ref]; c.value = v; c.font = font
    if fmt: c.number_format = fmt
    if fill: c.fill = fill
    if al: c.alignment = al
    if box: c.border = BOX
    return c

def th(ws, row, col0, labels, height=42):
    for i, t in enumerate(labels):
        c = ws.cell(row, col0 + i, t); c.font = WH; c.fill = NAVY; c.alignment = C; c.border = BOX
    ws.row_dimensions[row].height = height

def kardex_sheet(wb, title, demo=False):
    wk = wb.create_sheet(title)
    cell(wk, 'B2', 'KÁRDEX DE VACACIONES — RQ-008 (lo entrega el cliente; una fila por trabajador activo al corte)', ARB)
    cell(wk, 'B3', 'Celdas amarillas: días según kárdex. Dejar en blanco si no hay registro: la calculadora marca al trabajador como NO SOPORTADO.', IT)
    th(wk, 5, 2, ['N°', 'Cédula', 'Nombre', 'Fecha de ingreso', 'Días gozados o pagados desde el ingreso hasta el cierre anterior',
                  'Días gozados en el año auditado', 'Días pagados en dinero en el año auditado', 'Fuente / observación'], 54)
    rnd = random.Random(7)
    for i, w in cal.iterrows():
        r = 6 + i
        cell(wk, f'B{r}', i + 1, AR, box=True); cell(wk, f'C{r}', w['Cédula'], AR, box=True); cell(wk, f'D{r}', w['Nombre'], AR, box=True)
        cell(wk, f'E{r}', w['ingreso'].to_pydatetime(), AR, DT, box=True)
        for col in 'FGH':
            cell(wk, f'{col}{r}', None, BLUE, D2, INP, box=True)
        cell(wk, f'I{r}', None, BLUE, fill=INP, box=True)
        if demo and i % 9 != 0:     # 1 de cada 9 queda sin kárdex para probar el estado mixto
            yrs = (pd.Timestamp('2025-12-31') - w['ingreso']).days / 365
            wk[f'F{r}'].value = round(max(0, yrs * 15 - rnd.uniform(0, 20)), 2)
            wk[f'G{r}'].value = rnd.choice([0, 5, 8, 10, 15]); wk[f'H{r}'].value = rnd.choice([0, 0, 0, 3])
            wk[f'I{r}'].value = 'DEMO sintético'
    wk.column_dimensions['A'].width = 2; wk.column_dimensions['B'].width = 5; wk.column_dimensions['C'].width = 13
    wk.column_dimensions['D'].width = 40; wk.column_dimensions['E'].width = 12
    for col in 'FGH': wk.column_dimensions[col].width = 18
    wk.column_dimensions['I'].width = 30; wk.freeze_panes = 'E6'
    return wk

# ======================================================================= Calculadora
wb = Workbook()
# Fecha de corte real del ejercicio (de la ficha). En cierre calendario es 31-dic (histórico);
# en visita preliminar, el mes/día del corte (p. ej. 31-jul).
_mc = _R.CTX.mes_corte if _R.CTX else 12
_cc = _R.CTX.corte if (_R.CTX and _R.CTX.corte) else ''
_dia = int(_cc[8:10]) if len(_cc) >= 10 and _cc[8:10].isdigit() else 31
wf = wb.active; wf.title = 'Ficha'
cell(wf, 'B2', 'FICHA DEL ENCARGO Y PARÁMETROS DE LA CALCULADORA', ARB)
pars = [('Cliente', _R.CTX.cliente, None, BLUE),
        ('Año auditado', _R.CTX.ejercicio, '0', BLUE),
        ('Fecha de corte', f'=DATE(C5,{_mc},{_dia})', DT, AR),
        ('Fecha de cierre anterior', '=DATE(C5-1,12,31)', DT, AR),
        ('Preparado por', _R.CTX.preparado, None, BLUE), ('Revisado por', _R.CTX.revisado, None, BLUE), ('Fecha', '=TODAY()', DT, AR),
        ('Días de vacaciones por año (art. 69 CT)', 15, '0', BLUE),
        ('Incluir días adicionales desde el 6.º año (art. 69 CT)', 'Sí', None, BLUE),
        ('Máximo de días adicionales por año', 15, '0', BLUE),
        ('Divisor de valoración (remuneración mensual / días)', 30, '0', BLUE),
        ('Tope de acumulación en años (criterio del socio: 5; 0 = sin tope)', 5, '0', BLUE),
        ('Saldo vacaciones por pagar en libros al corte (5BS.21204.003)', _R.CIFRAS['vac_libros'], N2, BLUE),
        ('Saldo vacaciones por pagar en libros al cierre anterior', _R.CIFRAS['sal_ini_vac'], N2, BLUE),
        ('Base del valor día', 'Remuneración de corte', None, BLUE)]
for i, (k, v, f, fo) in enumerate(pars):
    r = 4 + i
    cell(wf, f'B{r}', k, ARB, box=True, al=W); cell(wf, f'C{r}', v, fo, f, box=True)
P = {k: f'Ficha!$C${4+i}' for i, (k, *_ ) in enumerate(pars)}
YR, FC, FA = P['Año auditado'], P['Fecha de corte'], P['Fecha de cierre anterior']
DPA, ADI, MXA, DIV, TOP = (P['Días de vacaciones por año (art. 69 CT)'], P['Incluir días adicionales desde el 6.º año (art. 69 CT)'],
                           P['Máximo de días adicionales por año'], P['Divisor de valoración (remuneración mensual / días)'],
                           P['Tope de acumulación en años (criterio del socio: 5; 0 = sin tope)'])
L1, L0 = P['Saldo vacaciones por pagar en libros al corte (5BS.21204.003)'], P['Saldo vacaciones por pagar en libros al cierre anterior']
BAS = P['Base del valor día']
ALT = 'Promedio 12 meses (art. 71)'
dv = DataValidation(type='list', formula1='"Sí,No"', allow_blank=False); wf.add_data_validation(dv); dv.add('C12')
dvb = DataValidation(type='list', formula1='"Remuneración de corte,Promedio 12 meses (art. 71)"', allow_blank=False); wf.add_data_validation(dvb); dvb.add('C18')
cell(wf, 'B19', 'Año auditado 2026. Los datos de trabajadores y remuneraciones provienen de la plantilla 2025 (DO-3.1 / DO-4) y se reemplazan con el '
     'rol y el maestro de 2026. Saldos de libros: Anexo RQ-002, conciliados con el Mayor de pasivos RQ-004.', IT)
wf.merge_cells('B19:C21'); wf['B19'].alignment = W
wf.column_dimensions['B'].width = 62; wf.column_dimensions['C'].width = 18

wk = kardex_sheet(wb, 'Kárdex RQ-008', DEMO)
KX = "'Kárdex RQ-008'"

ws = wb.create_sheet('VAC Calculadora', 0)
for r in range(1, 4):
    for col in range(1, 24): ws.cell(r, col).fill = NAVY
ws.row_dimensions[1].height = 34; ws.row_dimensions[2].height = 22
img = XLImage(_R.CTX.logo); img.height = 60; img.width = 160; ws.add_image(img, 'A1')
cell(ws, 'H1', 'OBLIGACIONES ACUMULADAS', WH12); cell(ws, 'H3', 'Vacaciones no gozadas — liquidación hipotética al corte', WH)
cell(ws, 'A4', 'Nombre del cliente:', ARB, box=True); cell(ws, 'C4', '=Ficha!C4', AR, box=True)
cell(ws, 'G4', 'Período terminado:', ARB, box=True); cell(ws, 'I4', f'={FC}', AR, DT, box=True)
cell(ws, 'K4', 'Año auditado:', ARB, box=True); cell(ws, 'L4', f'={YR}', RED, '0', box=True)
cell(ws, 'A5', 'Preparado por:', ARB, box=True); cell(ws, 'C5', '=Ficha!C8', AR, box=True)
cell(ws, 'D5', 'Revisado:', ARB, box=True); cell(ws, 'E5', '=Ficha!C9', AR, box=True)
cell(ws, 'G5', 'Fecha:', ARB, box=True); cell(ws, 'I5', '=Ficha!C10', AR, DT, box=True)
cell(ws, 'K5', 'Referencia de PT', ARB, box=True); cell(ws, 'L5', 'DO-4V', RED, box=True)
ws.merge_cells('A6:Q6'); b = ws['A6']
b.value = ('Fuente de días: Kárdex de vacaciones RQ-008 (pestaña «Kárdex RQ-008»). Remuneración de corte en naranja: base imponible de diciembre de la '
           'plantilla, provisional hasta la remuneración vigente aprobada al corte. Sin kárdex, el trabajador queda NO SOPORTADO y no se valora.')
b.font = Font(name='Arial', size=9, bold=True, color='FFC00000'); b.fill = YEL; b.alignment = Alignment(wrap_text=True, vertical='center'); ws.row_dimensions[6].height = 28

# ---- Resumen (filas 8-24)
R0 = 30; R1 = R0 + N - 1; RT = R1 + 1
rng = lambda col: f'{col}{R0}:{col}{R1}'
cell(ws, 'A8', 'RESUMEN Y AJUSTE PROPUESTO', WH, fill=NAVY); ws.merge_cells('A8:F8')
summ = [('Trabajadores activos al corte (población 100%)', f'=COUNTA({rng("B")})', '0'),
        ('Con kárdex completo', f'=COUNTIF({rng("N")},"Sí")', '0'),
        ('Sin kárdex (no soportados)', '=E9-E10', '0'),
        ('Pasivo exigible según calculadora al corte (a)', f'=SUM({rng("P")})', N2),
        ('Saldo en libros al corte (b)', f'={L1}', N2),
        ('Ajuste total propuesto (a) − (b)', '=IF(E11>0,"No concluyente",ROUND(E12-E13,2))', N2),
        ('Pasivo correcto al cierre anterior (c)', f'=SUM({rng("O")})', N2),
        ('Saldo en libros al cierre anterior (d)', f'={L0}', N2),
        ('Ajuste a resultados acumulados (c) − (d)  [NIC 8]', '=IF(E11>0,"No concluyente",ROUND(E15-E16,2))', N2),
        ('Ajuste al gasto del año auditado [(a) − (c)] − [(b) − (d)]', '=IF(E11>0,"No concluyente",ROUND((E12-E15)-(E13-E16),2))', N2),
        ('Control: resultados acumulados + gasto = ajuste total', '=IF(E11>0,"n/a hasta completar el kárdex",IF(ABS(E17+E18-E14)<0.01,"OK","REVISAR"))', None),
        ('Estado de la prueba', '=IF(E10=0,"NO SOPORTADO — sin kárdex: observación OBS-VAC (visita preliminar)",IF(E11>0,"PARCIAL — "&E11&" trabajadores sin kárdex: pasivo no concluyente","CALCULADO — pasivo y ajuste concluyentes (visita final)"))', None)]
for i, (t, f, fmt) in enumerate(summ):
    r = 9 + i
    ws.merge_cells(f'A{r}:D{r}'); cell(ws, f'A{r}', t, ARB if i in (5, 8, 9, 11) else AR, box=True)
    c = cell(ws, f'E{r}', f, RED if i in (5, 8, 9, 11) else AR, fmt, box=True)
ws.merge_cells('E20:Q20'); ws['E20'].alignment = Alignment(wrap_text=False)
cell(ws, 'A22', 'Asiento propuesto (se habilita cuando todos los trabajadores tienen kárdex):', ARB)
cell(ws, 'A23', 'Resultados acumulados — corrección de años anteriores', AR); cell(ws, 'E23', '=IF(E11>0,0,E17)', AR, N2)
cell(ws, 'A24', 'Gasto vacaciones del año auditado (prorrata por centro de costo, DO-12)', AR); cell(ws, 'E24', '=IF(E11>0,0,E18)', AR, N2)
cell(ws, 'A25', 'Vacaciones por pagar (5BS.21204.003)', AR); cell(ws, 'E25', '=IF(E11>0,0,-E14)', AR, N2)
cell(ws, 'F23', 'Positivo = débito; negativo = crédito. El pasivo se ajusta al importe exigible al corte.', IT)
cell(ws, 'A26', '="Base del valor día aplicada: "&'+BAS, ARB)
cell(ws, 'A27', 'Pasivo con la base alternativa (referencial)', AR); cell(ws, 'E27', f'=SUM({rng("X")})', AR, N2)
cell(ws, 'F27', 'Base por defecto: remuneración de corte / 30 (decisión del socio). Alternativa art. 71 CT: promedio de lo percibido en los últimos 12 meses (incluye horas extras, sin décimos) / 30.', IT)

# ---- Detalle
th(ws, R0 - 1, 1, ['N°', 'Cédula', 'Nombre', 'Fecha de ingreso', 'Remuneración mensual al corte', 'Remuneración al cierre anterior',
                   'Años completos al corte', 'Días devengados desde ingreso al cierre anterior', 'Días devengados desde ingreso al corte',
                   'Días gozados o pagados hasta cierre anterior (kárdex)', 'Días gozados o pagados en el año (kárdex)',
                   'Saldo de días al cierre anterior', 'Saldo de días al corte', '¿Kárdex?', 'Pasivo al cierre anterior', 'Pasivo exigible al corte',
                   'Estado', 'Años (ant.)', 'Fracción (ant.)', 'Años (corte)', 'Fracción (corte)', 'Días año en curso (corte)',
                   'Remuneración promedio 12 meses (art. 71)', 'Pasivo con la base alternativa'], 66)
cell(ws, f'A{R0-2}', 'DETALLE POR TRABAJADOR — 100% de la población activa', WH, fill=NAVY); ws.merge_cells(f'A{R0-2}:Q{R0-2}')

def dev(d, yc, fc):   # días devengados acumulados desde el ingreso hasta la fecha: completos + proporción del año en curso
    m = f'MIN(MAX({yc}-5,0),{MXA})'
    add = f'IF({ADI}="Sí",{m}*({m}+1)/2+{MXA}*MAX({yc}-5-{MXA},0),0)'
    cur = f'({DPA}+IF({ADI}="Sí",MIN(MAX({yc}-4,0),{MXA}),0))'
    return f'=ROUND({DPA}*{yc}+{add}+{cur}*{fc},2)'

for i, w in cal.iterrows():
    r = R0 + i; k = 6 + i
    cell(ws, f'A{r}', i + 1, AR, box=True)
    cell(ws, f'B{r}', f'={KX}!C{k}', GREEN, box=True); cell(ws, f'C{r}', f'={KX}!D{k}', GREEN, box=True)
    cell(ws, f'D{r}', f'={KX}!E{k}', GREEN, DT, box=True)
    cell(ws, f'E{r}', round(float(w['base_dic']), 2), ORANGE, N2, box=True)
    cell(ws, f'F{r}', f'=E{r}', BLUE, N2, box=True)
    # auxiliares R..V
    cell(ws, f'R{r}', f'=IF({FA}<D{r},0,DATEDIF(D{r},{FA},"y"))', AR, '0', box=True)
    cell(ws, f'S{r}', f'=IF({FA}<D{r},0,({FA}-EDATE(D{r},12*R{r}))/365)', AR, '0.0000', box=True)
    cell(ws, f'T{r}', f'=IF({FC}<D{r},0,DATEDIF(D{r},{FC},"y"))', AR, '0', box=True)
    cell(ws, f'U{r}', f'=IF({FC}<D{r},0,({FC}-EDATE(D{r},12*T{r}))/365)', AR, '0.0000', box=True)
    cell(ws, f'V{r}', f'={DPA}+IF({ADI}="Sí",MIN(MAX(T{r}-4,0),{MXA}),0)', AR, '0', box=True)
    cell(ws, f'G{r}', f'=T{r}', AR, '0', box=True)
    cell(ws, f'H{r}', dev(f'D{r}', f'R{r}', f'S{r}'), AR, D2, box=True)
    cell(ws, f'I{r}', dev(f'D{r}', f'T{r}', f'U{r}'), AR, D2, box=True)
    cell(ws, f'J{r}', f'=IF({KX}!F{k}="","",{KX}!F{k})', GREEN, D2, box=True)
    cell(ws, f'K{r}', f'=IF(AND({KX}!G{k}="",{KX}!H{k}=""),"",N({KX}!G{k})+N({KX}!H{k}))', GREEN, D2, box=True)
    cell(ws, f'N{r}', f'=IF(AND(J{r}<>"",K{r}<>""),"Sí","No")', ARB, box=True, al=Alignment(horizontal='center'))
    cell(ws, f'L{r}', f'=IF(N{r}="Sí",IF({TOP}>0,MIN(H{r}-J{r},{TOP}*V{r}),H{r}-J{r}),"")', AR, D2, box=True)
    cell(ws, f'M{r}', f'=IF(N{r}="Sí",IF({TOP}>0,MIN(I{r}-J{r}-K{r},{TOP}*V{r}),I{r}-J{r}-K{r}),"")', AR, D2, box=True)
    cell(ws, f'O{r}', f'=IF(N{r}="Sí",ROUND(L{r}*F{r}/{DIV},2),0)', AR, N2, box=True)
    cell(ws, f'W{r}', round(float(w['prom']), 2), ORANGE, N2, box=True)
    cell(ws, f'P{r}', f'=IF(N{r}="Sí",ROUND(M{r}*IF({BAS}="{ALT}",W{r},E{r})/{DIV},2),0)', ARB, N2, box=True)
    cell(ws, f'X{r}', f'=IF(N{r}="Sí",ROUND(M{r}*IF({BAS}="{ALT}",E{r},W{r})/{DIV},2),0)', AR, N2, box=True)
    cell(ws, f'Q{r}', f'=IF(N{r}="No","No soportado",IF(M{r}<0,"Revisar: saldo negativo",IF(AND({TOP}>0,I{r}-J{r}-K{r}>{TOP}*V{r}),"Tope aplicado: "&{TOP}&" períodos",IF(M{r}>{DPA}*3,"Acumula más de 3 períodos (art. 75)","Conforme"))))', AR, box=True)
cell(ws, f'A{RT}', 'TOTAL', RED, box=True)
for col in 'EFHIJKLMOPWX':
    cell(ws, f'{col}{RT}', f'=SUM({rng(col)})', ARB, N2, box=True)

# ---- Objetivo / procedimiento / marcas
t = RT + 2
txt = [('Objetivo:', ARB),
       ('Determinar el pasivo exigible por vacaciones no gozadas al corte, como si cada trabajador activo saliera ese día (liquidación hipotética, '
        'arts. 69, 71 y 76 del Código del Trabajo), y el ajuste al saldo contable separado entre el gasto del año auditado y los resultados acumulados.', AR),
       ('Procedimiento:', ARB),
       ('1. Visita preliminar: se solicita el Kárdex de vacaciones (RQ-008). Si no se entrega, la prueba queda NO SOPORTADA y se genera la observación OBS-VAC '
        '(debilidad de control: el pasivo por vacaciones no tiene respaldo por trabajador).', AR),
       ('2. Visita final: con el kárdex, para el 100% de los trabajadores activos se calculan los días devengados desde la fecha de ingreso '
        '(15 días por año, más un día adicional por cada año desde el sexto, con máximo de 15 adicionales) hasta el cierre anterior y hasta el corte.', AR),
       ('3. Se restan los días gozados o pagados según kárdex y se obtiene el saldo de días; se valora con la remuneración mensual vigente al corte / 30 (por defecto) o con el promedio de los últimos 12 meses / 30 (art. 71 CT: 1/24 de lo percibido); la cédula presenta la otra base como referencia.', AR),
       ('4. Ajuste total = pasivo exigible − saldo en libros. Porción de años anteriores: pasivo correcto al cierre anterior − saldo en libros a esa fecha '
        '(corrección de error, NIC 8, contra resultados acumulados). El resto es gasto del año auditado.', AR),
       ('5. El saldo de días se limita a 5 períodos anuales (criterio del socio; parámetro editable en Ficha). Se revisan los trabajadores con saldo negativo (días anticipados), con más de tres períodos acumulados (art. 75 CT) o con el tope aplicado.', AR),
       ('Marcas:  ✓ Verificado con kárdex · a) Recálculo de auditoría · ‡ Diferencia determinada.', AR)]
for i, (s, f) in enumerate(txt):
    ws.merge_cells(f'A{t+i}:Q{t+i}'); c = cell(ws, f'A{t+i}', s, f, al=W)
    if len(s) > 120: ws.row_dimensions[t + i].height = 28
widths = {'A': 5, 'B': 12, 'C': 34, 'D': 11, 'E': 13, 'F': 13, 'G': 8, 'H': 12, 'I': 12, 'J': 12, 'K': 12, 'L': 11, 'M': 11, 'N': 8,
          'O': 13, 'P': 13, 'Q': 22, 'R': 7, 'S': 8, 'T': 7, 'U': 8, 'V': 8, 'W': 14, 'X': 14}
for k2, v in widths.items(): ws.column_dimensions[k2].width = v
for col in 'RSTUV': ws.column_dimensions[col].outlineLevel = 1
ws.sheet_view.showGridLines = False; ws.freeze_panes = f'D{R0}'
ws.page_setup.orientation = 'landscape'; ws.sheet_properties.pageSetUpPr.fitToPage = True; ws.page_setup.fitToHeight = 0

# ---- Controles
wc = wb.create_sheet('Controles')
cell(wc, 'B2', 'CONTROLES DE INTEGRIDAD', ARB)
th(wc, 4, 2, ['Control', 'Valor A', 'Valor B', 'Diferencia', 'Estado'], 30)
VC = "'VAC Calculadora'"
ctl = [('Población = trabajadores activos con beneficios (DO-4: 140)', f'={VC}!E9', N, 0),
       ('Filas del kárdex = filas de la calculadora', f'=COUNTA({KX}!C6:C{5+N})', f'={VC}!E9', 0),
       ('Resultados acumulados + gasto = ajuste total', f'=N({VC}!E17)+N({VC}!E18)', f'=N({VC}!E14)', 0.01),
       ('Pasivo calculado = Σ por trabajador', f'={VC}!E12', f'={VC}!P{RT}', 0.01),
       ('Saldo libros al corte = DO-4C', f'={VC}!E13', _R.CIFRAS['vac_libros'], 0.01),
       ('Saldo libros cierre anterior = DO-4C', f'={VC}!E16', _R.CIFRAS['sal_ini_vac'], 0.01),
       ('Asiento cuadra (débitos = créditos)', f'={VC}!E23+{VC}!E24+{VC}!E25', 0, 0.01)]
for i, (tt, a, b2, tol) in enumerate(ctl):
    r = 5 + i
    cell(wc, f'B{r}', tt, AR, box=True); cell(wc, f'C{r}', a, GREEN, N2, box=True); cell(wc, f'D{r}', b2, GREEN, N2, box=True)
    cell(wc, f'E{r}', f'=ROUND(C{r}-D{r},2)', AR, N2, box=True)
    cell(wc, f'F{r}', f'=IF(ABS(E{r})<={tol},"OK","REVISAR")', ARB, box=True, al=Alignment(horizontal='center'))
n = len(ctl); cell(wc, f'B{6+n}', f'=COUNTIF(F5:F{4+n},"OK")&" de {n} controles OK"', ARB)
wc.column_dimensions['B'].width = 56
for col in 'CDEF': wc.column_dimensions[col].width = 16
wb.active = 0
wb.save(OUT); print('ok', OUT, N, 'filas', R0, R1)

# ======================================================================= RQ-008 modelo
if not DEMO:
    wr = Workbook(); wi = wr.active; wi.title = 'Instrucciones'
    ins = ['RQ-008 — KÁRDEX DE VACACIONES (modelo para el cliente)',
           '',
           'Qué entregar: el kárdex de vacaciones de cada trabajador activo al 31 de diciembre del año auditado.',
           'Una fila por trabajador. La lista ya viene precargada con cédula, nombre y fecha de ingreso según el rol.',
           'Columna F: total de días de vacaciones gozados o pagados desde la fecha de ingreso hasta el 31 de diciembre del año anterior.',
           'Columna G: días gozados durante el año auditado (según solicitudes y rol).',
           'Columna H: días pagados en dinero durante el año auditado (sin goce).',
           'Columna I: fuente (sistema de nómina, kárdex físico, solicitudes) u observaciones.',
           '',
           'Uso en auditoría: el auditor pega estas columnas en la pestaña «Kárdex RQ-008» de la calculadora VAC (DO-4V).',
           'Si no se entrega el kárdex en la visita preliminar se emite la observación OBS-VAC (pasivo por vacaciones sin respaldo por trabajador).',
           '',
           'Ejemplo ilustrativo (pestaña «Ejemplo»): cómo se obtiene el pasivo de un trabajador.']
    for i, s in enumerate(ins): cell(wi, f'B{2+i}', s, ARB if i == 0 else AR)
    wi.column_dimensions['B'].width = 120
    kardex_sheet(wr, 'Kárdex', False)
    we = wr.create_sheet('Ejemplo')
    cell(we, 'B2', 'EJEMPLO ILUSTRATIVO — un trabajador (datos ficticios)', ARB)
    ex = [('Fecha de ingreso', pd.Timestamp('2018-03-01').to_pydatetime(), DT, BLUE),
          ('Fecha de corte', pd.Timestamp(_R.CTX.corte).to_pydatetime(), DT, BLUE),
          ('Remuneración mensual vigente al corte', 1200, N2, BLUE),
          ('Años completos al corte', '=DATEDIF(C4,C5,"y")', '0', AR),
          ('Fracción del año en curso', '=(C5-EDATE(C4,12*C7))/365', '0.0000', AR),
          ('Días adicionales acumulados (desde el 6.º año)', '=MIN(MAX(C7-5,0),15)*(MIN(MAX(C7-5,0),15)+1)/2', D2, AR),
          ('Días del año en curso (15 + adicional)', '=15+MIN(MAX(C7-4,0),15)', '0', AR),
          ('Días devengados desde el ingreso', '=ROUND(15*C7+C9+C10*C8,2)', D2, ARB),
          ('Días gozados o pagados según kárdex', 100, D2, BLUE),
          ('Saldo de días no gozados', '=C11-C12', D2, ARB),
          ('Valor día (remuneración / 30)', '=C6/30', N2, AR),
          ('Pasivo exigible al corte (liquidación hipotética)', '=ROUND(C13*C14,2)', N2, RED)]
    for i, (k, v, f, fo) in enumerate(ex):
        cell(we, f'B{4+i}', k, ARB, box=True); cell(we, f'C{4+i}', v, fo, f, box=True)
    we.column_dimensions['B'].width = 50; we.column_dimensions['C'].width = 16
    wr.active = 1
    wr.save(OUT_RQ); print('ok', OUT_RQ)
