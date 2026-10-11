# -*- coding: utf-8 -*-
from backend.app.aud.niif.procesadores.nomina import rutas as _R
_S = _R.SUJETOS; _C = _R.CIFRAS
_n = lambda v: f"{v:,.2f}".translate(str.maketrans({',': '.', '.': ','}))
"""DO-0 Programa / Procedimiento de Auditoría de Nómina — recopila todos los procedimientos ejecutados (DO-1 a DO-10) y los pendientes (DO-12)."""
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.drawing.image import Image as XLImage
from openpyxl.worksheet.datavalidation import DataValidation

OUT = (_R.CTX.out + '/DO-0_Programa_Auditoria_Nomina.xlsx')
NAVY = PatternFill('solid', fgColor='FF0F2341'); SUB = PatternFill('solid', fgColor='FFDDE6F3'); YEL = PatternFill('solid', fgColor='FFFFF2CC')
GRN = PatternFill('solid', fgColor='FFE2EFDA'); ORG = PatternFill('solid', fgColor='FFFCE4D6')
AR = Font(name='Arial', size=9); ARB = Font(name='Arial', size=9, bold=True); WH = Font(name='Arial', size=9, bold=True, color='FFFFFFFF')
WH12 = Font(name='Arial', size=12, bold=True, color='FFFFFFFF'); BLUE = Font(name='Arial', size=9, color='FF0000FF')
RED = Font(name='Arial', size=9, bold=True, color='FFC00000'); NAVYF = Font(name='Arial', size=10, bold=True, color='FF1F3864'); IT = Font(name='Arial', size=8, italic=True)
thin = Side(style='thin', color='FF9E9E9E'); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
WR = Alignment(wrap_text=True, vertical='top'); C = Alignment(horizontal='center', vertical='center', wrap_text=True)

def th(ws, row, col0, labels, h=30):
    for i, t in enumerate(labels):
        c = ws.cell(row, col0 + i, t); c.font = WH; c.fill = NAVY; c.alignment = C; c.border = BOX
    ws.row_dimensions[row].height = h

def header(ws, titulo, ncol, ref):
    for r in range(1, 4):
        for col in range(1, ncol + 1): ws.cell(r, col).fill = NAVY
    ws.row_dimensions[1].height = 34; ws.row_dimensions[2].height = 20
    img = XLImage(_R.CTX.logo); img.height = 56; img.width = 150; ws.add_image(img, 'A1')
    ws.cell(1, 5, 'OBLIGACIONES ACUMULADAS Y GASTOS DE NÓMINA').font = WH12
    ws.cell(3, 5, titulo).font = WH
    for c0, lab, val in ((1, 'Cliente:', '=Ficha!C4'), (4, 'Período terminado:', '=Ficha!C5')):
        ws.cell(4, c0, lab).font = ARB; x = ws.cell(4, c0 + 1, val); x.font = AR
        if c0 == 4: x.number_format = 'dd/mm/yyyy'
    for c0, lab, val in ((1, 'Preparado por:', '=Ficha!C6'), (4, 'Revisado por:', '=Ficha!C7')):
        ws.cell(5, c0, lab).font = ARB; ws.cell(5, c0 + 1, val).font = AR
    ws.cell(5, ncol - 1, 'Referencia de PT').font = ARB; ws.cell(5, ncol, ref).font = RED

wb = Workbook()
wf = wb.active; wf.title = 'Ficha'
wf['B2'] = 'FICHA DEL ENCARGO'; wf['B2'].font = ARB
for i, (k, v) in enumerate([('Cliente', _R.CTX.cliente), ('Período terminado', pd.Timestamp(_R.CTX.corte).to_pydatetime()),
                            ('Preparado por', _R.CTX.preparado), ('Revisado por', _R.CTX.revisado), ('Marco', 'Legal / laboral / tributario: Código del Trabajo, Ley de Seguridad Social y resoluciones IESS, acuerdos MDT, LRTI')]):
    wf.cell(4 + i, 2, k).font = ARB; c = wf.cell(4 + i, 3, v); c.font = BLUE
    if i == 1: c.number_format = 'dd/mm/yyyy'
wf.column_dimensions['B'].width = 20; wf.column_dimensions['C'].width = 90

# =========================================================== PROGRAMA
P = []  # (prueba, ref, aserciones, objetivo, paso, procedimiento, insumos, criterio, resultado, hallazgo, estado)
def add(prueba, ref, aser, obj, pasos, ins, crit, res, hall, est):
    for i, p in enumerate(pasos):
        P.append((prueba if i == 0 else '', ref, aser if i == 0 else '', obj if i == 0 else '', f'{ref}.{i+1}', p,
                  ins if i == 0 else '', crit if i == 0 else '', res if i == 0 else '', hall if i == 0 else '', est))

add('Evaluación de Control Interno Laboral', 'DO-1', 'Cumplimiento',
    'Evaluar el cumplimiento de obligaciones laborales y de seguridad social y el control interno del ciclo de nómina.',
    ['Aplicar el cuestionario laboral IESS/MDT consolidado 2026.1 (72 ítems, 10 bloques) con el responsable de nómina.',
     'Calificar cada ítem (Sí / No / Parcial / No aplica) y documentar la evidencia revisada.',
     'Determinar el nivel de riesgo por bloque y las observaciones para la carta de control interno (sección laboral y de gobierno corporativo).',
     'Verificar en el Bloque F el cupo mínimo de personas con discapacidad (4% de la nómina; DO-4 informa 5,84 personas a diciembre).'],
    'RQ-001 Cuestionario laboral', 'Código del Trabajo; Ley de Seguridad Social; acuerdos MDT vigentes al corte 05-oct-2026',
    'Panel en ejecución: 0/72 evaluados al cierre de esta versión.', 'Según calificación', 'En ejecución')
add('Sumaria de Nómina', 'DO-2', 'Existencia · Integridad · Presentación',
    'Obtener los saldos de pasivos acumulados y gastos de nómina, sus variaciones y el saldo auditado.',
    ['Trasladar del Anexo de nómina los saldos al 31-dic-2024 y al 31-dic-2025 de pasivos (5BS.21203 / 5BS.21204) y gastos (5PYG / 5D…).',
     'Calcular variaciones absolutas y relativas y explicar las significativas.',
     'Cuadrar los totales con el estado de situación financiera y el estado de resultados.',
     'Referenciar cada saldo a la cédula que lo audita (DO-4C, DO-6, DO-9, DO-10) y recibir los ajustes propuestos de la DO-12.'],
    'RQ-002 Anexo de nómina', 'NIIF (presentación); saldos según libros',
    'Gasto de nómina por concepto (sueldos, horas extras, bonos, décimos, FR, aporte patronal) y pasivos acumulados al corte, trasladados del anexo y detallados en la DO-2.',
    '—', 'Terminada')
add('Resumen de Planillas de Aportes IESS', 'DO-3', 'Exactitud · Integridad',
    'Resumir las planillas de aportes del año y recalcular los aportes sobre la base imponible.',
    ['Cargar el Consolidado IESS enero–diciembre, por región.',
     'Resumir por mes: afiliados, base imponible, aporte personal, aporte patronal y CCC.',
     'Recalcular aportes con las tasas vigentes y el SBU del ejercicio y comparar con lo declarado.',
     'Identificar códigos de relación (06, 16, 74, 109) y registros atípicos (pasantes, códigos inconsistentes).'],
    'RQ-003 Consolidado IESS', 'Ley de Seguridad Social (materia gravada); resoluciones IESS de tasas',
    'Base imponible, aportes personal y patronal, CCC y total del año, resumidos por mes en la DO-3.',
    'Código de relación de pasantes (' + _S.get('cod06','') + ') reportado como 06 en meses de pasantía.', 'Terminada')
add('Resumen de Roles de Pago', 'DO-3.1', 'Integridad · Exactitud',
    'Consolidar el rol de pagos como fuente base de la remuneración y cruzarlo con el IESS.',
    ['Trasladar el 100% del rol (pestaña «normal»: empleados y jubilados) y la pestaña «pasantes».',
     'Agrupar por mes y concepto (sueldo, horas extras, variables, vacaciones, FR, décimos mensualizados, liquidaciones) y provisiones del cliente.',
     'Cruzar por nombre con el Consolidado IESS y comparar base gravada y aportes por trabajador.',
     'Generar el maestro de trabajadores: fechas de ingreso y salida, mensualización de décimos, liquidados, pasantes y jubilados.',
     'Cuadrar la provisión patronal del rol + aporte de pasantes con el gasto de la DO-2 y el AD 4,41% JP con «Otros gastos de nómina».'],
    'RQ-006 Rol de pagos · RQ-003', 'Reglas RL-01 a RL-06 (REGLAS_Beneficios_Sociales)',
    'Base gravada del rol frente a la base reportada al IESS y provisión patronal conciliada con la DO-2 (detalle en la DO-3.1).',
    'Posible subdeclaración de aportes en la diferencia de base (DO-3.1 / DO-8).', 'Terminada')
add('Reproceso de Beneficios Sociales por Pagar', 'DO-4', 'Valuación · Integridad · Corte',
    'Recalcular décimo tercero, décimo cuarto, vacaciones y fondos de reserva sobre el 100% de la base aportada.',
    ['Por trabajador y mes: D13 = base/12; D14 = SBU/360 × días (por región: Sierra ago–jul, Costa mar–feb); vacaciones = base/24; FR = 8,33% desde el mes 13 (mes de aniversario proporcional).',
     'Excluir pasantías y décimos mensualizados según el rol; considerar la fecha de ingreso vigente del rol.',
     'Aplicar exclusiones: código 109 automático y lista del auditor (representantes legales García Mancero y García Costa: D13, D14 y FR excluidos; conservan vacaciones).',
     'Determinar el pasivo al 31-dic solo de trabajadores activos; vacaciones netas de goces y finiquitos.',
     'Comparar con las provisiones del cliente y con la DO-2; cuadrar gasto (pagado en rol + provisión = gasto).',
     'Ejecutar validaciones V01–V11 (duplicados, FR sin base, acumulación de D13 sin solicitud, FR pagado a excluidos).'],
    'RQ-003 (+ Exclusiones) · DO-3.1 · DO-2', 'Código del Trabajo arts. 69 (vacaciones), 111 (D13), 113 (D14), 196 (FR); reglas D13, D14, VAC, FR, RL, EX',
    'Pasivo reprocesado por beneficio (D13, D14, vacaciones, FR) y valores excluidos por el auditor, detallados en la DO-4.',
    'Vacaciones sobreprovisionadas; FR pagado a representantes legales; trabajadores que acumulan décimos: solicitudes por muestreo en DO-4 V08.', 'Terminada')
add('Muestreo de Solicitudes de Acumulación de Décimos', 'DO-4 V08', 'Cumplimiento · Ocurrencia',
    'Verificar que los trabajadores que reciben D13 y D14 acumulados tienen la solicitud escrita de acumulación (prueba de atributos).',
    ['Población: trabajadores que acumulan D13 según DO-4 (y los que también acumulan D14), después de exclusiones.',
     'Muestra única para ambos décimos: 10% por defecto (configurable): partidas clave de mayor D13 + selección sistemática con arranque aleatorio.',
     'Solicitar al cliente las solicitudes de acumulación de las personas seleccionadas (RQ-007) y marcar su existencia para D13 y D14 (Sí/No/N/A).',
     'Excepción = persona sin solicitud: comunicar en DO-12 (H-8) y evaluar ampliar la muestra o extender a la población.'],
    'DO-4 Detalle RQ-003 · RQ-007 solicitudes', 'Código del Trabajo arts. 111 y 113 (mensualización como regla; acumulación a solicitud escrita); NIA 530 (muestreo de atributos)',
    'Muestra generada (partidas clave + selección sistemática); marcas del auditor pendientes de los documentos.',
    'H-8 (pendiente de documentos)', 'En ejecución')
add('Vacaciones No Gozadas — Liquidación Hipotética al Corte', 'DO-4V', 'Valuación · Existencia · Corte',
    'Determinar el pasivo exigible por vacaciones como si cada trabajador activo saliera al corte y separar el ajuste entre gasto del año y resultados acumulados.',
    ['Visita preliminar: solicitar el kárdex de vacaciones por trabajador (RQ-008). Si no se entrega, la prueba queda NO SOPORTADA y se emite la observación OBS-VAC.',
     'Visita final: para el 100% de trabajadores activos calcular días devengados desde la fecha de ingreso (15 por año + 1 adicional desde el 6.º año, máximo 15 adicionales) al cierre anterior y al corte.',
     'Restar días gozados o pagados según kárdex; valorar el saldo con la remuneración mensual vigente al corte / 30 (por defecto) o, como alternativa del art. 71 CT, con el promedio de remuneraciones de los últimos 12 meses / 30; la cédula muestra ambas.',
     'Ajuste total = pasivo exigible − libros; porción de años anteriores (pasivo correcto al cierre anterior − libros a esa fecha) contra resultados acumulados (NIC 8); el resto, gasto del año.',
     'Limitar el saldo a 5 períodos anuales (criterio del socio, parámetro editable); revisar saldos negativos (días anticipados) y acumulaciones de más de tres períodos (art. 75 CT).'],
    'DO-3.1 maestro · DO-4 · RQ-008 kárdex · RQ-002 saldos', 'Código del Trabajo arts. 69, 71, 75 y 76; NIC 19 (beneficios a corto plazo acumulables); NIC 8 (corrección de errores)',
    'Estado: NO SOPORTADO — trabajadores activos sin kárdex; observación OBS-VAC (visita preliminar). Calculadora lista para la visita final.',
    'H-1 (ajuste definitivo con kárdex)', 'En ejecución')
add('Cruce Global del Pasivo de Beneficios', 'DO-4C', 'Existencia · Valuación',
    'Verificar que el saldo de beneficios sociales por pagar del ESF esté sustentado y valorado.',
    ['Tomar los saldos ESF y saldos iniciales del Anexo RQ-002 (5BS.21204.001 a .003).',
     'Determinar el pasivo bruto según auditoría: D13 devengado de diciembre; D14 Sierra agosto–diciembre; vacaciones = saldo inicial + provisión del año.',
     'Restar las partidas del rol: liquidaciones (vacaciones de finiquito), finiquito (devengado de salidos), pago mensual (mensualizados y goces); ajuste solo con sustento.',
     'Conciliar el neto con el pasivo de la DO-4.'],
    'RQ-002 · DO-4 · DO-3.1', 'Reglas RL-04, RL-05',
    'Diferencia del pasivo por beneficio (principalmente vacaciones en exceso), conciliada con la DO-4 (detalle en la DO-4C).', 'Vacaciones: pasivo en exceso (ver DO-4C).', 'Terminada')
add('Cruce Mensual del Pasivo de Beneficios', 'DO-5', 'Valuación · Corte',
    'Comparar mes a mes la provisión de libros con el recálculo y conciliar el cierre con el cruce global.',
    ['Tomar las provisiones mensuales en libros (D13 diciembre; D14 agosto–diciembre; vacaciones enero–diciembre).',
     'Comparar con el recálculo mensual neto de pagos mensualizados.',
     'Conciliar el total con la DO-4C y explicar las partidas por conciliar con los débitos de la cuenta.'],
    'RQ-004 Mayor de pasivos (5BS.21204) · RQ-002 · DO-4C', 'Reglas D13, D14, VAC',
    'Mayor RQ-004: saldo inicial + movimientos = ESF; goces, finiquitos y décimos liquidados conciliados con el rol; una diferencia menor son ajustes manuales del mayor.',
    'Ajustes manuales de vacaciones por sustentar (H-13); compensación de CxC de empleados con el D13 (H-10).', 'Terminada')
add('Reproceso de Gastos y Beneficios Sociales', 'DO-6 / DO-7', 'Exactitud · Ocurrencia · Integridad',
    'Verificar que el gasto por beneficios y aportes patronales esté calculado y registrado correctamente, en total y por mes.',
    ['Agrupar las cuentas de gasto por beneficio y centro de costo (DO-6).',
     'Recalcular el gasto devengado del año (D13, D14, aporte patronal + CCC, FR, vacaciones, aporte de pasantes) con exclusiones.',
     'Analizar la diferencia de fondos de reserva: devengado, FR de excluidos, pagado (rol + IESS) y libros.',
     'Abrir el cruce mes a mes (DO-7) y cuadrar cada beneficio con la DO-6.'],
    'RQ-002 · RQ-003 · RQ-004 Mayor de gastos · DO-4 · DO-3.1', 'Código del Trabajo; Ley de Seguridad Social; LRTI (deducibilidad de gastos aportados)',
    'Diferencia del gasto por beneficio (vacaciones, FR, D14, D13, aporte), abierta por concepto en la DO-6/DO-7.',
    'FR pagado sin derecho a representantes legales; provisión de vacaciones en exceso. Mayor RQ-004 concilia los seis conceptos.', 'Terminada')
add('Análisis de Base Imponible IESS', 'DO-8', 'Integridad · Cumplimiento',
    'Verificar que la base declarada al IESS corresponda a los conceptos remunerativos en libros.',
    ['Separar la base IESS de empleados y de pasantes.',
     'Sumar los conceptos remunerativos de libros (sueldos, horas extras, bonos, comisiones, premios) y las vacaciones gozadas del rol.',
     'Comparar en total y por mes; cotejar con la base gravada del rol (DO-3.1).',
     'Analizar pasantes (Ley de Pasantías, art. 7): estipendio ≥ 1/3 del SBU, aporte sobre el SBU a cargo total de la empresa y duración ≤ 6 meses sin relación de dependencia.'],
    'RQ-003 · RQ-002 · RQ-004 Mayor de gastos · RQ-006', 'Ley de Seguridad Social, art. 11 (materia gravada)',
    'Base IESS de empleados conciliada con libros; base de pasantes sobre el SBU frente al estipendio; diferencia de base rol − IESS (detalle en la DO-8).',
    'Pasantes: el aporte sobre el SBU, asumido íntegramente por la empresa (17,6%), es el que exige la Ley de Pasantías, art. 7: no es incumplimiento. Riesgo de duración > 6 meses (H-5).', 'Terminada')
add('IESS por Pagar: Libros vs Comprobantes de Pago', 'DO-9', 'Existencia · Exactitud · Cumplimiento',
    'Verificar el pago oportuno de aportes, fondos de reserva y préstamos y sustentar los saldos por pagar.',
    ['Leer los comprobantes de pago del IESS (85 PDF) y clasificarlos por tipo y período; verificar su aritmética.',
     'Comparar mes a mes libros vs comprobantes; conciliar las notas de crédito del IESS.',
     'Conciliar aportes y FR a tres vías con el Consolidado IESS.',
     'Cotejar los saldos de diciembre con el Anexo RQ-002 y los sueldos por pagar con el rol.',
     'Evaluar plazos (V10): emisión vs fecha de vigencia de pago; confirmar con estado bancario.'],
    'RQ-005 Comprobantes · RQ-002 · RQ-003 · RQ-004 Mayor de pasivos (5BS.21203) · RQ-006', 'Ley de Seguridad Social y resoluciones IESS (plazos de pago, mora)',
    'Mayor RQ-004: cuentas del IESS reconstruidas sin diferencia; pagos al IESS conciliados con los comprobantes; saldos de diciembre sustentados; sin pagos fuera de plazo.',
    'Saldo de sueldos por pagar por sustentar (H-9); diferencias residuales menores del IESS (H-12).', 'Terminada')
add('Roles de Pago vs Libros: Gastos y Provisiones', 'DO-10', 'Ocurrencia · Integridad · Exactitud',
    'Verificar que los conceptos pagados en roles estén registrados en gastos y en las cuentas de pasivo.',
    ['Totalizar el rol por mes y concepto (16 conceptos), incluidos pasantes.',
     'Comparar con el gasto en libros por concepto.',
     'Cotejar fondos de reserva sumando los depósitos en el IESS (comprobantes).',
     'Cotejar los pagos que debitan el pasivo (goces y finiquitos) con el Mayor de pasivos y los décimos mensualizados con el gasto menos la provisión acreditada.',
     'Abrir por mes la diferencia de sueldos.'],
    'RQ-006 · RQ-002 · RQ-005 · RQ-004 Mayores de gastos y pasivos', 'Reglas RL-01 a RL-06',
    'Sueldos del rol frente al gasto en libros (diferencia en la nómina regular; liquidaciones cuadran); demás conceptos conciliados; FR y décimos jubilares explicados (detalle en la DO-10).',
    'Diferencia de sueldos: falta el reporte de nómina por centro de costo (H-4).', 'Terminada')
add('Hallazgos y Ajustes de Auditoría', 'DO-12', 'Todas',
    'Consolidar excepciones, cuantificar ajustes propuestos y emitir recomendaciones.',
    ['Recopilar los hallazgos de DO-1 a DO-10 (hoja «Hallazgos» de este programa).',
     'Clasificar por naturaleza (ajuste contable, reclasificación, cumplimiento, control interno); al cubrir el 100% de la población, cada diferencia se evalúa individualmente sin materialidad de muestreo.',
     'Proponer asientos de ajuste y reclasificación y su efecto en la DO-2.',
     'Redactar observaciones y recomendaciones para la carta de control interno.'],
    'Todas las cédulas', 'NIA 450 (acumulación de incorrecciones; sin muestreo ni proyección por cobertura 100%); NIA 265 (comunicación de deficiencias)',
    'Hallazgos cuantificados con los mayores RQ-004. AJ-1 vacaciones (pasivo y gasto); RJ-1 reclasificación de FR a remuneración; incorrecciones acumuladas sin proyección (prueba al 100%); observaciones para la carta de control interno.',
    'Ver hoja de hallazgos DO-12', 'Terminada')

ws = wb.create_sheet('Programa', 0)
COLS = ['Prueba', 'Ref. PT', 'Aserciones', 'Objetivo', 'Paso', 'Procedimiento', 'Insumos (RQ / PT)', 'Criterio / base normativa',
        'Resultado obtenido', 'Hallazgo vinculado', 'Estado', 'Hecho por / fecha', 'Revisado por / fecha']
header(ws, 'DO-0 · PROGRAMA DE AUDITORÍA DE NÓMINA — procedimientos ejecutados y pendientes', len(COLS), 'DO-0')
ws.merge_cells('A6:M6'); b = ws['A6']
b.value = ('Alcance: pasivos acumulados (beneficios sociales, IESS por pagar, sueldos por pagar) y gastos de nómina del ejercicio 2026 (cédulas con datos de plantilla 2025), sobre el 100% de la población; solo la prueba de atributos de solicitudes de acumulación (DO-4 V08) usa muestra. '
           'Marco legal/laboral/tributario (Memoria AuditBrain M02). Libros: Anexo RQ-002 y Mayores RQ-004 (gastos y pasivos), conciliados entre sí.')
b.font = Font(name='Arial', size=9, bold=True, color='FF1F3864'); b.fill = YEL; b.alignment = WR; ws.row_dimensions[6].height = 30
th(ws, 8, 1, COLS, 30)
dv = DataValidation(type='list', formula1='"Terminada,Terminada (libros provisionales),Terminada (débitos de pasivo pendientes),En ejecución,Siguiente,Pendiente"', allow_blank=True)
ws.add_data_validation(dv)
r = 9
for row in P:
    prueba, ref, aser, obj, paso, proc, ins, crit, res, hall, est = row
    vals = [prueba, ref, aser, obj, paso, proc, ins, crit, res, hall, est, '', '']
    fill = SUB if prueba else None
    for j, v in enumerate(vals):
        c = ws.cell(r, 1 + j, v); c.font = ARB if (j == 0 and v) else AR; c.alignment = WR; c.border = BOX
        if fill and j < 4: c.fill = fill
    est_c = ws.cell(r, 11); est_c.fill = GRN if est.startswith('Terminada') else (ORG if est in ('En ejecución', 'Siguiente') else YEL)
    ws.cell(r, 12).font = BLUE; ws.cell(r, 13).font = BLUE
    dv.add(f'K{r}')
    ws.row_dimensions[r].height = max(30, 12 * (len(proc) // 55 + 1), 12 * (len(res) // 40 + 1) if res else 0)
    r += 1
last = r - 1
for col, w in zip('ABCDEFGHIJKLM', [22, 8, 14, 28, 7, 52, 22, 26, 36, 28, 15, 14, 14]): ws.column_dimensions[col].width = w
ws.freeze_panes = 'F9'; ws.auto_filter.ref = f'A8:M{last}'
r += 1
ws.cell(r, 1, 'Resumen de avance').font = NAVYF; r += 1
for k, lab in enumerate(['Terminada', 'Terminada (libros provisionales)', 'Terminada (débitos de pasivo pendientes)', 'En ejecución', 'Siguiente']):
    ws.cell(r + k, 1, lab).font = AR
    ws.cell(r + k, 2, f'=SUMPRODUCT((K9:K{last}="{lab}")*(A9:A{last}<>""))').font = ARB
ws.cell(r + 5, 1, 'Pruebas (cédulas)').font = ARB; ws.cell(r + 5, 2, f'=COUNTA(A9:A{last})-COUNTBLANK(A9:A{last})*0').font = ARB
ws.cell(r + 5, 2).value = f'=SUMPRODUCT(--(A9:A{last}<>""))'
ws.page_setup.orientation = 'landscape'; ws.sheet_properties.pageSetUpPr.fitToPage = True; ws.page_setup.fitToHeight = 0
ws.print_title_rows = '8:8'

# =========================================================== REQUERIMIENTOS
wq = wb.create_sheet('Requerimientos')
header(wq, 'REQUERIMIENTOS DE INFORMACIÓN Y SU USO', 7, 'DO-0')
th(wq, 8, 1, ['Código', 'Documento', 'Compartimentos / formato', 'Estado', 'Cédulas que lo consumen', 'Observación', 'Recibido (fecha)'], 30)
RQ = [('RQ-001', 'Cuestionario laboral MDT e IESS', 'Plantilla 2026.1 incorporada', 'Incorporado', 'DO-1', 'Se ejecuta en campo'),
      ('RQ-002', 'Anexo de pasivos y gastos de nómina', 'Saldos 2024/2025 por cuenta', 'Recibido', 'DO-2, DO-4C, DO-6, DO-8, DO-9, DO-10', 'No trae gasto de vacaciones, comisiones, premios ni estipendio de pasantes'),
      ('RQ-003', 'Consolidado del IESS', 'Sierra / Costa (basta una) + Exclusiones del auditor (opcional)', 'Recibido (Sierra) + exclusiones', 'DO-3, DO-3.1, DO-4, DO-6, DO-8, DO-9', 'Código 109 excluido automáticamente'),
      ('RQ-004', 'Mayores de nómina', 'LM_GASTO_NOMINA, LM_PASIVO_IESS_POR_PAGAR, LM_PASIVO_BENEFICIOS_SOCIALES_POR_PAGAR', 'Recibido (10-oct-2026)', 'DO-2, DO-5, DO-6, DO-7, DO-8, DO-9, DO-10', 'Pasivos = anexo; gasto: cuentas del anexo más las que el anexo omite y sí están en el mayor. Falta el mayor de sueldos por pagar (5BS.21204.004)'),
      ('RQ-005', 'Comprobantes de pago IESS', 'Aportes, FR, quirografarios, hipotecarios + extensión de salud (opcional); PDF', 'Recibido (85 PDF)', 'DO-9, DO-10; V10 de DO-4', 'Lectura automática de PDF'),
      ('RQ-006', 'Rol de pagos', 'Pestañas «normal» y «pasantes»', 'Recibido', 'DO-3.1, DO-4, DO-4C, DO-9, DO-10', 'Sin cédula: cruce por nombre'),
      ('RQ-007', 'Solicitudes de acumulación de D13 y D14 (muestra)', 'Muestra 10% generada en DO-4 V08 (RQ-007_Muestreo_Solicitudes_Decimos.xlsx)', 'PENDIENTE', 'DO-4 V08', '15 personas; las mismas para D13 y D14'),
      ('RQ-008', 'Kárdex de vacaciones', 'Modelo RQ-008_Kardex_Vacaciones.xlsx (días gozados/pagados por trabajador)', 'PENDIENTE', 'DO-4V', 'Sin kárdex: observación OBS-VAC en visita preliminar')]
for i, row in enumerate(RQ):
    for j, v in enumerate(row):
        c = wq.cell(9 + i, 1 + j, v); c.font = AR; c.alignment = WR; c.border = BOX
    wq.cell(9 + i, 4).fill = ORG if 'PENDIENTE' in row[3] else GRN
    wq.cell(9 + i, 7).border = BOX; wq.cell(9 + i, 7).font = BLUE
    wq.row_dimensions[9 + i].height = 36
for col, w in zip('ABCDEFG', [9, 30, 40, 22, 30, 42, 14]): wq.column_dimensions[col].width = w

# =========================================================== HALLAZGOS (insumo DO-12)
wh = wb.create_sheet('Hallazgos')
header(wh, 'HALLAZGOS IDENTIFICADOS — insumo para la DO-12', 9, 'DO-0')
th(wh, 8, 1, ['N.º', 'Hallazgo', 'Ref. PT', 'Importe', 'Naturaleza', 'Estado', 'Acción requerida', 'Responsable', 'Fecha'], 30)
H = [('Provisión de vacaciones en exceso: el cliente provisiona ≈5,25% de la base vs 1/24 (4,17%). Sin kárdex por trabajador el pasivo no está soportado (DO-4V).', 'DO-4C / DO-6 / DO-4V', 24813.65, 'Ajuste contable', 'Obtener kárdex (RQ-008) y recalcular con la calculadora DO-4V'),
     ('Fondos de reserva pagados en rol a representantes legales sin derecho (' + _S.get('excluidos','') + ').', 'DO-4 V11 / DO-6', _C['excluido_fr'], 'Ajuste / reclasificación', 'Confirmar naturaleza del vínculo (mandato) y tratamiento'),
     ('Base gravada del rol excede la reportada al IESS: posible subdeclaración de aportes.', 'DO-3.1 / DO-8', _C['rol_menos_iess'], 'Cumplimiento IESS', 'Revisar conceptos por trabajador; cuantificar aportes omitidos (≈203,73 personal y 195,95 patronal)'),
     ('Sueldos según rol exceden el gasto en libros (nómina regular; liquidaciones cuadran con el mayor).', 'DO-10', _C['sue_exceso'], 'Por determinar', 'Solicitar el reporte de nómina por centro de costo'),
     ('Pasantías: aporte sobre SBU y estipendio conformes a la Ley de Pasantías (art. 7); ' + _S.get('pasante_exceso','') + ' exceden seis meses: riesgo de relación de dependencia.', 'DO-8', None, 'Cumplimiento / contingencia laboral', 'Criterio legal (sentencia 16-16-IN/22) y regularizar la modalidad'),
     ('Código de relación 06 reportado al IESS en meses de pasantía (' + _S.get('cod06','') + ').', 'DO-3 / DO-3.1', None, 'Cumplimiento IESS', 'Solicitar corrección del código de relación'),
     ('Décimo cuarto: gasto en exceso del devengado.', 'DO-6 / DO-7', _C['d14_exceso'], 'Ajuste menor', 'Revisar provisión de enero'),
     ('Acumulación de décimos: ' + str(_C['n_acum_d13']) + ' trabajadores acumulan D13 (' + str(_C['n_acum_d14']) + ' D14); muestra del 10% pendiente de verificar solicitudes.', 'DO-4 V08', None, 'Cumplimiento / control interno', 'Verificar solicitudes de la muestra (RQ-007)'),
     ('Sueldos por pagar (' + _n(_C['sueldo_pend']) + ', sueldo de diciembre de un trabajador) sin sustento de pago posterior.', 'DO-9', _C['sueldo_pend'], 'Sustento', 'Verificar pago en enero 2026'),
     ('Compensación de cuentas por cobrar a empleados con el décimo tercero y pago separado del décimo.', 'DO-4C / Mayor RQ-004', None, 'Sustento', 'Obtener autorizaciones escritas y detalle de CxC'),
     ('FR pagado en rol en mes con base IESS 0 (' + _S.get('v04_nombres','') + ').', 'DO-4 V04 / DO-6', _C['v04_total'], 'Ajuste menor', 'Revisar el pago'),
     ('IESS por pagar: diferencias residuales menores pagos vs comprobantes.', 'DO-9 (Mayor RQ-004)', None, 'Informativo', 'Registrar notas de crédito en el período del comprobante'),
     ('Ajustes manuales al pasivo de vacaciones y anexo de nómina que omite cuentas de gasto por ' + _n(_C['gasto_solo_mayor']) + '.', 'DO-5 / DO-7 / DO-2', None, 'Sustento', 'Sustentar ajustes y completar el anexo'),
     ('Deficiencias del papel de trabajo anterior: préstamos hipotecario/quirografario cruzados en varios meses; IESS de pasantes desordenado por mes; objetivos copiados entre cédulas.', 'DO-5 a DO-10', None, 'Calidad del papel (interno)', 'Corregido en las nuevas cédulas')]
for i, (t, ref, imp, nat, acc) in enumerate(H):
    rr = 9 + i
    for j, v in enumerate([i + 1, t, ref, imp, nat, 'Abierto', acc, '', '']):
        c = wh.cell(rr, 1 + j, v); c.font = AR; c.alignment = WR; c.border = BOX
    wh.cell(rr, 4).number_format = '#,##0.00;(#,##0.00);"-"'
    wh.row_dimensions[rr].height = 36
for col, w in zip('ABCDEFGHI', [5, 62, 16, 13, 20, 10, 40, 14, 12]): wh.column_dimensions[col].width = w

# =========================================================== NORMATIVA
wn = wb.create_sheet('Normativa')
header(wn, 'BASE NORMATIVA Y REGLAS APLICADAS', 4, 'DO-0')
th(wn, 8, 1, ['Tema', 'Fuente', 'Regla aplicada en las cédulas', 'Código interno (REGLAS)'], 30)
N = [('Décimo tercera remuneración', 'Código del Trabajo, art. 111', 'Base aportada/12; período diciembre–noviembre. Regla: pago mensual. Acumulación (hasta el 24-dic) solo con solicitud escrita en los primeros 15 días de enero, o al inicio de la relación para nuevos ingresos; no requiere renovarse cada año.', 'D13'),
     ('Décimo cuarta remuneración', 'Código del Trabajo, art. 113', 'SBU/360 × días; Sierra/Amazonía agosto–julio (pago 15-ago); Costa/Galápagos marzo–febrero (pago 15-mar); cálculo por bloques regionales.', 'D14 (D14-10)'),
     ('Vacaciones', 'Código del Trabajo, arts. 69, 71, 75 y 76; NIC 19; NIC 8', '15 días anuales; +1 por año excedente de cinco años (desde el 6.º), máx. 15; el empleador elige conceder o pagar los adicionales. Valor = 1/24 de lo percibido en el año (con horas extras, sin décimos). Acumulación legal hasta 3 años para gozar en el 4.º (art. 75); tope de la calculadora 5 años (criterio del socio). Años anteriores contra resultados acumulados (NIC 8).', 'VAC, RL-05'),
     ('Fondos de reserva', 'Código del Trabajo, art. 196; Ley para el Pago Mensual del Fondo de Reserva (RO 644, 29-jul-2009)', '8,33% después del primer año (desde el mes 13); mes de aniversario proporcional. Regla: pago mensual en rol; acumulación en el IESS a solicitud del trabajador.', 'FR (FR-08, FR-09)'),
     ('Materia gravada / aportes', 'Ley de Seguridad Social, art. 11; resoluciones IESS', 'Base imponible = remuneraciones; tasas personal, patronal y CCC; SBU 2025 = 470,00.', '—'),
     ('Pasantías', 'Ley de Pasantías en el Sector Empresarial, arts. 4, 5 y 7 (reforma RO 234-S, 20-ene-2023); sentencia CC 16-16-IN/22', 'Relación civil, sin beneficios del Código del Trabajo; estipendio ≥ 1/3 del SBU; afiliación obligatoria con aporte íntegro de la empresa sobre el SBU vigente; máximo 6 meses sin generar relación de dependencia. La sentencia declaró inconstitucional la reducción del estipendio con efectos diferidos (plazo vencido en ene-2024 sin nueva ley): confirmar criterio legal.', 'RL-03, PAS-01 a PAS-05'),
     ('Representantes legales', 'Código del Trabajo, art. 308 (mandatario); Ley de Seguridad Social, art. 2; IESS código 109', 'Mandatario, no empleado: sin D13, D14, FR ni vacaciones del Código del Trabajo por ese vínculo; afiliación con código 109 (sin relación de dependencia), aporte 17,6% a cargo de la empresa sobre lo percibido. Si figuran con código 06, el auditor los excluye por beneficio y se observa la afiliación.', 'EX-01 a EX-05'),
     ('Rol como fuente', 'Decisión metodológica del socio', 'El rol «normal» es la fuente base: mensualización, liquidaciones, goces y fechas de ingreso; pasivo solo de activos.', 'RL-01 a RL-06'),
     ('Muestreo de atributos', 'NIA 530', 'Solo para solicitudes de acumulación de décimos (DO-4 V08): 10% configurable, partidas clave + sistemática; mismas personas para D13 y D14.', '—'),
     ('Evaluación de incorrecciones', 'NIA 450 / NIA 265', 'Acumulación de diferencias exactas (prueba al 100%, sin materialidad de muestreo ni proyección) y comunicación de deficiencias (DO-12).', '—')]
for i, row in enumerate(N):
    for j, v in enumerate(row):
        c = wn.cell(9 + i, 1 + j, v); c.font = AR; c.alignment = WR; c.border = BOX
    wn.row_dimensions[9 + i].height = 40
wn.cell(20, 1, 'Detalle completo en REGLAS_Beneficios_Sociales_Ecuador.md. Los artículos citados deben verificarse contra el texto vigente al corte del encargo (Memoria AuditBrain M03).').font = IT
for col, w in zip('ABCD', [26, 36, 70, 18]): wn.column_dimensions[col].width = w

wb.active = 0
_wf = wb['Ficha']
_r = max(_wf.max_row + 2, 14)
_wf.cell(_r, 2, 'Año auditado 2026. Cédula construida con datos de la plantilla 2025 (rol, IESS, anexo y comprobantes); se reemplazan con la información 2026 del cliente.').font = Font(name='Arial', size=8, italic=True, color='FFC00000')
wb.save(OUT); print('ok', OUT, 'pasos', len(P))

# ---- JSON para el panel
import json, base64
prog = []
for row in P:
    prueba, ref, aser, obj, paso, proc, ins, crit, res, hall, est = row
    if prueba:
        prog.append(dict(t=prueba, ref=ref, aser=aser, obj=obj, ins=ins, crit=crit, res=res, hall=hall, est=est, pasos=[]))
    prog[-1]['pasos'].append([paso, proc])
data = dict(prog=prog, rq=[list(x) for x in RQ], hall=[[i + 1, t, ref, imp, nat, acc] for i, (t, ref, imp, nat, acc) in enumerate(H)],
            norm=[list(x) for x in N], xlsx=base64.b64encode(open(OUT, 'rb').read()).decode())
json.dump(data, open((_R.CTX.home + '/prog.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('json ok', len(prog), 'pruebas', round(len(data['xlsx']) / 1024), 'KB xlsx b64')
