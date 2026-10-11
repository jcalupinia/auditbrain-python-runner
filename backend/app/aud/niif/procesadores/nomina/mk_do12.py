# -*- coding: utf-8 -*-
from backend.app.aud.niif.procesadores.nomina import rutas as _R
"""DO-12 Hoja de hallazgos y ajustes. Formato del papel de referencia (No. · Observación · Ref. PT · Recomendación), ampliado a
condición–criterio–causa–efecto (USD) según su procedimiento, con ajustes propuestos, resumen NIA 450 y observaciones para la carta."""
import json, pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.drawing.image import Image as XLImage
from openpyxl.worksheet.datavalidation import DataValidation

OUT = (_R.CTX.out + '/DO-12_Hallazgos_y_Ajustes.xlsx')
ANEXO = {str(r[0]).strip(): (str(r[1]).strip(), abs(r[5])) for r in load_workbook(_R.CTX.anexo, data_only=True).active.iter_rows(min_row=4, values_only=True)
         if r[0] and isinstance(r[5], (int, float))}
s6 = load_workbook(_R.CTX.papel, data_only=True)['DO6 Cruce Gsto Benefi.']
VAC = [(s6.cell(r, 2).value, str(s6.cell(r, 3).value).strip(), float(s6.cell(r, 4).value or 0)) for r in range(102, 125) if s6.cell(r, 2).value]

NAVY = PatternFill('solid', fgColor='FF0F2341'); SUB = PatternFill('solid', fgColor='FFDDE6F3'); YEL = PatternFill('solid', fgColor='FFFFF2CC')
GRN = PatternFill('solid', fgColor='FFE2EFDA'); ORG = PatternFill('solid', fgColor='FFFCE4D6'); RSF = PatternFill('solid', fgColor='FFF8D7DA')
AR = Font(name='Arial', size=9); ARB = Font(name='Arial', size=9, bold=True); WH = Font(name='Arial', size=9, bold=True, color='FFFFFFFF')
WH12 = Font(name='Arial', size=12, bold=True, color='FFFFFFFF'); BLUE = Font(name='Arial', size=9, color='FF0000FF'); GREEN = Font(name='Arial', size=9, color='FF008000')
ORANGE = Font(name='Arial', size=9, color='FFC65911')
RED = Font(name='Arial', size=9, bold=True, color='FFC00000'); RU = Font(name='Arial', size=10, bold=True, color='FFC00000', underline='single')
NAVYF = Font(name='Arial', size=10, bold=True, color='FF1F3864'); IT = Font(name='Arial', size=8, italic=True)
thin = Side(style='thin', color='FF9E9E9E'); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
N2 = '#,##0.00;(#,##0.00);"-"'; PC = '0.0%;(0.0%);"-"'
WR = Alignment(wrap_text=True, vertical='top'); C = Alignment(horizontal='center', vertical='center', wrap_text=True)

def cell(ws, ref, v, font=AR, fmt=None, fill=None, al=None, box=False):
    c = ws[ref]; c.value = v; c.font = font
    if fmt: c.number_format = fmt
    if fill: c.fill = fill
    if al: c.alignment = al
    if box: c.border = BOX
    return c

def th(ws, row, col0, labels, h=30):
    for i, t in enumerate(labels):
        c = ws.cell(row, col0 + i, t); c.font = WH; c.fill = NAVY; c.alignment = C; c.border = BOX
    ws.row_dimensions[row].height = h

def header(ws, titulo, ncol, ref='DO-12'):
    for r in range(1, 4):
        for col in range(1, ncol + 1): ws.cell(r, col).fill = NAVY
    ws.row_dimensions[1].height = 34; ws.row_dimensions[2].height = 20
    img = XLImage(_R.CTX.logo); img.height = 56; img.width = 150; ws.add_image(img, 'A1')
    ws.cell(1, 4, 'OBLIGACIONES ACUMULADAS').font = WH12; ws.cell(3, 4, titulo).font = WH
    cell(ws, 'A4', 'Nombre del cliente:', ARB, box=True); cell(ws, 'B4', '=Ficha!C4', AR, box=True)
    cell(ws, 'C4', 'Período terminado:', ARB, box=True); cell(ws, 'D4', '=Ficha!C5', AR, 'dd/mm/yyyy', box=True)
    cell(ws, 'A5', 'Preparado por:', ARB, box=True); cell(ws, 'B5', '=Ficha!C6', AR, box=True)
    cell(ws, 'C5', 'Revisado por:', ARB, box=True); cell(ws, 'D5', '=Ficha!C7', AR, box=True)
    ws.cell(4, ncol - 1, 'Referencia de PT').font = ARB; ws.cell(4, ncol, ref).font = RED
    ws.cell(5, ncol - 1, 'Fecha').font = ARB; c = ws.cell(5, ncol, '=Ficha!C8'); c.font = AR; c.number_format = 'dd/mm/yyyy'

# ================================================================= HALLAZGOS
_S = _R.SUJETOS; _C = _R.CIFRAS
_n = lambda v: f"{v:,.2f}".translate(str.maketrans({',': '.', '.': ','}))
# (titulo, condicion, criterio, causa, efecto_txt, importe, ref, clasif, recomendacion, carta?)
H = [
 ('Provisión de vacaciones en exceso',
  'El pasivo por vacaciones al corte (' + _n(_C['vac_libros']) + ') excede el recálculo de auditoría (' + _n(_C['vac_reproc']) + '). El cliente provisiona una tasa superior a 1/24 (4,17%). No se entregó el kárdex de vacaciones por trabajador (RQ-008): el pasivo no puede validarse como liquidación hipotética al corte (DO-4V: NO SOPORTADO).',
  'Código del Trabajo, arts. 69, 71 y 76: 15 días anuales (1/24 de lo percibido), días adicionales desde el sexto año y pago de las no gozadas a la salida; NIC 19 (beneficios acumulables) y NIC 8 (corrección de años anteriores).', 'Tasa de provisión configurada en el sistema de nómina superior a la legal; no se concilia el saldo con un kárdex de vacaciones por trabajador.',
  'Pasivo y gasto sobrestimados en ' + _n(_C['vac_exceso']) + '. El ajuste definitivo se determina con la calculadora DO-4V al recibir el kárdex: porción de años anteriores contra resultados acumulados y el resto contra el gasto del año.', _C['vac_exceso'], 'DO-4C / DO-5 / DO-6', 'Ajuste contable',
  'Ajustar la provisión a 1/24 de la remuneración; mantener un kárdex de días devengados, gozados y pendientes por trabajador; valorar el saldo al cierre como liquidación hipotética con la remuneración vigente y conciliarlo mensualmente con la contabilidad.', True),
 ('Fondos de reserva pagados a representantes legales',
  'Se pagaron en rol fondos de reserva por ' + _n(_C['excluido_fr']) + ' a ' + _S.get('excluidos','') + ' (representantes legales / administradores), afiliados con código 06.',
  'Los fondos de reserva corresponden a trabajadores en relación de dependencia (Código del Trabajo, art. 196). Quien ejerce la representación legal con poder general es mandatario y no empleado (art. 308): no genera fondos de reserva ni décimos por ese vínculo y se afilia con código 109 (sin relación de dependencia, aporte 17,6% a cargo de la empresa). Exclusión EX-02 documentada por el auditor.',
  'La nómina trata a los administradores como empleados del Código del Trabajo al afiliarlos con código 06.',
  'Gasto de fondos de reserva sobrestimado en ' + _n(_C['excluido_fr']) + ' (sin efecto en el resultado si se reclasifica a remuneración). Afiliación con código 06 en lugar del 109: inconsistencia ante el IESS y riesgo de reclamos por beneficios del Código del Trabajo.', _C['excluido_fr'], 'DO-4 V11 / DO-6', 'Reclasificación',
  'Confirmar con asesoría legal la naturaleza del vínculo; reclasificar el valor pagado como remuneración de administradores y regularizar el código de relación de trabajo ante el IESS (109).', True),
 ('Base gravada del rol mayor que la reportada al IESS',
  'La base gravada según el rol excede la base reportada en las planillas del IESS en ' + _n(_C['rol_menos_iess']) + '.',
  'Ley de Seguridad Social, art. 11: la materia gravada comprende todo ingreso del trabajador por la prestación de servicios.',
  'Conceptos gravados en el rol que no se incluyen en la planilla de aportes (variables, retroactivos o ajustes registrados fuera de período).',
  'Posible subdeclaración de aportes, más intereses y glosas del IESS.', _C['rol_menos_iess'], 'DO-3.1 / DO-8', 'Cumplimiento IESS',
  'Revisar por trabajador los conceptos no reportados y presentar planillas de ajuste ante el IESS.', True),
 ('Sueldos del rol mayores que el gasto en libros',
  'El total de sueldos pagados en roles (' + _n(_C['sue_rol']) + ') excede el gasto registrado (' + _n(_C['sue_gasto']) + ') en ' + _n(_C['sue_exceso']) + '. El mayor se registra por centro de costo, no por trabajador.',
  'Los gastos de remuneraciones deben registrarse íntegramente y en el período en que se devengan.', 'El mayor de gastos (RQ-004) no tiene detalle por trabajador: falta el reporte de nómina por centro de costo para identificar los trabajadores y meses con diferencia.',
  'Gasto de sueldos potencialmente subestimado en ' + _n(_C['sue_exceso']) + '.', _C['sue_exceso'], 'DO-10', 'Por conciliar',
  'Conciliar mensualmente el rol de pagos con el registro contable por concepto y centro de costo.', False),
 ('Pasantías que exceden seis meses',
  str(_C['n_pasantes']) + ' pasantes en el año: la empresa asume el 100% del aporte sobre el SBU (sin descuento al pasante), por lo que la base IESS de ' + _n(_C['base_pas']) + ' frente al estipendio de ' + _n(_C['estipendio']) + ' es la legalmente exigida y no constituye incumplimiento. Sin embargo, ' + _S.get('pasante_exceso','') + ' exceden seis meses de pasantía (meses afiliados entre paréntesis).',
  'Ley de Pasantías en el Sector Empresarial, art. 7 (reforma RO 234-S, 20-ene-2023): la pasantía no puede extenderse más de seis meses sin generar relación de dependencia; arts. 4 y 5: relación civil sin beneficios del Código del Trabajo. La sentencia de la Corte Constitucional 16-16-IN/22 declaró inconstitucional la reducción del estipendio a 1/3 del SBU con efectos diferidos; el plazo a la Asamblea venció en enero de 2024 sin nueva ley.',
  'No existe control del plazo máximo de las pasantías ni alerta en el sistema de nómina.',
  'Contingencia laboral: posible relación de dependencia desde el séptimo mes (remuneración mínima, décimos, vacaciones y aportes como trabajador), a cuantificar con criterio legal; la diferencia de base de ' + _n(_C['base_pas_dif']) + ' no requiere ajuste.', None, 'DO-8 / DO-3.1', 'Cumplimiento / contingencia laboral',
  'Controlar el plazo de cada pasantía con alerta antes del sexto mes, regularizar a los pasantes que lo exceden (' + _S.get('pasante_exceso_nombres','') + ') y obtener criterio legal sobre el estipendio mínimo tras la sentencia 16-16-IN/22.', True),
 ('Código de relación de trabajo incorrecto en meses de pasantía',
  _S.get('cod06','') + ' figuran en el IESS con código 06 (Código del Trabajo) en los meses en que el rol los registra como pasantes.',
  'El código de relación debe corresponder a la modalidad contractual vigente (pasantía: código 74).', 'Afiliación registrada antes del cambio de modalidad o error de registro.',
  'Inconsistencia de afiliación; posibles diferencias en aportes y beneficios.', None, 'DO-3 / DO-3.1', 'Cumplimiento IESS',
  'Corregir el código de relación ante el IESS y verificar los aportes de esos meses.', True),
 ('Décimo cuarto: gasto en exceso del devengado',
  'El gasto de décimo cuarto (' + _n(_C['d14_gasto']) + ') excede el devengado de auditoría (' + _n(_C['d14_dev']) + ') en ' + _n(_C['d14_exceso']) + '.',
  'Código del Trabajo, art. 113: SBU/360 × días laborados.', 'Provisión de enero calculada con un parámetro distinto al del resto del año.',
  'Gasto sobrestimado en ' + _n(_C['d14_exceso']) + '.', _C['d14_exceso'], 'DO-6 / DO-7 / DO-4C', 'Ajuste menor',
  'Revisar el parámetro de provisión del décimo cuarto al inicio de cada año.', False),
 ('Acumulación de décimos: solicitudes escritas por muestreo',
  str(_C['n_acum_d13']) + ' trabajadores acumulan el décimo tercero (' + str(_C['n_acum_d14']) + ' también el décimo cuarto). Se seleccionó una muestra única del 10% para verificar las solicitudes escritas de acumulación de ambos décimos (DO-4 V08); la verificación está pendiente de los documentos (RQ-007).',
  'Código del Trabajo, arts. 111 y 113: el pago mensualizado es la regla y la acumulación requiere solicitud escrita del trabajador. NIA 530 (muestreo de atributos).', 'Falta de archivo de las solicitudes en los expedientes del personal.',
  'Riesgo de reclamos laborales y de observaciones del Ministerio del Trabajo; con excepciones en la muestra se evalúa ampliarla o extenderla a la población.', None, 'DO-4 V08 / RQ-007', 'Cumplimiento / control interno',
  'Obtener y archivar en el expediente de cada trabajador la solicitud escrita de acumulación de D13 y D14, y validar en el sistema de nómina que solo acumulan quienes la presentaron.', True),
 ('Sueldos por pagar sin sustento de pago posterior',
  'El saldo de sueldos por pagar (' + _n(_C['sueldo_pend']) + ') corresponde al sueldo de diciembre de un trabajador; el resto del rol de diciembre se pagó en el mes.',
  'Los pasivos deben estar sustentados y liquidarse en el período siguiente.', 'Pago pendiente o error de registro.', 'Saldo de ' + _n(_C['sueldo_pend']) + ' por sustentar.', _C['sueldo_pend'], 'DO-9', 'Sustento',
  'Proporcionar el comprobante de pago de enero de 2026.', False),
 ('Compensación de cuentas por cobrar a empleados con el décimo tercero', 'En diciembre se debitó el pasivo del décimo tercero (asientos CIERRE.CXC.EMPLEADO) para cancelar cuentas por cobrar a empleados, y se pagó parte del décimo tercero fuera de la transferencia general (Mayor RQ-004, 5BS.21204.001).',
  'Código del Trabajo: las deducciones a la remuneración y a los décimos requieren autorización del trabajador o disposición legal; los décimos tienen protección especial frente a descuentos.', 'Cobro de anticipos o préstamos a empleados mediante compensación con el décimo tercero.',
  'Riesgo de reclamo laboral si no existe autorización escrita; sin efecto en el saldo (importe por sustentar).', None, 'DO-4C / Mayor RQ-004', 'Sustento',
  'Obtener la autorización escrita de cada trabajador y el detalle de las cuentas por cobrar compensadas; sustentar el pago separado.', True),
 ('Fondo de reserva pagado en mes sin aportación', _S.get('v04_nombres','') + ' recibió fondos de reserva (' + _n(_C['v04_total']) + ') en un mes en que su base IESS es cero.',
  'Código del Trabajo, art. 196: el fondo de reserva se calcula sobre la remuneración aportada.', 'Pago fuera de período o error de rol.', 'Pago sin sustento de ' + _n(_C['v04_total']) + '.', _C['v04_total'], 'DO-4 V04 / DO-6', 'Ajuste menor',
  'Revisar el pago y su recuperación o regularización.', False),
 ('IESS por pagar: conciliación con el mayor y diferencias residuales', 'Con el Mayor RQ-004 las cinco cuentas del IESS por pagar se reconstruyen desde el saldo inicial sin diferencia y cada pago al IESS coincide con su comprobante, salvo diferencias residuales menores (extensión de salud descontada en el comprobante y un ajuste de fondos de reserva). Las notas de crédito por permisos médicos se cierran contra el pasivo.',
  'El pasivo por aportes y fondos de reserva debe coincidir con lo liquidado por el IESS.', 'Notas de crédito y ajustes del IESS registrados en asientos separados del pago.', 'Diferencia residual menor; sin efecto significativo.', None, 'DO-9 (Mayor RQ-004)', 'Informativo',
  'Registrar las notas de crédito del IESS en el mismo período del comprobante y conciliar mensualmente las cuentas 5BS.21203.', True),
 ('Ajustes manuales del pasivo de vacaciones y anexo de nómina incompleto', 'Mayor RQ-004: los goces y finiquitos debitados al pasivo de vacaciones coinciden con el rol; una diferencia menor corresponde a ajustes manuales (actualización del sistema, reversos y redondeos). Además, el anexo de nómina (RQ-002) omite cuentas de gasto por ' + _n(_C['gasto_solo_mayor']) + ' (vacaciones, comisiones, premios, estipendio de pasantes, bono familiar) que sí están en el mayor.',
  'Los ajustes contables deben estar sustentados y aprobados; los anexos entregados al auditor deben ser completos (NIA 500).', 'Ajustes de actualización del sistema de nómina sin documento soporte; anexo preparado con un filtro de cuentas incompleto.', 'Ajustes manuales por sustentar; riesgo de omitir gasto en reportes basados en el anexo.', None, 'DO-5 / DO-7 / DO-2', 'Sustento',
  'Documentar y aprobar los ajustes manuales al pasivo de vacaciones y entregar el anexo de nómina con todas las cuentas de gasto.', True),
 ('Deficiencias del papel de trabajo anterior (uso interno)', 'Préstamos hipotecario/quirografario cruzados en varios meses; IESS de pasantes desordenado por mes; objetivos y procedimientos copiados entre cédulas; encabezados con referencias rotas.',
  'NIA 230: documentación de auditoría suficiente y adecuada.', 'Papel armado por copia de cédulas sin vinculación.', 'Riesgo de conclusiones incorrectas; corregido en las cédulas nuevas.', None, 'DO-5 a DO-10', 'Calidad del papel (interno)',
  'Usar las cédulas automatizadas del módulo AuditBrain.', False),
]

wb = Workbook()
wf = wb.active; wf.title = 'Ficha'
cell(wf, 'B2', 'FICHA DEL ENCARGO', ARB)
for i, (k, v) in enumerate([('Cliente', _R.CTX.cliente), ('Período terminado', pd.Timestamp(_R.CTX.corte).to_pydatetime()),
                            ('Preparado por', _R.CTX.preparado), ('Revisado por', _R.CTX.revisado), ('Fecha', '=TODAY()')]):
    cell(wf, f'B{4+i}', k, ARB, box=True); c = cell(wf, f'C{4+i}', v, BLUE if i < 4 else AR, box=True)
    if i in (1, 4): c.number_format = 'dd/mm/yyyy'
cell(wf, 'B11', 'Alcance: 100% de la población de nómina (sin muestreo). No se aplica materialidad de muestreo ni proyección de incorrecciones:', ARB)
cell(wf, 'B12', 'cada diferencia se evalúa y comunica individualmente.', ARB)
wf.column_dimensions['B'].width = 44; wf.column_dimensions['C'].width = 30

# ---------------- DO-12 hoja principal
ws = wb.create_sheet('DO12 Hoja de Hallazgos', 0)
header(ws, 'Hoja de hallazgos — condición, criterio, causa, efecto y recomendación', 12)
cols = ['No.', 'Observación (hallazgo)', 'Condición', 'Criterio', 'Causa', 'Efecto', 'Importe USD', 'Referencia de PT', 'Clasificación', 'Recomendación', 'Respuesta de la gerencia', 'Estado']
th(ws, 7, 1, cols, 30)
dv = DataValidation(type='list', formula1='"Abierto,En proceso,Cerrado,Ajustado"', allow_blank=True); ws.add_data_validation(dv)
FILL = {'Ajuste contable': RSF, 'Reclasificación': ORG, 'Cumplimiento IESS': YEL, 'Cumplimiento (por confirmar)': YEL, 'Cumplimiento / contingencia laboral': YEL, 'Informativo': YEL, 'Cumplimiento / control interno': YEL,
        'Ajuste menor': SUB, 'Por conciliar': SUB, 'Sustento': SUB, 'Calidad del papel (interno)': GRN}
for i, h in enumerate(H):
    r = 8 + i; t, cond, crit, cau, efe, imp, ref, cla, rec, _ = h
    vals = [i + 1, t, cond, crit, cau, efe, imp, ref, cla, rec, None, 'Abierto']
    for j, v in enumerate(vals):
        c = ws.cell(r, 1 + j, v); c.font = ARB if j == 1 else AR; c.alignment = WR; c.border = BOX
    ws.cell(r, 7).number_format = N2; ws.cell(r, 9).fill = FILL[cla]; ws.cell(r, 11).font = BLUE; ws.cell(r, 12).font = BLUE
    dv.add(f'L{r}')
    ws.row_dimensions[r].height = max(60, 11 * (max(len(cond), len(rec), len(crit)) // 34 + 1))
LH = 7 + len(H)
cell(ws, f'F{LH+1}', 'Total cuantificado', ARB); cell(ws, f'G{LH+1}', f'=SUM(G8:G{LH})', ARB, N2)
for k, (lab, crit) in enumerate([('Ajustes contables', 'Ajuste contable'), ('Reclasificaciones', 'Reclasificación'), ('Ajustes menores', 'Ajuste menor'), ('Por conciliar / sustento', 'Por conciliar')]):
    cell(ws, f'F{LH+2+k}', lab, AR); cell(ws, f'G{LH+2+k}', f'=SUMIF(I8:I{LH},"{crit}",G8:G{LH})' + ('+SUMIF(I8:I{0},"Sustento",G8:G{0})'.format(LH) if crit == 'Por conciliar' else ''), AR, N2)
t0 = LH + 8
cell(ws, f'A{t0}', 'Procedimiento:', RU)
cell(ws, f'A{t0+1}', 'Se detallaron las observaciones encontradas en cada análisis (DO-1 a DO-10), indicando el problema encontrado, el criterio, la causa y el efecto, con el valor en USD '
                    'de las diferencias determinadas. Al cubrir el 100% de la población no se aplica materialidad de muestreo: las incorrecciones se acumulan en su resumen y los ajustes propuestos en la hoja respectiva.', AR)
ws.merge_cells(f'A{t0+1}:L{t0+1}'); ws[f'A{t0+1}'].alignment = WR; ws.row_dimensions[t0 + 1].height = 30
cell(ws, f'A{t0+3}', 'Clasificación:', RED)
for k, (lab, f) in enumerate(FILL.items()):
    c = cell(ws, f'B{t0+4+k}', lab, AR); c.fill = f
for col, w in zip('ABCDEFGHIJKL', [5, 26, 40, 30, 28, 30, 13, 15, 16, 36, 24, 11]): ws.column_dimensions[col].width = w
ws.freeze_panes = 'C8'; ws.auto_filter.ref = f'A7:L{LH}'
ws.page_setup.orientation = 'landscape'; ws.sheet_properties.pageSetUpPr.fitToPage = True; ws.page_setup.fitToHeight = 0; ws.print_title_rows = '7:7'

# ---------------- Ajustes propuestos
wa = wb.create_sheet('Ajustes propuestos', 1)
header(wa, 'Asientos de ajuste y reclasificación propuestos', 7)
th(wa, 7, 1, ['Asiento', 'Cuenta', 'Descripción', 'Debe', 'Haber', 'Hallazgo', 'Efecto'], 28)
rows = []
rows.append(('AJ-1', '5BS.21204.003', 'Vacaciones por pagar', 24813.65, None, 'H-1', 'Disminuye pasivo'))
first_vac = len(rows)
tot_vac = sum(v for _, _, v in VAC)
for k, (cod, nom, v) in enumerate(VAC):
    f = f'=ROUND(24813.65*{v}/{tot_vac},2)' if k < len(VAC) - 1 else f'=24813.65-SUM(E9:E{7+len(VAC)})'
    rows.append(('AJ-1', cod, f'{nom} (prorrata por centro de costo)', None, f, 'H-1', 'Disminuye gasto'))
rows.append(('', '', 'Glosa: ajuste de la provisión de vacaciones a 1/24 de la remuneración (Código del Trabajo, art. 69).', None, None, '', ''))
rows.append(('RJ-1', '5DGEN.61101.001', 'Sueldos — administración general (remuneración del representante legal)', 11719.34, None, 'H-2', 'Reclasificación'))
rows.append(('RJ-1', '5DGEN.61101.007', 'Fondos de reserva — administración general', None, 11719.34, 'H-2', 'Reclasificación'))
rows.append(('RJ-1', '5DIR.61101.001', 'Sueldos — directorio (remuneración del presidente)', 6574.86, None, 'H-2', 'Reclasificación'))
rows.append(('RJ-1', '5DIR.61101.007', 'Fondos de reserva — directorio', None, 6574.86, 'H-2', 'Reclasificación'))
rows.append(('', '', 'Glosa: reclasificación de fondos de reserva pagados a administradores por nombramiento. Verificar centro de costo y efecto tributario (LRTI).', None, None, '', ''))
for i, rw in enumerate(rows):
    r = 8 + i
    for j, v in enumerate(rw):
        c = wa.cell(r, 1 + j, v); c.font = AR; c.border = BOX; c.alignment = WR
        if j in (3, 4): c.number_format = N2
    if rw[0] == '': wa.cell(r, 3).font = IT
LA = 7 + len(rows)
cell(wa, f'C{LA+1}', 'Σ (debe = haber)', ARB); cell(wa, f'D{LA+1}', f'=SUM(D8:D{LA})', ARB, N2); cell(wa, f'E{LA+1}', f'=SUM(E8:E{LA})', ARB, N2)
cell(wa, f'F{LA+1}', f'=IF(ABS(D{LA+1}-E{LA+1})<0.05,"Cuadra ✓","Revisar")', IT)
cell(wa, f'A{LA+3}', 'EFECTO EN SALDOS (cédula sumaria DO-2)', NAVYF)
th(wa, LA + 4, 1, ['Cuenta / rubro', '', 'Saldo en libros', 'Ajuste', 'Saldo auditado', 'Referencia', ''], 24)
efe = [('Vacaciones por pagar (5BS.21204.003)', _C['vac_libros'], -_C['vac_exceso'], 'DO-4C'), ('Gasto vacaciones', _C['vac_gasto_libros'], -_C['vac_exceso'], 'DO-6'),
       ('Gasto fondos de reserva', _C['fr_gasto_libros'], -_C['excluido_fr'], 'DO-6'), ('Gasto sueldos', _C['sue_gasto'], _C['excluido_fr'], 'DO-8 / DO-10')]
for i, (t, s0, aj, rf) in enumerate(efe):
    r = LA + 5 + i
    cell(wa, f'A{r}', t, AR, box=True); wa.merge_cells(f'A{r}:B{r}')
    cell(wa, f'C{r}', s0, BLUE, N2, box=True); cell(wa, f'D{r}', aj, AR, N2, box=True); cell(wa, f'E{r}', f'=C{r}+D{r}', ARB, N2, box=True); cell(wa, f'F{r}', rf, IT, box=True)
cell(wa, f'A{LA+10}', 'Efecto en el resultado del ejercicio (antes de impuestos): aumento de la utilidad por ' + _n(_C['vac_exceso']) + ' (AJ-1); RJ-1 no afecta el resultado.', ARB)
for col, w in zip('ABCDEFG', [8, 18, 58, 14, 14, 10, 18]): wa.column_dimensions[col].width = w

# ---------------- Resumen NIA 450
wn = wb.create_sheet('Resumen de incorrecciones', 2)
header(wn, 'Acumulación de incorrecciones — prueba al 100% de la población', 8)
th(wn, 7, 1, ['Hallazgo', 'Descripción', 'Tipo', 'Activo', 'Pasivo', 'Resultado (gasto)', 'Ajustada', 'Tratamiento'], 30)
inc = [('H-1', 'Provisión de vacaciones en exceso', 'De hecho', 0, -_C['vac_exceso'], -_C['vac_exceso'], 'Propuesta AJ-1'),
       ('H-2', 'FR pagado a administradores (reclasificación)', 'De hecho', 0, 0, 0, 'Propuesta RJ-1'),
       ('H-7', 'Décimo cuarto: pasivo en exceso', 'De hecho', 0, _C['d14_pas_dif'], _C['d14_pas_dif'], 'No ajustada'),
       ('H-7', 'Décimo tercero: pasivo en exceso', 'De hecho', 0, _C['d13_pas_dif'], _C['d13_pas_dif'], 'No ajustada'),
       ('H-11', 'FR pagado sin base (' + _S.get('v04_nombres','') + ')', 'De hecho', 0, 0, -_C['v04_total'], 'No ajustada'),
       ('H-4', 'Sueldos rol > libros (por conciliar)', 'De juicio (pendiente reporte de nómina por centro de costo)', 0, 0, _C['sue_exceso'], 'Pendiente'),
       ('H-3', 'Aportes potencialmente omitidos', 'De juicio', 0, None, None, 'Pendiente')]
for i, rw in enumerate(inc):
    r = 8 + i
    for j, v in enumerate(rw):
        c = wn.cell(r, 1 + j if j < 6 else 7, v); c.font = AR; c.border = BOX; c.alignment = WR
        if j in (3, 4, 5): c.number_format = N2
    TR = {'Propuesta AJ-1': 'Ajuste propuesto', 'Propuesta RJ-1': 'Reclasificación propuesta', 'No ajustada': 'Comunicar a la gerencia (diferencia exacta, sin proyección)', 'Pendiente': 'Cuantificar con RQ-004 / confirmación'}
    c = wn.cell(r, 8, TR[rw[6]]); c.font = AR; c.border = BOX; c.alignment = WR
LN = 7 + len(inc)
cell(wn, f'B{LN+1}', 'Total incorrecciones no ajustadas (de hecho)', ARB)
cell(wn, f'E{LN+1}', f'=SUMIF(G8:G{LN},"No ajustada",E8:E{LN})', ARB, N2); cell(wn, f'F{LN+1}', f'=SUMIF(G8:G{LN},"No ajustada",F8:F{LN})', ARB, N2)
cell(wn, f'B{LN+2}', 'Conclusión', ARB)
cell(wn, f'C{LN+2}', 'Al probarse el 100% de la nómina, las diferencias son exactas (no estimadas): se propone ajuste de las sustentadas (AJ-1, RJ-1) y se comunican todas las demás a la gerencia; las de juicio se cuantifican al recibir el RQ-004.', AR)
wn.merge_cells(f'C{LN+2}:H{LN+3}'); wn[f'C{LN+2}'].alignment = WR; wn.row_dimensions[LN + 2].height = 30
cell(wn, f'B{LN+4}', 'Signo: negativo = disminuye el saldo según libros. Pasivo y resultado según el efecto del ajuste en los estados financieros del cliente.', IT)
for col, w in zip('ABCDEFGH', [9, 44, 22, 10, 14, 15, 15, 34]): wn.column_dimensions[col].width = w

# ---------------- Carta de control interno
wl = wb.create_sheet('Carta control interno', 3)
header(wl, 'Observaciones para la carta de control interno — sección laboral', 5)
th(wl, 7, 1, ['N.º', 'Observación', 'Recomendación', 'Ref.', 'Respuesta de la gerencia'], 26)
k = 0
for i, h in enumerate(H):
    if not h[9]: continue
    k += 1; r = 7 + k
    obs = f'{h[0]}. {h[1]} Criterio: {h[2]} Efecto: {h[4]}'
    for j, v in enumerate([k, obs, h[8], f'H-{i+1}', None]):
        c = wl.cell(r, 1 + j, v); c.font = AR; c.alignment = WR; c.border = BOX
    wl.cell(r, 5).font = BLUE; wl.row_dimensions[r].height = 110
for col, w in zip('ABCDE', [5, 70, 45, 8, 30]): wl.column_dimensions[col].width = w

# ---------------- Controles
wc = wb.create_sheet('Controles')
cell(wc, 'B2', 'CONTROLES', ARB); th(wc, 4, 2, ['Control', 'Valor A', 'Valor B', 'Diferencia', 'Estado'])
ctl = [('Asientos: debe = haber', f"='Ajustes propuestos'!D{LA+1}", f"='Ajustes propuestos'!E{LA+1}", 0.05),
       ('AJ-1 prorrata vacaciones', f"=SUM('Ajustes propuestos'!E{8+first_vac}:E{7+first_vac+len(VAC)})", _C['vac_exceso'], 0.05),
       ('Saldo auditado vacaciones = reproceso DO-4', f"='Ajustes propuestos'!E{LA+5}", _C['vac_reproc'], 0.05),
       ('RJ-1 = FR excluido de administradores', "='Ajustes propuestos'!D{0}+'Ajustes propuestos'!D{1}".format(8 + first_vac + len(VAC) + 1, 8 + first_vac + len(VAC) + 3), _C['excluido_fr'], 0.05),
       ('Hallazgos registrados = 14', "=COUNTA('DO12 Hoja de Hallazgos'!B8:B{0})".format(LH), 14, 0)]
for i, (t, a, b2, tol) in enumerate(ctl):
    r = 5 + i
    cell(wc, f'B{r}', t, AR, box=True); cell(wc, f'C{r}', a, GREEN, N2, box=True); cell(wc, f'D{r}', b2, GREEN, N2, box=True)
    cell(wc, f'E{r}', f'=ROUND(C{r}-D{r},2)', AR, N2, box=True); cell(wc, f'F{r}', f'=IF(ABS(E{r})<={tol},"OK","REVISAR")', ARB, box=True)
n = len(ctl); cell(wc, f'B{6+n}', f'=COUNTIF(F5:F{4+n},"OK")&" de {n} controles OK"', ARB)
wc.column_dimensions['B'].width = 56
for col in 'CDEF': wc.column_dimensions[col].width = 16
wb.active = 0
_wf = wb['Ficha']
_r = max(_wf.max_row + 2, 14)
_wf.cell(_r, 2, 'Año auditado 2026. Cédula construida con datos de la plantilla 2025 (rol, IESS, anexo y comprobantes); se reemplazan con la información 2026 del cliente.').font = Font(name='Arial', size=8, italic=True, color='FFC00000')
wb.save(OUT)

# ---- JSON para el panel
aj = [[a, b, c, d if isinstance(d, (int, float)) else None, (round(24813.65 * float(e.split('*')[1].split('/')[0]) / tot_vac, 2) if isinstance(e, str) and e.startswith('=ROUND') else (None if isinstance(e, str) else e)), f]
      for a, b, c, d, e, f, _ in rows]
json.dump(dict(hall=[[i + 1, h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7], h[8]] for i, h in enumerate(H)], aj=aj,
               efe=[[t, s0, aj_, s0 + aj_, rf] for t, s0, aj_, rf in efe]),
          open((_R.CTX.home + '/do12.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('ok', OUT, 'hallazgos', len(H), 'filas ajuste', len(rows))
