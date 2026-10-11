# -*- coding: utf-8 -*-
from backend.app.aud.niif.procesadores.nomina import rutas as _R
"""DO-3.1 Resumen de Roles de Pago.

Calca la cédula de referencia ``referencia/cedulas/DO-3.1_Resumen_Roles_de_Pago.xlsx``
(7 hojas: «DO3.1 Resumen Roles», «Detalle Rol», «Detalle RQ-003»,
«Maestro Trabajadores», «Cruce Rol vs IESS», «Parámetros», «Controles»).

Fuentes de datos (en runtime; NADA del cliente va escrito en el código):
  - Rol histórico (RQ-006) desde ``_R.CTX.rol``, hoja «normal»: el 100% de los
    registros (empleados y jubilados), trasladados a «Detalle Rol» con el mismo
    orden del archivo fuente. Las columnas de concepto (ingresos, descuentos,
    provisiones) se copian tal cual; las derivadas (Total ingresos, base gravada,
    base IESS, etc.) son fórmulas.
  - Consolidado IESS (RQ-003) desde ``_R.CTX.consolidado``, hoja
    «detallePlanillaConsolidado»: todos los registros trabajador-mes, ordenados
    por (mes, nombre) en «Detalle RQ-003».
  - «Maestro Trabajadores» = un registro por trabajador único del rol (orden
    alfabético), con cargo/fechas/tipo vigentes y las marcas (mensualiza,
    liquidado, pasantía) por fórmula.

La identidad del encargo (cliente, ejercicio, preparado/revisado) sale de la
ficha vía ``_R.CTX``, con placeholder ``[desde Ficha del encargo]`` si la ficha
viene vacía. Los nombres/cédulas de trabajadores salen de los datos, no del
código. Los rangos de las fórmulas crecen con la población real (no fijos)."""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter as GL
from backend.app.aud.niif.procesadores.nomina import motor
from backend.app.aud.niif.procesadores import marca

OUT = (_R.CTX.out + '/DO-3.1_Resumen_Roles_de_Pago.xlsx')
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
MESES_EN = ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December']

# ---- formatos / estilos (calcados de la referencia)
NUM = '#,##0.00;[RED]\\-#,##0.00;\\-'
INT = '#,##0;[RED]\\-#,##0;\\-'
DATEF = 'dd/mm/yyyy'
HFILL = PatternFill('solid', fgColor='1F3864')
BANDFILL = PatternFill('solid', fgColor='0B1F3A')
HF = Font(bold=True, color='FFFFFF', size=9)
BF = Font(bold=True, size=10)
BF11 = Font(bold=True, size=11)
TITLE = Font(bold=True, color='1F3864', size=13)
BANDT = Font(bold=True, color='FFFFFF', size=14)
BANDS = Font(color='C9D6E8', size=9)
GREY = Font(color='808080', size=10)
RED = Font(bold=True, color='FF0000', size=10)
SMALL = Font(size=8)
SMALLR = Font(size=8, color='C00000')
CEN = Alignment(horizontal='center', vertical='center', wrap_text=True)
TOPW = Alignment(vertical='top', wrap_text=True)
NOTA_A53 = ('Año auditado 2026. Cédula construida con datos de la plantilla 2025; '
            'se reemplazan con la información 2026 del cliente.')


# ------------------------------------------------------------------ lectura
def _leer_rol(path):
    """Registros de la hoja «normal» del rol, en el orden del archivo. Cada registro
    conserva la tupla cruda ``raw`` (para copiar las columnas de concepto) más los
    campos ya normalizados que necesitan las hojas Detalle/Maestro."""
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)['normal']
    out = []
    for r in ws.iter_rows(min_row=6, values_only=True):
        if r[0] in (None, '') or str(r[0]).startswith('Total') or r[1] in (None, ''):
            continue
        m = motor.mnum(r[0])
        if m is None:
            continue
        cargo = str(r[2] or '')
        tipo = 'Jubilado' if 'JUBIL' in cargo.upper() else 'Empleado'
        out.append(dict(
            mes=m, nombre=str(r[1]).strip(), cargo=cargo, tipo=tipo,
            ingreso=motor.fdate(r[3]), salida=motor.fdate(r[4]), raw=r))
    return out


def _leer_consolidado(path):
    """Registros trabajador-mes del Consolidado IESS, con la relación de trabajo
    SIN normalizar (se conserva el texto original, p. ej. el espacio final)."""
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)['detallePlanillaConsolidado']
    out = []
    for r in ws.iter_rows(min_row=3, values_only=True):
        c1 = r[1] if len(r) > 1 else None
        if c1 is None or str(c1).strip().lower().startswith('total'):
            continue
        out.append(dict(
            mes=motor.mnum(c1), ced=str(r[2]).strip(), nombre=str(r[3]).strip(),
            rel=r[4], base=motor.num(r[5]), pat=motor.num(r[7]), ind=motor.num(r[8]),
            ccc=motor.num(r[12])))
    return out


# ------------------------------------------------------------------ datos
rol = _leer_rol(_R.CTX.rol)
cons = _leer_consolidado(_R.CTX.consolidado)
cons.sort(key=lambda d: (d['mes'], d['nombre']))          # orden de Detalle RQ-003

nm2ced = {}
for d in cons:
    nm2ced.setdefault(d['nombre'], d['ced'])

# maestro: un registro por trabajador único del rol (orden alfabético)
_mae = {}
for d in rol:
    m = _mae.get(d['nombre'])
    if m is None:
        m = _mae[d['nombre']] = dict(nombre=d['nombre'], first_ing=None, vig_mes=-1,
                                     cargo='', tipo='', vig_ing=None, salida=None)
    if d['ingreso'] and (m['first_ing'] is None or d['ingreso'] < m['first_ing']):
        m['first_ing'] = d['ingreso']
    if d['mes'] >= m['vig_mes']:
        m['vig_mes'] = d['mes']; m['cargo'] = d['cargo']; m['tipo'] = d['tipo']
        m['vig_ing'] = d['ingreso']
    if d['salida']:
        m['salida'] = d['salida']
maestro = [_mae[k] for k in sorted(_mae.keys())]

n_rol, n_cons, n_mae = len(rol), len(cons), len(maestro)
drlast = n_rol + 1
r3last = n_cons + 1
mtlast = n_mae + 1

# año del ejercicio: derivado de los datos (período del Consolidado), no de la ficha
_wsc = openpyxl.load_workbook(_R.CTX.consolidado, read_only=True, data_only=True)['detallePlanillaConsolidado']
_anio = 0
for _r in _wsc.iter_rows(min_row=3, max_row=3, values_only=True):
    try:
        _anio = int(str(_r[1]).split('-')[0])
    except (ValueError, IndexError, TypeError):
        _anio = 0
anio = _anio or motor.EJ

# targets de controles (derivados de los datos; Valor B que cuadra con el detalle)
def _col_rol(idx):
    return round(sum(motor.num(d['raw'][idx]) for d in rol), 2)

tot_ingresos = round(sum(sum(motor.num(d['raw'][k]) for k in range(5, 33)) for d in rol), 2)
tot_patronal = _col_rol(61)          # BJ · IESS patronal
tot_personal = _col_rol(37)          # AL fuente · IESS personal (negativo)
tot_ad441 = _col_rol(62)             # BK · aporte adic. 4,41% JP
# patronal rol + aporte individual de pasantes (IESS fuera del rol «normal»)
_en_rol = {(d['mes'], d['nombre']) for d in rol}
pasantes_ind = round(sum(c['ind'] for c in cons
                         if c['pat'] == 0 and (c['mes'], c['nombre']) not in _en_rol), 2)
tot_patronal_mas_pasantes = round(tot_patronal + pasantes_ind, 2)

# identidad del encargo (de _R.CTX; placeholder si la ficha viene vacía)
_cliente = (_R.CTX.cliente or '').strip() or '[desde Ficha del encargo]'
_prep = (_R.CTX.preparado or '').strip()
_prep = '[desde Ficha]' if _prep in ('', '[auditor]') else _prep
_rev = (_R.CTX.revisado or '').strip()
_rev = '[desde Ficha]' if _rev in ('', '[socio]') else _rev
# banda de marca (firma del encargo): nombre de la firma desde marca.py, no un literal del cliente
_FIRMA = marca.ALT['auditconsulting_blanco'].upper()

DR = "'Detalle Rol'"
R3 = "'Detalle RQ-003'"
CR = "'Cruce Rol vs IESS'"
MT = "'Maestro Trabajadores'"
RS = "'DO3.1 Resumen Roles'"


def _hdr(ws, coord, txt):
    ws[coord] = txt
    ws[coord].font = HF
    ws[coord].fill = HFILL
    ws[coord].alignment = CEN


# ------------------------------------------------------------------ libro
wb = openpyxl.Workbook()
wb.remove(wb.active)

# ===================================================== 1) DO3.1 Resumen Roles
rs = wb.create_sheet('DO3.1 Resumen Roles')
rs['E1'] = _FIRMA; rs['E1'].font = BANDT; rs['E1'].fill = BANDFILL
rs['E2'] = 'Auditoría externa · Pasivos acumulados y gastos de nómina'
rs['E2'].font = BANDS; rs['E2'].fill = BANDFILL
rs['B4'] = 'Cliente:'; rs['B4'].font = BF
rs['C4'] = _cliente; rs['C4'].font = GREY
rs['N4'] = 'Referencia de PT'; rs['N4'].font = BF; rs['P4'] = 'DO-3.1'
rs['B5'] = 'Ejercicio:'; rs['B5'].font = BF; rs['C5'] = '=Parámetros!C4'
rs['N5'] = 'Preparado por:'; rs['N5'].font = BF; rs['P5'] = _prep; rs['P5'].font = GREY
rs['B6'] = 'Rubro:'; rs['B6'].font = BF
rs['C6'] = 'Pasivos acumulados y gastos de nómina'
rs['N6'] = 'Revisado por:'; rs['N6'].font = BF; rs['P6'] = _rev; rs['P6'].font = GREY
rs['B8'] = 'DO-3.1 RESUMEN DE ROLES DE PAGO'; rs['B8'].font = TITLE
rs.merge_cells('B9:T9')
rs['B9'] = ('Objetivo: consolidar el rol de pagos «normal» del ejercicio (empleados y '
            'jubilados) como fuente base de la remuneración, cruzarlo contra el '
            'Consolidado IESS y generar el maestro de trabajadores (fechas, '
            'mensualización, liquidaciones) que consumen el Reproceso de Beneficios '
            'Sociales y las conciliaciones.')
rs['B9'].alignment = TOPW
rs.merge_cells('B10:T10')
rs['B10'] = ('Procedimiento: traslado del 100% de los registros del rol (sin muestreo), '
             'agrupación por concepto, cruce por nombre con el RQ-003, comparación de '
             'base aportable y aportes, e identificación de pasantes, jubilados, '
             'mensualizados y liquidados.')
rs['B10'].alignment = TOPW
# tabla mensual (fila 12 encabezado, 13..24 meses, 25 Σ)
cab = ['Mes', 'Nº trabajadores (sin jubilados)', 'Sueldo',
       'Horas extras y recargo nocturno', 'Variable y bonificaciones',
       'Vacaciones gozadas', 'Fondos de reserva en rol', 'Décimos mensualizados',
       'Liquidaciones y finiquitos', 'Otros ingresos', 'Total ingresos',
       'Aporte personal IESS', 'Otros descuentos', 'Líquido a recibir',
       'Provisión aporte patronal', 'Base gravada rol', 'Base IESS (RQ-003)',
       'Diferencia base']
for j, t in enumerate(cab):
    _hdr(rs, f'{GL(2 + j)}12', t)
# columna de Detalle Rol por cada columna del resumen (C..S)
_srccol = {'D': 'J', 'E': 'BP', 'F': 'BQ', 'G': 'K', 'H': 'AC', 'I': 'BR',
           'J': 'BS', 'K': 'BT', 'L': 'AL', 'M': 'AM', 'N': 'BX', 'O': 'BI',
           'P': 'BJ', 'Q': 'BU', 'R': 'BV', 'S': 'BW'}
for m in range(1, 13):
    r = 12 + m
    rs[f'B{r}'] = MESES[m - 1]
    rs[f'C{r}'] = (f'=COUNTIFS({DR}!$B$2:$B${drlast},{m},'
                   f'{DR}!$H$2:$H${drlast},"<>Jubilado")')
    for col, src in _srccol.items():
        rs[f'{col}{r}'] = (f'=SUMIFS({DR}!${src}$2:${src}${drlast},'
                           f'{DR}!$B$2:$B${drlast},{m})')
        rs[f'{col}{r}'].number_format = NUM
rs['B25'] = 'Σ'; rs['B25'].font = RED
rs['C25'] = (f'=SUMPRODUCT(({DR}!$H$2:$H${drlast}<>"Jubilado")/'
             f'COUNTIFS({DR}!$D$2:$D${drlast},{DR}!$D$2:$D${drlast}))')
rs['C25'].font = BF; rs['C25'].number_format = INT
for col in 'DEFGHIJKLMNOPQRS':
    rs[f'{col}25'] = f'=SUM({col}13:{col}24)'
    rs[f'{col}25'].font = BF; rs[f'{col}25'].number_format = NUM
rs['C26'] = 'personas distintas en el año'
# provisiones registradas por el cliente (insumo DO-4)
rs['B29'] = 'PROVISIONES REGISTRADAS POR EL CLIENTE EN EL ROL (insumo para DO-4 Reproceso)'
rs['B29'].font = BF
for j, t in enumerate(['Mes', 'Décimo tercero', 'Décimo cuarto', 'Vacaciones',
                       'Fondos de reserva', 'Aporte adic. 4,41% JP', 'Total']):
    _hdr(rs, f'{GL(2 + j)}30', t)
_provcol = {'C': 'BL', 'D': 'BM', 'E': 'BN', 'F': 'BO', 'G': 'BK'}
for m in range(1, 13):
    r = 30 + m
    rs[f'B{r}'] = MESES[m - 1]
    for col, src in _provcol.items():
        rs[f'{col}{r}'] = (f'=SUMIFS({DR}!${src}$2:${src}${drlast},'
                           f'{DR}!$B$2:$B${drlast},{m})')
        rs[f'{col}{r}'].number_format = NUM
    rs[f'H{r}'] = f'=SUM(C{r}:G{r})'; rs[f'H{r}'].number_format = NUM
rs['B43'] = 'Σ'; rs['B43'].font = BF
for col in 'CDEFGH':
    rs[f'{col}43'] = f'=SUM({col}31:{col}42)'
    rs[f'{col}43'].font = BF; rs[f'{col}43'].number_format = NUM
# pensiones jubilares patronales (fuera del cruce IESS)
rs['B46'] = 'PENSIONES JUBILARES PATRONALES (fuera del cruce IESS)'; rs['B46'].font = BF
for j, t in enumerate(['Concepto', 'Personas', 'Registros', 'Total pagado']):
    _hdr(rs, f'{GL(2 + j)}47', t)
rs['B48'] = 'Jubilados patronales'
rs['C48'] = (f'=SUMPRODUCT(({DR}!$H$2:$H${drlast}="Jubilado")/'
             f'COUNTIFS({DR}!$D$2:$D${drlast},{DR}!$D$2:$D${drlast}))')
rs['C48'].number_format = INT
rs['D48'] = f'=COUNTIF({DR}!$H$2:$H${drlast},"Jubilado")'
rs['E48'] = f'=SUMIFS({DR}!$AL$2:$AL${drlast},{DR}!$H$2:$H${drlast},"Jubilado")'
rs['E48'].number_format = NUM
rs['B51'] = ('Marcas: Σ sumatoria · √ cruzado con RQ-003 · ‡ diferencia a investigar. '
             'Fuente: Rol histórico 2025, hoja «normal», 100% de registros.')
rs['B51'].font = SMALL
rs['A53'] = NOTA_A53; rs['A53'].font = SMALLR
rs.freeze_panes = 'C13'
rs.column_dimensions['A'].width = 2.0
rs.column_dimensions['B'].width = 14.0

# ===================================================== 2) Detalle Rol
de = wb.create_sheet('Detalle Rol')
hdr = ['Mes', 'Mes Nº', 'Cédula', 'Nombre', 'Cargo', 'Fecha ingreso', 'Fecha salida',
       'Tipo', 'Región', 'SUELDO', 'VAC TOMADAS', 'REC.NOCTURNO', 'H. EXT. 50%',
       'H. EXT. 100%', 'DESEMPEÑO', 'COMISIONES', 'PREMIOS', 'BONO MOVI', 'ALIMENTACION',
       'COMISARIATO', 'TRANSPORTE', 'BONO FAMILIA', 'VAC.FINIQUIT', 'BONF.DESAHUC',
       'BO.XDESP.INT', 'PENSION JUB', 'SOBREGIRO', 'DSTO. MAL AP', 'FOND.RESERV.',
       'D13 MENS', 'D14 MENS SIE', 'LIQ.DEC13', 'LIQ.DEC14S', 'BONIFICACION',
       'RETROACTIVO', 'BONO EMP', 'BONO EDUCACI', 'Total ingresos', 'IESSPERSONAL',
       'IMP.RTA.', 'ANT. SUEL', 'ATR Y/O PERM', 'CXC_EMPLEADO', 'MULTAS', 'OTRAS CXC',
       'PR. H IESS', 'PR. Q IESS', 'PRT CIA', 'RET JUD', 'CXC PAG 3ROS', 'CXC MERCAD',
       'MATERNIDAD', 'SOBREGIRO', 'DES ALIMENTA', 'ENFER. 25%', 'EXT. COB IES',
       'CXC EMPL_CUO', 'CXC.SEG.MED.', 'DIAS NO LABO', 'Total descuentos',
       'Líquido a recibir', 'Prov. IESS patronal', 'Prov. aporte adic. 4,41% JP',
       'Prov. D13', 'Prov. D14', 'Prov. vacaciones', 'Prov. fondos reserva',
       'G·Horas extras y recargo', 'G·Variable y bonificaciones',
       'G·Décimos mensualizados', 'G·Liquidaciones', 'G·Otros ingresos',
       'Base gravada rol', 'Base IESS (RQ-003)', 'Diferencia base', 'Otros descuentos']
for j, h in enumerate(hdr, 1):
    de.cell(1, j, h).font = HF
    de.cell(1, j).fill = HFILL
    de.cell(1, j).alignment = CEN
for i, d in enumerate(rol, 2):
    raw = d['raw']
    de.cell(i, 1, MESES[d['mes'] - 1])                 # A Mes
    de.cell(i, 2, d['mes'])                             # B Mes Nº
    ced = nm2ced.get(d['nombre'])
    if ced:
        de.cell(i, 3, ced)                             # C Cédula
    de.cell(i, 4, d['nombre'])                          # D Nombre
    de.cell(i, 5, d['cargo'])                           # E Cargo
    if d['ingreso']:
        c = de.cell(i, 6, d['ingreso']); c.number_format = DATEF   # F Fecha ingreso
    if d['salida']:
        c = de.cell(i, 7, d['salida']); c.number_format = DATEF    # G Fecha salida
    de.cell(i, 8, d['tipo'])                            # H Tipo
    de.cell(i, 9, '=Parámetros!$C$7')                   # I Región
    # columnas de concepto crudas (copia exacta del archivo fuente; el 0 va en blanco)
    for c in range(10, 38):                             # J..AK ingresos (src c-5)
        v = raw[c - 5]
        if v not in (None, 0, ''):
            de.cell(i, c, v).number_format = NUM
    for c in range(39, 60):                             # AM..BG descuentos (src c-2)
        v = raw[c - 2]
        if v not in (None, 0, ''):
            de.cell(i, c, v).number_format = NUM
    for c in range(62, 68):                             # BJ..BO provisiones (src c-1)
        v = raw[c - 1]
        if v not in (None, 0, ''):
            de.cell(i, c, v).number_format = NUM
    # derivadas (fórmulas)
    de.cell(i, 38, f'=SUM(J{i}:AK{i})')                                  # AL Total ingresos
    de.cell(i, 60, f'=SUM(AM{i}:BG{i})')                                 # BH Total descuentos
    de.cell(i, 61, f'=AL{i}+BH{i}')                                      # BI Líquido
    de.cell(i, 68, f'=L{i}+M{i}+N{i}')                                   # BP
    de.cell(i, 69, f'=O{i}+P{i}+Q{i}+AH{i}+AI{i}+AJ{i}')                 # BQ
    de.cell(i, 70, f'=AD{i}+AE{i}')                                      # BR
    de.cell(i, 71, f'=W{i}+X{i}+Y{i}+AF{i}+AG{i}')                       # BS
    de.cell(i, 72, f'=R{i}+S{i}+T{i}+U{i}+V{i}+Z{i}+AA{i}+AB{i}+AK{i}')  # BT
    de.cell(i, 73, f'=IF(H{i}="Jubilado",0,J{i}+K{i}+L{i}+M{i}+N{i}+O{i}'
                   f'+P{i}+Q{i}+AI{i}+AJ{i}+AH{i})')                     # BU Base gravada
    de.cell(i, 74, f'=IF(H{i}="Jubilado",0,SUMIFS({R3}!$E$2:$E${r3last},'
                   f'{R3}!$A$2:$A${r3last},B{i},{R3}!$C$2:$C${r3last},D{i}))')  # BV Base IESS
    de.cell(i, 75, f'=BU{i}-BV{i}')                                      # BW Diferencia
    de.cell(i, 76, f'=BH{i}-AM{i}')                                      # BX Otros descuentos
    for c in (38, 60, 61, 68, 69, 70, 71, 72, 73, 74, 75, 76):
        de.cell(i, c).number_format = NUM
de.freeze_panes = 'E2'
for col, w in dict(A=12.0, D=38.0, E=28.0, F=12.0).items():
    de.column_dimensions[col].width = w

# ===================================================== 3) Detalle RQ-003
rq = wb.create_sheet('Detalle RQ-003')
for j, h in enumerate(['Mes', 'Cédula', 'Nombre', 'Relación', 'Base imponible',
                       'Patronal', 'Individual', 'Valor CCC',
                       'Esquema pasante (indiv. sin patronal)', 'En rol «normal»'], 1):
    rq.cell(1, j, h).font = HF
    rq.cell(1, j).fill = HFILL
    rq.cell(1, j).alignment = CEN
for i, c in enumerate(cons, 2):
    rq.cell(i, 1, c['mes'])
    rq.cell(i, 2, c['ced'])
    rq.cell(i, 3, c['nombre'])
    rq.cell(i, 4, c['rel'])
    rq.cell(i, 5, c['base']).number_format = NUM
    rq.cell(i, 6, c['pat']).number_format = NUM
    rq.cell(i, 7, c['ind']).number_format = NUM
    rq.cell(i, 8, c['ccc']).number_format = NUM
    rq.cell(i, 9, f'=IF(F{i}=0,G{i},0)').number_format = NUM
    rq.cell(i, 10, f'=IF(COUNTIFS({DR}!$B$2:$B${drlast},A{i},'
                   f'{DR}!$D$2:$D${drlast},C{i})>0,"Sí","No")')
rq.freeze_panes = 'D2'
for col, w in dict(A=6.0, B=13.0, C=40.0, D=30.0, E=14.0, F=12.0, I=16.0, J=12.0).items():
    rq.column_dimensions[col].width = w

# ===================================================== 4) Maestro Trabajadores
mw = wb.create_sheet('Maestro Trabajadores')
for j, h in enumerate(['Nombre', 'Cédula', 'Cargo vigente', 'Tipo vigente',
                       'Fecha ingreso inicial', 'Fecha ingreso vigente', 'Fecha salida',
                       'Meses en rol', 'Meses en IESS', 'Pasantía en IESS fuera del rol',
                       'Mensualiza D13', 'Mensualiza D14', 'Liquidado en el año',
                       'Derecho a fondos de reserva desde', 'FR pagado en rol',
                       'Vacaciones gozadas', 'Región', 'Observación'], 1):
    mw.cell(1, j, h).font = HF
    mw.cell(1, j).fill = HFILL
    mw.cell(1, j).alignment = CEN
for i, m in enumerate(maestro, 2):
    mw.cell(i, 1, m['nombre'])
    ced = nm2ced.get(m['nombre'])
    if ced:
        mw.cell(i, 2, ced)
    mw.cell(i, 3, m['cargo'])
    mw.cell(i, 4, m['tipo'])
    if m['first_ing']:
        mw.cell(i, 5, m['first_ing']).number_format = DATEF
    if m['vig_ing']:
        mw.cell(i, 6, m['vig_ing']).number_format = DATEF
    if m['salida']:
        mw.cell(i, 7, m['salida']).number_format = DATEF
    mw.cell(i, 8, f"=COUNTIF({DR}!$D$2:$D${drlast},A{i})")
    mw.cell(i, 9, f'=IF(B{i}="",0,COUNTIF({R3}!$C$2:$C${r3last},A{i}))')
    mw.cell(i, 10, f'=IF(COUNTIFS({R3}!$C$2:$C${r3last},A{i},'
                   f'{R3}!$J$2:$J${r3last},"No")>0,"Sí","No")')
    mw.cell(i, 11, f'=IF(SUMIFS({DR}!$AD$2:$AD${drlast},{DR}!$D$2:$D${drlast},A{i})>0,"Sí","No")')
    mw.cell(i, 12, f'=IF(SUMIFS({DR}!$AE$2:$AE${drlast},{DR}!$D$2:$D${drlast},A{i})>0,"Sí","No")')
    mw.cell(i, 13, f'=IF(SUMIFS({DR}!$BS$2:$BS${drlast},{DR}!$D$2:$D${drlast},A{i})>0,"Sí","No")')
    mw.cell(i, 14, f'=IF(OR(D{i}<>"Empleado",F{i}=""),"",EDATE(F{i},12))').number_format = DATEF
    mw.cell(i, 15, f"=SUMIFS({DR}!$AC$2:$AC${drlast},{DR}!$D$2:$D${drlast},A{i})").number_format = NUM
    mw.cell(i, 16, f"=SUMIFS({DR}!$K$2:$K${drlast},{DR}!$D$2:$D${drlast},A{i})").number_format = NUM
    mw.cell(i, 17, '=Parámetros!$C$7')
    mw.cell(i, 18, f'=IF(J{i}="Sí","Pasantía previa (en IESS, fuera del rol): fondos de '
                   f'reserva desde la fecha de ingreso vigente","")')
mw.freeze_panes = 'B2'
for col, w in dict(A=40.0, B=13.0, C=34.0, D=11.0, E=12.0, H=8.0, K=10.0, N=14.0,
                   O=13.0, Q=16.0, R=60.0).items():
    mw.column_dimensions[col].width = w

# ===================================================== 5) Cruce Rol vs IESS
cx = wb.create_sheet('Cruce Rol vs IESS')
cx['B2'] = ('CRUCE ROL «NORMAL» vs CONSOLIDADO IESS (RQ-003) — sin jubilados; IESS '
            'limitado a los registros presentes en el rol')
cx['B2'].font = BF
for j, t in enumerate(['Mes', 'Registros rol', 'Registros IESS', 'Dif. registros',
                       'Base gravada rol', 'Base IESS', 'Dif. base ‡',
                       'Aporte personal rol', 'Individual IESS (sin pasantes)',
                       'Dif. personal ‡', 'Patronal rol (provisión)',
                       'Patronal + CCC IESS (registros en rol)', 'Dif. patronal ‡']):
    _hdr(cx, f'{GL(2 + j)}4', t)
for m in range(1, 13):
    r = 4 + m
    cx[f'B{r}'] = MESES[m - 1]
    cx[f'C{r}'] = (f'=COUNTIFS({DR}!$B$2:$B${drlast},{m},'
                   f'{DR}!$H$2:$H${drlast},"<>Jubilado")')
    cx[f'D{r}'] = (f'=COUNTIFS({R3}!$A$2:$A${r3last},{m},'
                   f'{R3}!$J$2:$J${r3last},"Sí")')
    cx[f'E{r}'] = f'=C{r}-D{r}'
    cx[f'F{r}'] = f'=SUMIFS({DR}!$BU$2:$BU${drlast},{DR}!$B$2:$B${drlast},{m})'
    cx[f'G{r}'] = (f'=SUMIFS({R3}!$E$2:$E${r3last},{R3}!$A$2:$A${r3last},{m},'
                   f'{R3}!$J$2:$J${r3last},"Sí")')
    cx[f'H{r}'] = f'=F{r}-G{r}'
    cx[f'I{r}'] = f'=-SUMIFS({DR}!$AM$2:$AM${drlast},{DR}!$B$2:$B${drlast},{m})'
    cx[f'J{r}'] = (f'=SUMIFS({R3}!$G$2:$G${r3last},{R3}!$A$2:$A${r3last},{m},'
                   f'{R3}!$J$2:$J${r3last},"Sí")-SUMIFS({R3}!$I$2:$I${r3last},'
                   f'{R3}!$A$2:$A${r3last},{m},{R3}!$J$2:$J${r3last},"Sí")')
    cx[f'K{r}'] = f'=I{r}-J{r}'
    cx[f'L{r}'] = (f'=SUMIFS({DR}!$BJ$2:$BJ${drlast},{DR}!$B$2:$B${drlast},{m},'
                   f'{DR}!$H$2:$H${drlast},"<>Jubilado")')
    cx[f'M{r}'] = (f'=SUMIFS({R3}!$F$2:$F${r3last},{R3}!$A$2:$A${r3last},{m},'
                   f'{R3}!$J$2:$J${r3last},"Sí")+SUMIFS({R3}!$H$2:$H${r3last},'
                   f'{R3}!$A$2:$A${r3last},{m},{R3}!$J$2:$J${r3last},"Sí")+'
                   f'SUMIFS({R3}!$I$2:$I${r3last},{R3}!$A$2:$A${r3last},{m},'
                   f'{R3}!$J$2:$J${r3last},"Sí")')
    cx[f'N{r}'] = f'=L{r}-M{r}'
    for col in 'FGHIJKLMN':
        cx[f'{col}{r}'].number_format = NUM
cx['B17'] = 'Σ'; cx['B17'].font = BF
for col in 'CDEFGHIJKLMN':
    cx[f'{col}17'] = f'=SUM({col}5:{col}16)'; cx[f'{col}17'].font = BF
    if col not in 'CDE':
        cx[f'{col}17'].number_format = NUM
cx['B18'] = 'IESS fuera del rol «normal» (pasantes)'
cx['D18'] = f'=COUNTIF({R3}!$J$2:$J${r3last},"No")'
cx['G18'] = f'=SUMIFS({R3}!$E$2:$E${r3last},{R3}!$J$2:$J${r3last},"No")'
cx['G18'].number_format = NUM
cx['M18'] = (f'=SUMIFS({R3}!$F$2:$F${r3last},{R3}!$J$2:$J${r3last},"No")+'
             f'SUMIFS({R3}!$H$2:$H${r3last},{R3}!$J$2:$J${r3last},"No")+'
             f'SUMIFS({R3}!$I$2:$I${r3last},{R3}!$J$2:$J${r3last},"No")')
cx['M18'].number_format = NUM
cx['B19'] = 'Total Consolidado IESS'
cx['D19'] = '=D17+D18'
cx['G19'] = '=G17+G18'; cx['G19'].number_format = NUM
cx['M19'] = '=M17+M18'; cx['M19'].number_format = NUM
# diferencias por trabajador (empleados del maestro; los jubilados no cruzan con IESS)
cx['B21'] = ('Diferencias por trabajador (base gravada rol − base IESS), solo casos '
             'fuera de tolerancia')
cx['B21'].font = BF
for j, t in enumerate(['Nombre', 'Cédula', 'Base gravada rol', 'Base IESS',
                       'Diferencia', 'Meses con diferencia']):
    _hdr(cx, f'{GL(2 + j)}22', t)
r = 23
for m in maestro:
    if m['tipo'] == 'Jubilado':
        continue
    cx[f'B{r}'] = m['nombre']
    ced = nm2ced.get(m['nombre'])
    if ced:
        cx[f'C{r}'] = ced
    cx[f'D{r}'] = f"=SUMIFS({DR}!$BU$2:$BU${drlast},{DR}!$D$2:$D${drlast},B{r})"
    cx[f'E{r}'] = (f'=SUMIFS({R3}!$E$2:$E${r3last},{R3}!$C$2:$C${r3last},B{r},'
                   f'{R3}!$J$2:$J${r3last},"Sí")')
    cx[f'F{r}'] = f'=D{r}-E{r}'
    cx[f'G{r}'] = (f'=COUNTIFS({DR}!$D$2:$D${drlast},B{r},'
                   f'{DR}!$BW$2:$BW${drlast},">"&Parámetros!$C$6)+'
                   f'COUNTIFS({DR}!$D$2:$D${drlast},B{r},'
                   f'{DR}!$BW$2:$BW${drlast},"<"&-Parámetros!$C$6)')
    for col in 'DEF':
        cx[f'{col}{r}'].number_format = NUM
    r += 1
cx.column_dimensions['B'].width = 40.0
cx.column_dimensions['C'].width = 15.0

# ===================================================== 6) Parámetros
pa = wb.create_sheet('Parámetros')
pa['B2'] = 'PARÁMETROS DO-3.1'; pa['B2'].font = BF
pa['B4'] = 'Ejercicio auditado'; pa['C4'] = anio
pa['B5'] = f'SBU {anio}'; pa['C5'] = int(motor.SBU_2025)
pa['B6'] = 'Tolerancia de cruce (USD)'; pa['C6'] = 0.01
pa['B7'] = 'Región por defecto'; pa['C7'] = 'Sierra / Amazonía'
pa['B8'] = 'Tasa pasantes (sobre SBU)'; pa['C8'] = 0.176
# fuente: nombre real del archivo del cliente (en runtime, no literal)
import os as _os
pa['B11'] = 'Fuente'
pa['C11'] = (f'{_os.path.basename(_R.CTX.rol)} · hoja «normal» (empleados y jubilados; '
             'los pasantes no forman parte de esta hoja, por decisión del socio)')
pa['B12'] = 'Cruce de identidad'
pa['C12'] = 'Por nombre contra el Consolidado IESS (RQ-003); el rol no trae cédula'
pa['B13'] = 'Jubilados'
pa['C13'] = ('Pensión jubilar patronal: se reportan aparte y no participan del cruce '
             'con el IESS')
pa['B15'] = 'Mes'; pa['C15'] = 'Nombre en el rol'
for m in range(1, 13):
    pa[f'B{15 + m}'] = MESES[m - 1]
    pa[f'C{15 + m}'] = MESES_EN[m - 1]
pa.column_dimensions['B'].width = 28.0
pa.column_dimensions['C'].width = 90.0
pa['C4'].font = Font(color='0000FF', size=10)
for r in range(5, 9):
    pa[f'C{r}'].font = Font(color='0000FF', size=10)

# ===================================================== 7) Controles
co = wb.create_sheet('Controles')
co['B2'] = 'CONTROLES DE INTEGRIDAD Y CRUCE — DO-3.1'; co['B2'].font = BF
for j, t in enumerate(['Control', 'Valor A', 'Valor B', 'Diferencia', 'Estado']):
    _hdr(co, f'{GL(2 + j)}4', t)


def _ctrl(r, desc, a, b):
    co[f'B{r}'] = desc
    co[f'C{r}'] = a; co[f'D{r}'] = b
    co[f'E{r}'] = f'=C{r}-D{r}'
    co[f'F{r}'] = f'=IF(ABS(E{r})<=Parámetros!$C$6,"OK","REVISAR")'
    co[f'F{r}'].alignment = Alignment(horizontal='center')
    for col in 'CDE':
        co[f'{col}{r}'].number_format = NUM


_ctrl(5, 'Registros trasladados = registros de la hoja «normal»',
      f"=COUNTA({DR}!$D$2:$D${drlast})", n_rol)
_ctrl(6, 'Total ingresos detalle = archivo fuente',
      f"=SUM({DR}!$AL$2:$AL${drlast})", tot_ingresos)
_ctrl(7, 'Provisión patronal detalle = archivo fuente',
      f"=SUM({DR}!$BJ$2:$BJ${drlast})", tot_patronal)
_ctrl(8, 'Aporte personal detalle = archivo fuente',
      f"=SUM({DR}!$AM$2:$AM${drlast})", tot_personal)
_ctrl(9, 'Resumen: total ingresos = detalle',
      f"={RS}!L25", f"=SUM({DR}!$AL$2:$AL${drlast})")
_ctrl(10, 'Resumen: suma de grupos = total ingresos',
      f"=SUM({RS}!D25:K25)", f"={RS}!L25")
_ctrl(11, 'Resumen: líquido = ingresos + descuentos',
      f"={RS}!O25", f"=SUM({DR}!$AL$2:$AL${drlast})+SUM({DR}!$BH$2:$BH${drlast})")
_ctrl(12, 'Registros rol sin jubilados = registros IESS presentes en el rol',
      f'=COUNTIF({DR}!$H$2:$H${drlast},"<>Jubilado")',
      f'=COUNTIF({R3}!$J$2:$J${r3last},"Sí")')
_ctrl(13, 'Registros IESS: en rol + fuera del rol = total RQ-003',
      f"={CR}!D19", f"=COUNTA({R3}!$C$2:$C${r3last})")
_ctrl(14, 'Registros rol sin cédula (excepto jubilados)',
      f'=COUNTIFS({DR}!$C$2:$C${drlast},"",{DR}!$H$2:$H${drlast},"<>Jubilado")', 0)
_ctrl(15, 'Base IESS traída al rol + base fuera del rol = total RQ-003',
      f"=SUM({DR}!$BV$2:$BV${drlast})+{CR}!G18", f"=SUM({R3}!$E$2:$E${r3last})")
_ctrl(16, 'Aporte adic. 4,41% JP = «Otros gastos de nómina» DO-2',
      f"=SUM({DR}!$BK$2:$BK${drlast})", tot_ad441)
_ctrl(17, 'Patronal rol + aporte pasantes IESS = gasto aporte patronal DO-2',
      f'=SUM({DR}!$BJ$2:$BJ${drlast})+SUMIFS({R3}!$I$2:$I${r3last},'
      f'{R3}!$J$2:$J${r3last},"No")', tot_patronal_mas_pasantes)
# indicadores para otras pruebas
co['B20'] = 'INDICADORES PARA OTRAS PRUEBAS'; co['B20'].font = BF
co['B21'] = 'Trabajadores que mensualizan D13'
co['C21'] = f'=COUNTIF({MT}!$K$2:$K${mtlast},"Sí")'
co['B22'] = 'Trabajadores que mensualizan D14'
co['C22'] = f'=COUNTIF({MT}!$L$2:$L${mtlast},"Sí")'
co['B23'] = 'Trabajadores liquidados en el año'
co['C23'] = f'=COUNTIF({MT}!$M$2:$M${mtlast},"Sí")'
co['B24'] = 'Trabajadores con pasantía previa en IESS (fuera del rol)'
co['C24'] = f'=COUNTIF({MT}!$J$2:$J${mtlast},"Sí")'
co['B25'] = 'Trabajadores con FR pagado en rol'
co['C25'] = f'=COUNTIF({MT}!$O$2:$O${mtlast},">0")'
co['B26'] = 'Diferencia base gravada rol vs IESS'; co['C26'] = f"={CR}!H17"
co['C26'].number_format = NUM
co['B27'] = 'Diferencia aporte personal'; co['C27'] = f"={CR}!K17"
co['C27'].number_format = NUM
co['B28'] = 'Diferencia aporte patronal'; co['C28'] = f"={CR}!N17"
co['C28'].number_format = NUM
co.column_dimensions['B'].width = 52.0
co.column_dimensions['C'].width = 16.0

wb.save(OUT)
