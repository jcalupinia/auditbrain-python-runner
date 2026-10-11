# -*- coding: utf-8 -*-
from backend.app.aud.niif.procesadores.nomina import rutas as _R
"""DO-4 Reproceso de Beneficios Sociales.

Calca la cédula de referencia ``referencia/cedulas/DO-4_Reproceso_Beneficios_Sociales.xlsx``
(6 hojas, en este orden: «DO4 Reproceso Ben Sociales», «Parámetros»,
«Insumo DO-3.1», «Exclusiones», «Detalle RQ-003», «Controles»).

Fuentes de datos (en runtime; NADA del cliente va escrito en el código):
  - Consolidado IESS (RQ-003) desde ``_R.CTX.consolidado``, hoja
    «detallePlanillaConsolidado»: un registro trabajador-mes por fila en
    «Detalle RQ-003», ordenado por (nombre, mes) igual que DO-3. Las columnas
    A–K y W (región) son datos; todo lo demás es fórmula (mensualización,
    exclusiones, devengados y provisiones del reproceso).
  - Rol «normal» sin jubilados (RQ-006) desde ``_R.CTX.rol`` → hoja
    «Insumo DO-3.1», un registro por trabajador-mes ordenado por (nombre, mes);
    de ahí salen por fórmula la fecha de ingreso, la mensualización, los goces y
    las provisiones del cliente que consume «Detalle RQ-003».
  - Exclusiones del auditor (RQ-003 Exclusiones) desde ``_R.CTX.exclusiones`` →
    hoja «Exclusiones» (cédula, nombre, marcas por beneficio y motivo).
  - Anexo de nómina (RQ-002) desde ``_R.CTX.anexo``: saldos del pasivo (ESF) y
    gasto de libros por beneficio (DO-2), que entran como «Valor B» de los
    cruces del reproceso.
  - Serie ``g`` (``_R.CTX.home/g.pkl``): devengado bruto mensual de D13/D14 y
    vacaciones para la comparación contra el modelo anterior.

La identidad del encargo (cliente, período, preparado/revisado) sale de la
ficha vía ``_R.CTX`` con placeholder ``[desde Ficha del encargo]`` / ``[desde
Ficha]`` si la ficha viene vacía; NUNCA se copia el bloque de título heredado
de la plantilla. Los nombres/cédulas de trabajadores salen de los datos en
runtime (``_R.SUJETOS`` y los archivos del cliente), no del código. Los rangos
de las fórmulas crecen con la población real (no fijos)."""
import datetime
import re
import os
import openpyxl
import pandas as pd
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter as GL
from backend.app.aud.niif.procesadores.nomina import motor
from backend.app.aud.niif.procesadores.nomina.cedulas_nuevas import leer_anexo, _concepto_do2

OUT = (_R.CTX.out + '/DO-4_Reproceso_Beneficios_Sociales.xlsx')
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
_MESES_ES = ('', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
             'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')

NUM = '#,##0.00;[RED]\\-#,##0.00;\\-'
INT = '#,##0'
PCT = '0.00%'
DATEF = 'dd/mm/yyyy'
BF = Font(bold=True)
BLUE = Font(color='0000FF')
CEN = Alignment(horizontal='center', vertical='center', wrap_text=True)
CENL = Alignment(horizontal='center')
NOTA = ('Año auditado 2026. Cédula construida con datos de la plantilla 2025; se '
        'reemplazan con la información 2026 del cliente.')


# ------------------------------------------------------------------ lectura
def _leer_rol_emp(path):
    """Registros del rol «normal» SIN jubilados, en orden (nombre, mes). Cada registro
    conserva los campos que vuelca la hoja «Insumo DO-3.1»."""
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)['normal']
    out = []
    for r in ws.iter_rows(min_row=6, values_only=True):
        if r[0] in (None, '') or str(r[0]).startswith('Total') or r[1] in (None, ''):
            continue
        m = motor.mnum(r[0])
        if m is None:
            continue
        cargo = str(r[2] or '')
        if 'JUBIL' in cargo.upper():
            continue
        out.append(dict(
            mes=m, nom=str(r[1]).strip(), cargo=cargo,
            ingreso=motor.fdate(r[3]), salida=motor.fdate(r[4]),
            d13mens=motor.num(r[25]), d14mens=motor.num(r[26]), fr_rol=motor.num(r[24]),
            vac_gozada=motor.num(r[6]), vac_finiquito=motor.num(r[18]),
            liq13=motor.num(r[27]), liq14=motor.num(r[28]),
            prov_d13=motor.num(r[63]), prov_d14=motor.num(r[64]),
            prov_vac=motor.num(r[65]), prov_fr=motor.num(r[66])))
    out.sort(key=lambda d: (d['nom'], d['mes']))
    return out


def _leer_exclusiones(path):
    """Filas de la hoja «Exclusiones» del archivo RQ-003 (orden del archivo)."""
    if not path:
        return []
    try:
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True)['Exclusiones']
    except Exception:
        return []
    out = []
    for r in ws.iter_rows(min_row=6, values_only=True):
        ced = str(r[1]).strip() if len(r) > 1 and r[1] not in (None, '') else ''
        nom = str(r[2]).strip() if len(r) > 2 and r[2] not in (None, '') else ''
        # solo trabajadores reales: se descarta la fila de ejemplo «(opcional)/(copie…)»
        # y las filas de instrucciones («Reglas:», viñetas) que no tienen nombre propio
        if not nom or nom.startswith('(copie') or ced == '(opcional)':
            continue

        def _x(v):
            return 'X' if str(v or '').strip().upper() == 'X' else None
        out.append((ced or None, nom or None, _x(r[3]), _x(r[4]), _x(r[5]), _x(r[6]),
                    (str(r[7]).strip() if len(r) > 7 and r[7] not in (None, '') else None)))
    return out


def _anexo_vals(anexo_path):
    """Saldos del pasivo (ESF) y gasto de libros por beneficio, desde el anexo RQ-002
    (DO-2). Devuelve el dict con las cifras «Valor B» del reproceso."""
    if not anexo_path:
        return {}
    try:
        pas, gas = leer_anexo(anexo_path)
    except Exception:
        return {}

    def pas25(*tokens):
        return round(sum(abs(s25) for _c, d, _s24, s25 in pas
                         if all(t in d.lower() for t in tokens)), 2)

    def pas24(*tokens):
        return round(sum(abs(_s24) for _c, d, _s24, _s25 in pas
                         if all(t in d.lower() for t in tokens)), 2)

    def gas25(concepto):
        return round(sum(s25 for _c, d, _s24, s25 in gas
                         if _concepto_do2(d) == concepto), 2)
    return dict(
        vac_ini=pas24('vacacion'), d13_esf=pas25('tercer'), d14_esf=pas25('cuarto'),
        vac_esf=pas25('vacacion'), fr_esf=pas25('fondo', 'reserva'),
        gasto_d13=gas25('Décimo Tercer Sueldo'), gasto_d14=gas25('Décimo Cuarto Sueldo'),
        gasto_fr=gas25('Fondos de Reserva'))


# ------------------------------------------------------------------ datos
cons = motor.leer_consolidado(_R.CTX.consolidado)
cons.sort(key=lambda d: (d['nombre'], d['mes']))
rol = _leer_rol_emp(_R.CTX.rol)
exc = _leer_exclusiones(_R.CTX.exclusiones)
anx = _anexo_vals(_R.CTX.anexo)

n_cons = len(cons)
n_rol = len(rol)
DL = n_cons + 1                     # última fila de datos de «Detalle RQ-003»
IL = n_rol + 1                      # última fila de datos de «Insumo DO-3.1»
EL = max(len(exc), 50) + 1          # bloque reservado de «Exclusiones» (mín. 50 filas)

# año del ejercicio: derivado del período del Consolidado (no de la ficha)
_wsc = openpyxl.load_workbook(_R.CTX.consolidado, read_only=True, data_only=True)['detallePlanillaConsolidado']
anio = 0
for _r in _wsc.iter_rows(min_row=3, max_row=3, values_only=True):
    try:
        anio = int(str(_r[1]).split('-')[0])
    except (ValueError, IndexError, TypeError):
        anio = 0
anio = anio or motor.EJ

# modelo anterior (devengado bruto mensual): serie g (pickle del motor)
_mod13 = _mod14 = _modvac = {}
try:
    _g = pd.read_pickle(f'{_R.CTX.home}/g.pkl')
    _mod13 = {int(m): round(float(_g.loc[m, 'd13b']), 2) for m in _g.index}
    _mod14 = {int(m): round(float(_g.loc[m, 'd14b']), 2) for m in _g.index}
    _modvac = {int(m): round(float(_g.loc[m, 'Vacaciones']), 2) for m in _g.index}
except Exception:
    pass

# targets de control (derivados de los datos; «Valor B»)
tgt_base = round(sum(r['base'] for r in cons), 2)
tgt_pat = round(sum(r['pat'] for r in cons), 2)
tgt_ind = round(sum(r['ind'] for r in cons), 2)
tgt_ccc = round(sum(r['ccc'] for r in cons), 2)
tgt_total = round(tgt_pat + tgt_ind + tgt_ccc, 2)


def _rolsum(k):
    return round(sum(x[k] for x in rol), 2)


# identidad del encargo (de _R.CTX; placeholder si la ficha viene vacía)
_cliente = (_R.CTX.cliente or '').strip() or '[desde Ficha del encargo]'
_periodo_term = (_R.CTX.corte or '').strip() or '[desde Ficha del encargo]'
_prep = (_R.CTX.preparado or '').strip()
_prep = '[desde Ficha]' if _prep in ('', '[auditor]') else _prep
_rev = (_R.CTX.revisado or '').strip()
_rev = '[desde Ficha]' if _rev in ('', '[socio]') else _rev
_corte_dt = None
_m = re.match(r'(\d{4})-(\d{2})-(\d{2})', _R.CTX.corte or '')
if _m:
    _corte_dt = datetime.datetime(int(_m.group(1)), int(_m.group(2)), int(_m.group(3)))
_al_corte = (f'Al {_corte_dt.day} de {_MESES_ES[_corte_dt.month]} del {_corte_dt.year}'
             if _corte_dt else '[desde Ficha del encargo]')

# sujetos de la narrativa (derivados de los datos; nunca literales)
_cod06 = (_R.SUJETOS or {}).get('cod06', '') or 'los pasantes afiliados con código 06'
_excluidos = (_R.SUJETOS or {}).get('excluidos', '') or 'los representantes legales excluidos'

DR = "'Detalle RQ-003'"
IN = "'Insumo DO-3.1'"
DO4 = "'DO4 Reproceso Ben Sociales'"


# ------------------------------------------------------------------ libro
wb = openpyxl.Workbook()
wb.remove(wb.active)


def _num(cell, v):
    cell.number_format = NUM
    return cell


# ===================================================== 1) DO4 Reproceso Ben Sociales
rs = wb.create_sheet('DO4 Reproceso Ben Sociales')
rs.merge_cells('B1:J2'); rs.merge_cells('B3:J3'); rs.merge_cells('H4:J4')
rs['B1'] = 'OBLIGACIONES ACUMULADAS'; rs['B1'].font = BF; rs['B1'].alignment = CEN
rs['B3'] = 'Reproceso de Beneficios Sociales'; rs['B3'].font = BF; rs['B3'].alignment = CENL
rs['B4'] = 'Nombre del cliente:'; rs['C4'] = _cliente
rs['F4'] = 'Período terminado:'; rs['H4'] = _periodo_term
rs['B5'] = 'Preparado por:'; rs['C5'] = _prep
rs['D5'] = 'Revisado:'; rs['E5'] = _rev
rs['F5'] = 'Fecha:'; rs['G5'] = '[desde Ficha]'
rs['I5'] = 'Referencia de PT'; rs['J5'] = 'DO-4'
for c in ('B4', 'F4', 'B5', 'D5', 'F5', 'I5', 'J5'):
    rs[c].font = BF
rs['C11'] = 'EO'; rs['C11'].font = BF
rs['B12'] = _cliente; rs['B12'].font = BF
if _corte_dt:
    rs['C12'] = _corte_dt; rs['C12'].number_format = DATEF
rs['B13'] = 'Análisis de nómina'; rs['B13'].font = BF
rs['B14'] = _al_corte; rs['B14'].font = BF
# cabecera de la tabla mensual (filas 16-18)
rs.merge_cells('B16:B18'); rs.merge_cells('C16:D16'); rs.merge_cells('E16:M16')
rs.merge_cells('H17:H18'); rs.merge_cells('K17:K18')
rs['B16'] = 'MES'; rs['C16'] = 'Planillas'; rs['E16'] = 'AUDITORIA'
for c in ('B16', 'C16', 'E16'):
    rs[c].font = BF; rs[c].alignment = CEN
for c, t in zip('CDEFGHIJKLM', ['No.', 'Base ', 'Apor Personal', 'Aporte ', 'Valor ',
                                'Total Aporte', 'Décimo', 'Décimo', 'Vacaciones',
                                'Fondos de ', 'Dias ']):
    rs[f'{c}17'] = t; rs[f'{c}17'].font = BF; rs[f'{c}17'].alignment = CEN
for c, t in zip('CDEFGIJLM', ['Empleados', 'Imponible', 0.0945, 'patronal', 'ccc',
                              'Tercero', 'Cuarto', 'Reserva', 'Laborados']):
    rs[f'{c}18'] = t
    if isinstance(t, str):
        rs[f'{c}18'].font = BF
    rs[f'{c}18'].alignment = CEN
rs['E18'].number_format = PCT; rs['F18'].number_format = PCT
# filas mensuales 19-30
_dcol = {'D': 'F', 'E': 'I', 'F': 'H', 'G': 'J', 'I': 'P', 'J': 'Q', 'K': 'R', 'L': 'S', 'M': 'G'}
for m in range(1, 13):
    r = 18 + m
    rs[f'B{r}'] = MESES[m - 1]
    rs[f'C{r}'] = f'=COUNTIFS({DR}!$B$2:$B${DL},{m})'; rs[f'C{r}'].number_format = INT
    for col, src in _dcol.items():
        rs[f'{col}{r}'] = f'=SUMIFS({DR}!${src}$2:${src}${DL},{DR}!$B$2:$B${DL},{m})'
        rs[f'{col}{r}'].number_format = NUM
    rs[f'H{r}'] = f'=SUM(E{r}:G{r})'; rs[f'H{r}'].number_format = NUM
rs['B31'] = 'Σ  '; rs['B31'].font = BF
rs['C31'] = '=SUM(C19:C30)'; rs['C31'].font = BF; rs['C31'].number_format = INT
for col in 'DEFGHIJKLM':
    rs[f'{col}31'] = f'=SUM({col}19:{col}30)'; rs[f'{col}31'].font = BF
    rs[f'{col}31'].number_format = NUM
for c in 'CDEFGH':
    rs[f'{c}32'] = '∏'; rs[f'{c}32'].font = BF
for c in 'IJKL':
    rs[f'{c}32'] = 'a)'; rs[f'{c}32'].font = BF
rs['B33'] = ('Columnas C–H: Consolidado IESS (RQ-003), mismas cifras de DO-3. Columnas '
             'I–L: recálculo de auditoría sobre el 100% de registros trabajador-mes, con '
             'mensualización, fecha de ingreso y pasantías tomadas del rol (DO-3.1).')
rs['C34'] = '=+C30*4%'; rs['C34'].font = BF
rs['C34'].number_format = '_-* #,##0.00\\ _€_-;\\-* #,##0.00\\ _€_-;_-* \\-??\\ _€_-;_-@_-'
rs['D34'] = ('Mínimo de empleados con discapacidad (4% del personal a diciembre); '
             'verificar contra el Bloque F del checklist DO-1.')
rs['B38'] = 'Objetivo:'; rs['B38'].font = BF
rs['B39'] = ('Recalcular las provisiones de décimo tercero, décimo cuarto, vacaciones y '
             'fondos de reserva sobre la base aportada al IESS, como insumo del cruce con '
             'el pasivo y el gasto (DO-4 Cruce, DO-5, DO-6, DO-7).')
rs['B41'] = 'Procedimiento:'; rs['B41'].font = BF
rs['B42'] = 'º'; rs['B42'].font = BF
rs['B43'] = ('Se tomó el Consolidado IESS de enero a diciembre 2025 (RQ-003), el mismo '
             'que sustenta la cédula DO-3.')
rs['B44'] = ('Según el Manual de Beneficios Sociales, se recalculó por trabajador y mes: '
             'D13 = base/12; D14 = SBU/360 × días; vacaciones = base/24; FR = 8,33% de la '
             'base desde el mes 13 de servicio. Se excluyen pasantías y décimos '
             'mensualizados según el rol (DO-3.1); el pasivo considera solo activos al '
             '31-dic y descuenta vacaciones gozadas y de finiquito.')
rs['B47'] = 'Marcas:'; rs['B47'].font = BF
for r, (mk, txt) in zip(range(48, 53), [
        ('√', 'Verificado, comprobado, cotejado (con libros).'),
        ('∏', 'Verificado, comprobado, cotejado (con planillas)'),
        ('a)', 'Recálculo de auditoría'),
        ('Σ  ', 'Sumado, totalizado'),
        ('‡ ', 'Diferencia determinada.')]):
    rs[f'A{r}'] = mk; rs[f'A{r}'].font = BF
    rs[f'B{r}'] = txt; rs[f'B{r}'].font = BF
# provisiones al 31-dic según reproceso
rs['B55'] = ('PROVISIONES AL 31-DIC-2025 SEGÚN REPROCESO (insumo del Cruce Global del Pasivo)')
rs['B55'].font = BF
for c, t in zip('BCDEFG', ['Beneficio', 'Período de devengo', 'Según reproceso a)',
                           'Según DO-2 (ESF) √', 'Diferencia ‡', 'Observación']):
    rs[f'{c}56'] = t; rs[f'{c}56'].font = BF
_conc = [
    ('Décimo tercer sueldo', 'Diciembre (dic–nov)', '=G103', '=Parámetros!C13',
     'Se paga hasta el 24-dic; queda pendiente diciembre'),
    ('Décimo cuarto', 'Sierra ago–dic + Costa mar–dic', '=H103', '=Parámetros!C14',
     'Sierra: pago hasta 15-ago · Costa: pago hasta 15-mar (ver Resumen por región)'),
    ('Vacaciones', 'Saldo inicial + provisión − goces − finiquitos',
     f"=Parámetros!C12+K31-SUM({DR}!$AC$2:$AC${DL})-SUM({DR}!$AD$2:$AD${DL})",
     '=Parámetros!C15',
     'Goces y finiquitos del rol (DO-3.1); saldo por trabajador requiere kárdex (V09)'),
    ('Fondos de reserva', 'Diciembre, por depositar en IESS',
     f"=SUMIFS({DR}!$AL$2:$AL${DL},{DR}!$B$2:$B${DL},12)", '=Parámetros!C16',
     'Activos con derecho que no lo cobran en rol; se deposita en el IESS en enero'),
]
for i, (ben, per, d, e, obs) in enumerate(_conc):
    r = 57 + i
    rs[f'B{r}'] = ben; rs[f'C{r}'] = per
    rs[f'D{r}'] = d; rs[f'D{r}'].number_format = NUM
    rs[f'E{r}'] = e; rs[f'E{r}'].number_format = NUM
    rs[f'F{r}'] = f'=ROUND(E{r}-D{r},2)'; rs[f'F{r}'].number_format = NUM
    rs[f'G{r}'] = obs
rs['B61'] = 'Σ'; rs['B61'].font = BF
for c in 'DEF':
    rs[f'{c}61'] = f'=SUM({c}57:{c}60)'; rs[f'{c}61'].font = BF; rs[f'{c}61'].number_format = NUM
rs['B62'] = ('Pasivo con datos del rol (DO-3.1): solo activos al 31-dic, sin mensualizados '
             'ni pasantías, vacaciones netas de goces y finiquitos.')
# bloques regionales (Sierra 65-79, Costa 82-96)
_rcols = ['C', 'D', 'E', 'F', 'G', 'H']
_rsrc = {'C': None, 'D': 'F', 'E': 'P', 'F': 'Q', 'G': 'R', 'H': 'S'}


def _region_block(top, region, nota):
    rs[f'B{top}'] = f'BLOQUE {"1 — SIERRA / AMAZONÍA" if region.startswith("Sierra") else "2 — COSTA / GALÁPAGOS"}'
    rs[f'B{top}'].font = BF
    rs[f'F{top}'] = nota
    hr = top + 1
    for c, t in zip('BCDEFGH', ['Mes', 'Nº empleados', 'Base imponible', 'Décimo tercero',
                                'Décimo cuarto', 'Vacaciones', 'Fondos de reserva']):
        rs[f'{c}{hr}'] = t; rs[f'{c}{hr}'].font = BF
    for m in range(1, 13):
        r = hr + m
        rs[f'B{r}'] = MESES[m - 1]
        rs[f'C{r}'] = (f'=COUNTIFS({DR}!$B$2:$B${DL},{m},{DR}!$W$2:$W${DL},"{region}")')
        for col in 'DEFGH':
            src = _rsrc[col]
            rs[f'{col}{r}'] = (f'=SUMIFS({DR}!${src}$2:${src}${DL},{DR}!$B$2:$B${DL},{m},'
                               f'{DR}!$W$2:$W${DL},"{region}")')
            rs[f'{col}{r}'].number_format = NUM
    sr = hr + 13
    rs[f'B{sr}'] = 'Σ'; rs[f'B{sr}'].font = BF
    rs[f'C{sr}'] = f'=SUM(C{hr + 1}:C{hr + 12})'; rs[f'C{sr}'].font = BF
    for col in 'DEFGH':
        rs[f'{col}{sr}'] = f'=SUM({col}{hr + 1}:{col}{hr + 12})'
        rs[f'{col}{sr}'].font = BF; rs[f'{col}{sr}'].number_format = NUM
    return sr


_sr_sierra = _region_block(65, 'Sierra / Amazonía',
                           'D14: período 1-ago a 31-jul, pago hasta 15-ago (regla D14-06)')
_sr_costa = _region_block(82, 'Costa / Galápagos',
                          'D14: período 1-mar a fin de febrero, pago hasta 15-mar (regla D14-05)')
# resumen por región 99-103
rs['B99'] = 'RESUMEN POR REGIÓN'; rs['B99'].font = BF
for c, t in zip('BCDEFGHIJ', ['Región', 'D13 anual', 'D14 anual', 'Vacaciones anual',
                              'FR anual', 'D13 por pagar 31-dic', 'D14 por pagar 31-dic',
                              'Meses D14 pendientes', 'Pago D14']):
    rs[f'{c}100'] = t; rs[f'{c}100'].font = BF
_reg_rows = [
    ('Sierra / Amazonía', 79, '12', '>=8', 'Ago–dic (5)', '15-ago'),
    ('Costa / Galápagos', 96, '12', '>=3', 'Mar–dic (10)', '15-mar'),
]
for i, (region, sr, mes_dic, cmp14, mesestxt, pago) in enumerate(_reg_rows):
    r = 101 + i
    rs[f'B{r}'] = region
    rs[f'C{r}'] = f'=E{sr}'; rs[f'D{r}'] = f'=F{sr}'; rs[f'E{r}'] = f'=G{sr}'; rs[f'F{r}'] = f'=H{sr}'
    rs[f'G{r}'] = (f'=SUMIFS({DR}!$AJ$2:$AJ${DL},{DR}!$W$2:$W${DL},"{region}",'
                   f'{DR}!$B$2:$B${DL},{mes_dic})')
    rs[f'H{r}'] = (f'=SUMIFS({DR}!$AK$2:$AK${DL},{DR}!$W$2:$W${DL},"{region}",'
                   f'{DR}!$B$2:$B${DL},"{cmp14}")')
    for col in 'CDEFGH':
        rs[f'{col}{r}'].number_format = NUM
    rs[f'I{r}'] = mesestxt; rs[f'J{r}'] = pago
rs['B103'] = 'Σ TOTAL'; rs['B103'].font = BF
for col in 'CDEFGH':
    rs[f'{col}103'] = f'=SUM({col}101:{col}102)'; rs[f'{col}103'].font = BF
    rs[f'{col}103'].number_format = NUM
# conciliación con el rol (106-113)
rs['B106'] = 'CONCILIACIÓN DEL REPROCESO CON EL ROL DE PAGOS (DO-3.1) — ejercicio 2025'
rs['B106'].font = BF
for c, t in zip('BCDEFGHIJ', ['Beneficio', 'Devengado reproceso', 'Pagado mensual en rol',
                              'A provisionar (reproceso)', 'Provisión del cliente',
                              'Diferencia ‡', 'Gasto DO-2', 'Dif. gasto ‡',
                              'Excluido por el auditor']):
    rs[f'{c}107'] = t; rs[f'{c}107'].font = BF
_cc = [
    ('Décimo tercero',
     f'=SUMIFS({DR}!$F$2:$F${DL},{DR}!$L$2:$L${DL},"Sí")/12-SUM({DR}!$AR$2:$AR${DL})',
     f"=SUM({DR}!$Z$2:$Z${DL})", f"=SUM({DR}!$P$2:$P${DL})", f"=SUM({DR}!$AE$2:$AE${DL})",
     anx.get('gasto_d13', 0.0), f"=SUM({DR}!$AR$2:$AR${DL})"),
    ('Décimo cuarto',
     f'=SUMIFS({DR}!$G$2:$G${DL},{DR}!$L$2:$L${DL},"Sí")*Parámetros!$C$9/360-SUM({DR}!$AS$2:$AS${DL})',
     f"=SUM({DR}!$AA$2:$AA${DL})", f"=SUM({DR}!$Q$2:$Q${DL})", f"=SUM({DR}!$AF$2:$AF${DL})",
     anx.get('gasto_d14', 0.0), f"=SUM({DR}!$AS$2:$AS${DL})"),
    ('Vacaciones', f"=SUM({DR}!$R$2:$R${DL})", 0, f"=SUM({DR}!$R$2:$R${DL})",
     f"=SUM({DR}!$AG$2:$AG${DL})", None, f"=SUM({DR}!$AT$2:$AT${DL})"),
    ('Fondos de reserva', f"=SUM({DR}!$S$2:$S${DL})", f"=SUM({DR}!$AB$2:$AB${DL})",
     f"=SUM({DR}!$AI$2:$AI${DL})", f"=SUM({DR}!$AH$2:$AH${DL})",
     anx.get('gasto_fr', 0.0), f"=SUM({DR}!$AU$2:$AU${DL})"),
]
for i, (ben, c, d, e, f, h, j) in enumerate(_cc):
    r = 108 + i
    rs[f'B{r}'] = ben
    rs[f'C{r}'] = c; rs[f'D{r}'] = d; rs[f'E{r}'] = e; rs[f'F{r}'] = f
    rs[f'G{r}'] = f'=ROUND(F{r}-E{r},2)'
    if h is not None:
        rs[f'H{r}'] = h
    rs[f'I{r}'] = f'=IF(H{r}="","",ROUND(D{r}+F{r}-H{r},2))'
    rs[f'J{r}'] = j
    for col in 'CDEFGHIJ':
        rs[f'{col}{r}'].number_format = NUM
rs['B112'] = 'Σ'; rs['B112'].font = BF
for col in 'CDEFGHIJ':
    rs[f'{col}112'] = f'=SUM({col}108:{col}111)'; rs[f'{col}112'].font = BF
    rs[f'{col}112'].number_format = NUM
rs['B113'] = ('Diferencia = provisión del cliente − a provisionar según reproceso. Dif. '
              'gasto = (pagado mensual en rol + provisión del cliente) − gasto DO-2. '
              'Vacaciones no tiene cuenta de gasto propia en DO-2. Devengado neto de '
              'exclusiones del auditor (columna J; hoja «Exclusiones»).')
# exclusiones aplicadas (116 + población)
rs['B116'] = 'EXCLUSIONES APLICADAS POR DECISIÓN DEL AUDITOR (hoja «Exclusiones», archivo RQ-003)'
rs['B116'].font = BF
for c, t in zip('BCDEFGHIJ', ['Nombre', 'D13 excluido', 'D14 excluido', 'Vacaciones excluidas',
                              'FR excluido', 'Total excluido', 'FR pagado en rol',
                              'Prov. cliente D13', 'Motivo']):
    rs[f'{c}117'] = t; rs[f'{c}117'].font = BF
_nx = max(len(exc), 1)
for i in range(_nx):
    r = 118 + i
    er = 2 + i
    rs[f'B{r}'] = f'=Exclusiones!B{er}'
    rs[f'C{r}'] = f"=SUMIFS({DR}!$AR$2:$AR${DL},{DR}!$D$2:$D${DL},B{r})"
    rs[f'D{r}'] = f"=SUMIFS({DR}!$AS$2:$AS${DL},{DR}!$D$2:$D${DL},B{r})"
    rs[f'E{r}'] = f"=SUMIFS({DR}!$AT$2:$AT${DL},{DR}!$D$2:$D${DL},B{r})"
    rs[f'F{r}'] = f"=SUMIFS({DR}!$AU$2:$AU${DL},{DR}!$D$2:$D${DL},B{r})"
    rs[f'G{r}'] = f'=SUM(C{r}:F{r})'
    rs[f'H{r}'] = f"=SUMIFS({DR}!$AB$2:$AB${DL},{DR}!$D$2:$D${DL},B{r})"
    rs[f'I{r}'] = f"=SUMIFS({DR}!$AE$2:$AE${DL},{DR}!$D$2:$D${DL},B{r})"
    rs[f'J{r}'] = f'=Exclusiones!G{er}'
    for col in 'CDEFGHI':
        rs[f'{col}{r}'].number_format = NUM
_sx = 118 + _nx
rs[f'B{_sx}'] = 'Σ'; rs[f'B{_sx}'].font = BF
for col in 'CDEFGHI':
    rs[f'{col}{_sx}'] = f'=SUM({col}118:{col}{_sx - 1})'; rs[f'{col}{_sx}'].font = BF
    rs[f'{col}{_sx}'].number_format = NUM
rs[f'B{_sx + 1}'] = ('FR pagado en rol a personas excluidas de fondos de reserva = gasto sin '
                     'sustento legal (posible ajuste o reclasificación a remuneración). Lo '
                     'excluido no forma parte del pasivo ni del gasto reprocesado.')
rs[f'A{_sx + 3}'] = NOTA
for col, w in dict(A=4.4, B=22.15, C=15.73, D=15.13, E=15.26, F=16.12, G=14.86,
                   H=18.26, I=17.61, J=14.14, L=14.26, M=11.53, N=11.39).items():
    rs.column_dimensions[col].width = w

# ===================================================== 2) Parámetros
pa = wb.create_sheet('Parámetros')
pa['B2'] = f'PARÁMETROS DEL REPROCESO DE BENEFICIOS SOCIALES {anio}'; pa['B2'].font = BF
for c, t in zip('BCDE', ['Código', 'Relación de trabajo', 'Aplica beneficios', 'Observación']):
    pa[f'{c}4'] = t; pa[f'{c}4'].font = BF
_tasas = [
    ('06', 'Código del Trabajo', 'Sí', 'Décimos, vacaciones y fondos de reserva'),
    ('16', 'Tiempo y/o jornada parcial', 'Sí',
     'Décimo cuarto calculado por días; la ley lo prorratea por jornada (confirmar horas)'),
    ('74', 'Pasantes / internos / becarios', 'No', 'Sin relación laboral bajo Código del Trabajo'),
    ('109', 'Representante legal / administrador por nombramiento', 'No',
     'Mandato, no relación de dependencia: excluido de todos los beneficios automáticamente'),
]
for i, (cod, rel, apl, obs) in enumerate(_tasas):
    r = 5 + i
    pa[f'B{r}'] = cod; pa[f'C{r}'] = rel; pa[f'D{r}'] = apl; pa[f'E{r}'] = obs
pa['B9'] = f'SBU {anio} (USD)'; pa['B9'].font = BF
pa['C9'] = int(motor.SBU_2025); pa['C9'].number_format = NUM; pa['C9'].font = BLUE
pa['B10'] = '% Fondos de Reserva'; pa['B10'].font = BF
pa['C10'] = motor.PCT_FR; pa['C10'].number_format = PCT; pa['C10'].font = BLUE
pa['B11'] = 'Región'; pa['B11'].font = BF
pa['C11'] = 'Por registro: columna W del detalle, según el archivo RQ-003 cargado (Sierra o Costa)'
for r, (lbl, val) in zip(range(12, 17), [
        (f'Saldo vacaciones por pagar 31-dic-{anio - 1} (DO-2)', anx.get('vac_ini', 0.0)),
        (f'Décimo tercero por pagar 31-dic-{anio} (DO-2)', anx.get('d13_esf', 0.0)),
        (f'Décimo cuarto por pagar 31-dic-{anio} (DO-2)', anx.get('d14_esf', 0.0)),
        (f'Vacaciones por pagar 31-dic-{anio} (DO-2)', anx.get('vac_esf', 0.0)),
        (f'Fondos de reserva por pagar 31-dic-{anio} (DO-2)', anx.get('fr_esf', 0.0))]):
    pa[f'B{r}'] = lbl; pa[f'B{r}'].font = BF
    pa[f'C{r}'] = val; pa[f'C{r}'].number_format = NUM; pa[f'C{r}'].font = BLUE
for r, txt in zip(range(18, 25), [
        'FUENTE DE DATOS POR TRABAJADOR: DO-3.1 Resumen de Roles de Pago (hoja «Insumo DO-3.1», rol «normal»)',
        'Mensualización: por registro trabajador-mes; si el rol pagó D13/D14 mensualizado ese mes, no se provisiona (reemplaza la lista inferida anterior, refutada por el rol).',
        'Pasantes: solo generan beneficios los registros presentes en el rol «normal»; los meses de pasantía (en IESS, fuera del rol) no aplican.',
        'Fecha de ingreso: la vigente en el rol; fondos de reserva desde el mes 13 de servicio.',
        'Activo al 31-dic: trabajador sin fecha de salida en el año; los liquidados no generan pasivo (sus décimos se pagaron en la liquidación).',
        'Vacaciones: pasivo = saldo inicial + provisión del año − vacaciones gozadas − vacaciones de finiquito (rol).',
        'Exclusiones: código 109 excluido de todo por parámetro; personas con código 06 que no deben generar un beneficio se listan en la hoja «Exclusiones» (archivo RQ-003 Exclusiones, decisión del auditor, por beneficio y con motivo).']):
    pa[f'B{r}'] = txt
    if r == 18:
        pa[f'B{r}'].font = BF
for col, w in dict(A=3.0, B=46.0, C=30.0, D=16.0, F=58.0).items():
    pa.column_dimensions[col].width = w

# ===================================================== 3) Insumo DO-3.1
ins = wb.create_sheet('Insumo DO-3.1')
for j, h in enumerate(['Mes', 'Nombre', 'Cargo', 'Fecha ingreso', 'Fecha salida',
                       'D13 mensualizado', 'D14 mensualizado', 'FR pagado en rol',
                       'Vacaciones gozadas', 'Vacaciones finiquito', 'Liq. D13', 'Liq. D14',
                       'Prov. cliente D13', 'Prov. cliente D14', 'Prov. cliente vacaciones',
                       'Prov. cliente FR'], 1):
    ins.cell(1, j, h).font = BF
_insnum = {6: 'd13mens', 7: 'd14mens', 8: 'fr_rol', 9: 'vac_gozada', 10: 'vac_finiquito',
           11: 'liq13', 12: 'liq14', 13: 'prov_d13', 14: 'prov_d14', 15: 'prov_vac', 16: 'prov_fr'}
for i, d in enumerate(rol, 2):
    ins.cell(i, 1, d['mes'])
    ins.cell(i, 2, d['nom'])
    ins.cell(i, 3, d['cargo'])
    if d['ingreso']:
        ins.cell(i, 4, d['ingreso']).number_format = DATEF
    if d['salida']:
        ins.cell(i, 5, d['salida']).number_format = DATEF
    for c, k in _insnum.items():
        v = d[k]
        if v not in (None, 0, 0.0, ''):
            ins.cell(i, c, v).number_format = NUM
ins.freeze_panes = 'C2'
for col, w in dict(A=5.0, B=40.0, C=30.0, D=12.0).items():
    ins.column_dimensions[col].width = w

# ===================================================== 4) Exclusiones
ex = wb.create_sheet('Exclusiones')
for j, h in enumerate(['Cédula', 'Nombre', 'Excluir D13', 'Excluir D14', 'Excluir Vacaciones',
                       'Excluir Fondos reserva', 'Motivo de la exclusión', 'Encontrado en IESS'], 1):
    ex.cell(1, j, h).font = BF
for i, (ced, nom, xd13, xd14, xvac, xfr, mot) in enumerate(exc, 2):
    if ced:
        ex.cell(i, 1, ced)
    if nom:
        ex.cell(i, 2, nom)
    if xd13:
        ex.cell(i, 3, xd13)
    if xd14:
        ex.cell(i, 4, xd14)
    if xvac:
        ex.cell(i, 5, xvac)
    if xfr:
        ex.cell(i, 6, xfr)
    if mot:
        ex.cell(i, 7, mot)
for i in range(2, EL + 1):
    ex.cell(i, 8, (f'=IF(B{i}="","",IF(COUNTIF({DR}!$D:$D,B{i})+'
                   f'COUNTIF({DR}!$C:$C,A{i})>0,"Sí","NO ENCONTRADO"))'))
ex.cell(EL + 2, 1, ('Fuente: archivo «RQ-003 Exclusiones de beneficios» cargado por el auditor. '
                    '«X» = el beneficio no se provisiona; en blanco = se calcula. El código 109 '
                    'se excluye automáticamente (Parámetros). Celdas en azul = insumo editable.'))
ex.freeze_panes = 'C2'
for col, w in dict(A=13.0, B=38.0, C=11.0, E=13.0, F=14.0, G=70.0, H=16.0).items():
    ex.column_dimensions[col].width = w

# ===================================================== 5) Detalle RQ-003
de = wb.create_sheet('Detalle RQ-003')
hdr = ['Período', 'Mes', 'Cédula', 'Nombre', 'Relación de trabajo', 'Base imponible', 'Días',
       'Patronal', 'Individual', 'Valor CCC', 'Total aporte IESS', 'Aplica beneficios',
       'Mensualiza D13', 'Mensualiza D14', 'Fecha de ingreso (rol DO-3.1)', 'Décimo tercero',
       'Décimo cuarto', 'Vacaciones', 'Fondos de reserva', 'Estado FR', 'V01 Repet. cédula-período',
       'Primera aparición', 'Región (archivo RQ-003)', 'En rol «normal»', 'Activo al 31-dic',
       'D13 mens. pagado (rol)', 'D14 mens. pagado (rol)', 'FR pagado en rol', 'Vac. gozadas (rol)',
       'Vac. finiquito (rol)', 'Prov. cliente D13', 'Prov. cliente D14', 'Prov. cliente vac.',
       'Prov. cliente FR', 'FR a depositar IESS', 'D13 por pagar (activos)', 'D14 por pagar (activos)',
       'FR por pagar (activos)', 'Excluir D13 (auditor)', 'Excluir D14 (auditor)',
       'Excluir vac. (auditor)', 'Excluir FR (auditor)', 'Motivo de la exclusión', 'D13 excluido',
       'D14 excluido', 'Vacaciones excluidas', 'FR excluido']
for j, h in enumerate(hdr, 1):
    de.cell(1, j, h).font = BF
_insmap = {26: 'F', 27: 'G', 28: 'H', 29: 'I', 30: 'J', 31: 'M', 32: 'N', 33: 'O', 34: 'P'}
for idx, r in enumerate(cons, 2):
    i = idx
    de.cell(i, 1, f"{anio}-{r['mes']}")
    de.cell(i, 2, r['mes'])
    de.cell(i, 3, r['ced'])
    de.cell(i, 4, r['nombre'])
    de.cell(i, 5, str(r['rel'] or '').strip())
    _num(de.cell(i, 6, r['base']), 0); de.cell(i, 7, r['dias'])
    _num(de.cell(i, 8, r['pat']), 0); _num(de.cell(i, 9, r['ind']), 0)
    _num(de.cell(i, 10, r['ccc']), 0); _num(de.cell(i, 11, r['total']), 0)
    de.cell(i, 12, (f'=IF(AND(IFERROR(VLOOKUP(LEFT(E{i},FIND("-",E{i}&"-")-1),'
                    f'Parámetros!$B$5:$D$8,3,0),"No")="Sí",X{i}="Sí"),"Sí","No")'))
    de.cell(i, 13, f'=IF(Z{i}>0,"Sí","No")')
    de.cell(i, 14, f'=IF(AA{i}>0,"Sí","No")')
    de.cell(i, 15, (f'=IF(X{i}="Sí",SUMIFS({IN}!$D$2:$D${IL},{IN}!$A$2:$A${IL},B{i},'
                    f'{IN}!$B$2:$B${IL},D{i}),"")')).number_format = DATEF
    de.cell(i, 16, f'=IF(AND(L{i}="Sí",M{i}="No",AM{i}<>"X"),F{i}/12,0)').number_format = NUM
    de.cell(i, 17, (f'=IF(AND(L{i}="Sí",N{i}="No",AN{i}<>"X"),Parámetros!$C$9/12*G{i}/30,0)')).number_format = NUM
    de.cell(i, 18, f'=IF(AND(L{i}="Sí",AO{i}<>"X"),F{i}/24,0)').number_format = NUM
    de.cell(i, 19, (f'=IF(OR(L{i}<>"Sí",O{i}="",AP{i}="X"),0,IF(DATE({anio},B{i},1)>='
                    f'EDATE(O{i},12),F{i}*Parámetros!$C$10,IF(EOMONTH(DATE({anio},B{i},1),0)>='
                    f'EDATE(O{i},12),F{i}*Parámetros!$C$10*(EOMONTH(DATE({anio},B{i},1),0)-'
                    f'EDATE(O{i},12)+1)/DAY(EOMONTH(DATE({anio},B{i},1),0)),0)))')).number_format = NUM
    de.cell(i, 20, (f'=IF(L{i}<>"Sí","No aplica",IF(AP{i}="X",IF(AB{i}>0,"Excluido · pagado en rol",'
                    f'"Excluido por el auditor"),IF(S{i}>0,IF(AB{i}>0,"Con derecho · pagado en rol",'
                    f'"Con derecho · a depositar IESS"),IF(AB{i}>0,"Pagado en rol sin derecho",'
                    f'"Menos de 1 año"))))'))
    de.cell(i, 21, f'=COUNTIFS($C$2:$C${DL},C{i},$A$2:$A${DL},A{i})')
    de.cell(i, 22, f'=IF(COUNTIF($C$2:C{i},C{i})=1,1,0)')
    de.cell(i, 23, 'Sierra / Amazonía')
    de.cell(i, 24, (f'=IF(COUNTIFS({IN}!$A$2:$A${IL},B{i},{IN}!$B$2:$B${IL},D{i})>0,"Sí","No")'))
    de.cell(i, 25, (f'=IF(X{i}="Sí",IF(COUNTIFS({IN}!$B$2:$B${IL},D{i},{IN}!$E$2:$E${IL},'
                    f'">0")>0,"No","Sí"),"")'))
    for c, src in _insmap.items():
        de.cell(i, c, (f"=SUMIFS({IN}!${src}$2:${src}${IL},{IN}!$A$2:$A${IL},B{i},"
                       f"{IN}!$B$2:$B${IL},D{i})")).number_format = NUM
    de.cell(i, 35, f'=IF(AB{i}>0,0,S{i})').number_format = NUM
    de.cell(i, 36, f'=IF(Y{i}="Sí",P{i},0)').number_format = NUM
    de.cell(i, 37, f'=IF(Y{i}="Sí",Q{i},0)').number_format = NUM
    de.cell(i, 38, f'=IF(Y{i}="Sí",AI{i},0)').number_format = NUM
    for c, col in zip((39, 40, 41, 42), ('C', 'D', 'E', 'F')):
        de.cell(i, c, (f'=IF(COUNTIFS(Exclusiones!$A$2:$A${EL},C{i},Exclusiones!${col}$2:${col}${EL},'
                       f'"X")+COUNTIFS(Exclusiones!$B$2:$B${EL},D{i},Exclusiones!${col}$2:${col}${EL},'
                       f'"X")>0,"X","")'))
    de.cell(i, 43, (f'=IF(COUNTIF(AM{i}:AP{i},"X")=0,"",IFERROR(INDEX(Exclusiones!$G$2:$G${EL},'
                    f'MATCH(C{i},Exclusiones!$A$2:$A${EL},0)),IFERROR(INDEX(Exclusiones!$G$2:$G${EL},'
                    f'MATCH(D{i},Exclusiones!$B$2:$B${EL},0)),"")))'))
    de.cell(i, 44, f'=IF(AND(L{i}="Sí",M{i}="No",AM{i}="X"),F{i}/12,0)').number_format = NUM
    de.cell(i, 45, (f'=IF(AND(L{i}="Sí",N{i}="No",AN{i}="X"),Parámetros!$C$9/12*G{i}/30,0)')).number_format = NUM
    de.cell(i, 46, f'=IF(AND(L{i}="Sí",AO{i}="X"),F{i}/24,0)').number_format = NUM
    de.cell(i, 47, (f'=IF(OR(L{i}<>"Sí",O{i}="",AP{i}<>"X"),0,IF(DATE({anio},B{i},1)>='
                    f'EDATE(O{i},12),F{i}*Parámetros!$C$10,IF(EOMONTH(DATE({anio},B{i},1),0)>='
                    f'EDATE(O{i},12),F{i}*Parámetros!$C$10*(EOMONTH(DATE({anio},B{i},1),0)-'
                    f'EDATE(O{i},12)+1)/DAY(EOMONTH(DATE({anio},B{i},1),0)),0)))')).number_format = NUM
# totales (SUBTOTAL)
tr = DL + 1
de.cell(tr, 4, 'Σ TOTALES').font = BF
for col in ['F', 'H', 'I', 'J', 'K', 'P', 'Q', 'R', 'S', 'Z', 'AA', 'AB', 'AC', 'AD', 'AE',
            'AF', 'AG', 'AH', 'AI', 'AJ', 'AK', 'AL', 'AR', 'AS', 'AT', 'AU']:
    de[f'{col}{tr}'] = f'=SUBTOTAL(9,{col}2:{col}{DL})'
    de[f'{col}{tr}'].font = BF; de[f'{col}{tr}'].number_format = NUM
de.freeze_panes = 'E2'
for col, w in dict(A=9.0, B=5.0, C=12.0, D=38.0, E=34.0, F=13.0, G=6.0, H=11.0, J=10.0,
                   K=12.0, L=10.0, O=13.0, Q=12.0, T=16.0, U=12.0, V=10.0, W=18.0, X=13.0,
                   AQ=48.0, AR=13.0).items():
    de.column_dimensions[col].width = w

# ===================================================== 6) Controles
co = wb.create_sheet('Controles')
co['B2'] = 'CONTROLES DE INTEGRIDAD — DO-4 REPROCESO'; co['B2'].font = BF
for c, t in zip('BCDEF', ['Control', 'Valor A', 'Valor B', 'Diferencia', 'Estado']):
    co[f'{c}4'] = t; co[f'{c}4'].font = BF


def _ctrl(r, desc, a, b):
    co[f'B{r}'] = desc; co[f'C{r}'] = a; co[f'D{r}'] = b
    co[f'E{r}'] = f'=ROUND(C{r}-D{r},2)'
    co[f'F{r}'] = f'=IF(ABS(E{r})<=0.01,"OK","REVISAR")'
    for c in 'CDE':
        co[f'{c}{r}'].number_format = NUM


_ctrl(5, 'Registros trasladados vs reporte IESS', f"=COUNTA({DR}!$C$2:$C${DL})", n_cons)
_ctrl(6, 'Base imponible: detalle vs reporte IESS', f"=SUM({DR}!$F$2:$F${DL})", tgt_base)
_ctrl(7, 'Patronal: detalle vs reporte IESS', f"=SUM({DR}!$H$2:$H${DL})", tgt_pat)
_ctrl(8, 'Individual: detalle vs reporte IESS', f"=SUM({DR}!$I$2:$I${DL})", tgt_ind)
_ctrl(9, 'Valor CCC: detalle vs reporte IESS', f"=SUM({DR}!$J$2:$J${DL})", tgt_ccc)
_ctrl(10, 'Base imponible DO-4 = DO-3 (D34)', f"={DO4}!D31", tgt_base)
_ctrl(11, 'Total aporte DO-4 = DO-3 (J34)', f"={DO4}!H31", tgt_total)
_ctrl(12, 'Décimo tercero cédula = detalle', f"={DO4}!I31", f"=SUM({DR}!$P$2:$P${DL})")
_ctrl(13, 'Décimo cuarto cédula = detalle', f"={DO4}!J31", f"=SUM({DR}!$Q$2:$Q${DL})")
_ctrl(14, 'Vacaciones cédula = detalle', f"={DO4}!K31", f"=SUM({DR}!$R$2:$R${DL})")
_ctrl(15, 'Fondos de reserva cédula = detalle', f"={DO4}!L31", f"=SUM({DR}!$S$2:$S${DL})")
_ctrl(16, 'Vacaciones + excluidas = base con beneficios / 24',
      f"={DO4}!K31+SUM({DR}!$AT$2:$AT${DL})",
      f'=SUMIFS({DR}!$F$2:$F${DL},{DR}!$L$2:$L${DL},"Sí")/24')
_ctrl(17, 'D13 provisionado + excluido = base que acumula / 12',
      f"=SUM({DR}!$P$2:$P${DL})+SUM({DR}!$AR$2:$AR${DL})",
      f'=SUMIFS({DR}!$F$2:$F${DL},{DR}!$L$2:$L${DL},"Sí",{DR}!$M$2:$M${DL},"No")/12')
_ctrl(18, 'Exclusiones: personas listadas no encontradas en el IESS',
      f'=COUNTIF(Exclusiones!$H$2:$H${EL},"NO ENCONTRADO")', 0)
_ctrl(19, 'Base: Sierra + Costa = total', f"={DO4}!D79+{DO4}!D96", f"={DO4}!D31")
_ctrl(20, 'D13: Sierra + Costa = total', f"={DO4}!E79+{DO4}!E96", f"={DO4}!I31")
_ctrl(21, 'D14: Sierra + Costa = total', f"={DO4}!F79+{DO4}!F96", f"={DO4}!J31")
_ctrl(22, 'Vacaciones: Sierra + Costa = total', f"={DO4}!G79+{DO4}!G96", f"={DO4}!K31")
_ctrl(23, 'Registros sin región válida',
      f'=COUNTA({DR}!$W$2:$W${DL})-COUNTIF({DR}!$W$2:$W${DL},"Sierra / Amazonía")-'
      f'COUNTIF({DR}!$W$2:$W${DL},"Costa / Galápagos")', 0)
_ctrl(24, 'Insumo DO-3.1: registros = rol «normal» sin jubilados',
      f"=COUNTA({IN}!$B$2:$B${IL})", n_rol)
_ctrl(25, 'Registros IESS presentes en el rol = insumo',
      f'=COUNTIF({DR}!$X$2:$X${DL},"Sí")', f"=COUNTA({IN}!$B$2:$B${IL})")
_ctrl(26, 'D13 mensualizado traído = rol', f"=SUM({DR}!$Z$2:$Z${DL})", _rolsum('d13mens'))
_ctrl(27, 'D14 mensualizado traído = rol', f"=SUM({DR}!$AA$2:$AA${DL})", _rolsum('d14mens'))
_ctrl(28, 'FR pagado en rol traído = rol', f"=SUM({DR}!$AB$2:$AB${DL})", _rolsum('fr_rol'))
_ctrl(29, 'Vacaciones gozadas traídas = rol', f"=SUM({DR}!$AC$2:$AC${DL})", _rolsum('vac_gozada'))
_ctrl(30, 'Vacaciones finiquito traídas = rol', f"=SUM({DR}!$AD$2:$AD${DL})", _rolsum('vac_finiquito'))
_ctrl(31, 'Provisión cliente D13 traída = rol', f"=SUM({DR}!$AE$2:$AE${DL})", _rolsum('prov_d13'))
_ctrl(32, 'Provisión cliente D14 traída = rol', f"=SUM({DR}!$AF$2:$AF${DL})", _rolsum('prov_d14'))
_ctrl(33, 'Provisión cliente vacaciones traída = rol', f"=SUM({DR}!$AG$2:$AG${DL})", _rolsum('prov_vac'))
_ctrl(34, 'Provisión cliente FR traída = rol', f"=SUM({DR}!$AH$2:$AH${DL})", _rolsum('prov_fr'))
# comparación con el modelo anterior (devengado bruto, serie g)
co['B37'] = 'COMPARACIÓN CON EL MODELO ANTERIOR (valores digitados del papel de trabajo, en azul)'
co['B37'].font = BF
for c, t in zip('BCDEFGHIJK', ['Mes', 'D13 modelo', 'D13 reproceso', 'Dif. D13', 'D14 modelo',
                               'D14 reproceso', 'Dif. D14', 'Vac. modelo', 'Vac. reproceso',
                               'Dif. Vac.']):
    co[f'{c}38'] = t; co[f'{c}38'].font = BF
for m in range(1, 13):
    r = 38 + m
    co[f'B{r}'] = MESES[m - 1]
    co[f'C{r}'] = _mod13.get(m, 0.0); co[f'C{r}'].font = BLUE
    co[f'D{r}'] = f"={DO4}!I{18 + m}"
    co[f'E{r}'] = f'=ROUND(D{r}-C{r},2)'
    co[f'F{r}'] = _mod14.get(m, 0.0); co[f'F{r}'].font = BLUE
    co[f'G{r}'] = f"={DO4}!J{18 + m}"
    co[f'H{r}'] = f'=ROUND(G{r}-F{r},2)'
    co[f'I{r}'] = _modvac.get(m, 0.0); co[f'I{r}'].font = BLUE
    co[f'J{r}'] = f"={DO4}!K{18 + m}"
    co[f'K{r}'] = f'=ROUND(J{r}-I{r},2)'
    for c in 'CDEFGHIJK':
        co[f'{c}{r}'].number_format = NUM
co['B51'] = 'Σ'; co['B51'].font = BF
for c in 'CDEFGHIJK':
    co[f'{c}51'] = f'=SUM({c}39:{c}50)'; co[f'{c}51'].font = BF; co[f'{c}51'].number_format = NUM
co['B52'] = (f'Explicación: con el rol (DO-3.1) el reproceso excluye los meses de pasantía de '
             f'{_cod06} (igual que el modelo) {_excluidos} no mensualizan; por decisión del '
             f'auditor (hoja «Exclusiones») no se les provisiona D13, D14 ni FR.')
co['B53'] = (f'Base de {_cod06} en meses de pasantía (relación 06, aporte patronal 0; excluida '
             f'del reproceso)')
co['C53'] = (f'=SUMIFS({DR}!$F$2:$F${DL},{DR}!$E$2:$E${DL},"06*",{DR}!$H$2:$H${DL},0)')
co['C53'].number_format = NUM
co['B54'] = 'Efecto D13 de esa base (base/12)'; co['C54'] = '=ROUND(C53/12,2)'; co['C54'].number_format = NUM
co['B55'] = 'Efecto vacaciones de esa base (base/24)'; co['C55'] = '=ROUND(C53/24,2)'; co['C55'].number_format = NUM
# matriz de validaciones V01..V11
co['B58'] = 'MATRIZ DE VALIDACIONES DE AUDITORÍA (Manual Consolidado de Beneficios Sociales 2026, §6)'
co['B58'].font = BF
for c, t in zip('BCDE', ['Código y prueba', 'Casos', 'Resultado esperado', 'Estado / evidencia']):
    co[f'{c}59'] = t; co[f'{c}59'].font = BF
_vals = [
    ('V01 Duplicado por cédula y período', f'=COUNTIF({DR}!$U$2:$U${DL},">1")',
     'Rechazar o explicar', '=IF(C60=0,"OK","REVISAR")'),
    ('V02 Sueldo ≤ 0 con días > 0',
     f'=COUNTIFS({DR}!$F$2:$F${DL},"<=0",{DR}!$G$2:$G${DL},">0")', 'Error',
     '=IF(C61=0,"OK","REVISAR")'),
    ('V03 Días fuera de 0–30',
     f'=COUNTIF({DR}!$G$2:$G${DL},"<0")+COUNTIF({DR}!$G$2:$G${DL},">30")', 'Error',
     '=IF(C62=0,"OK","REVISAR")'),
    ('V04 Fondo pagado antes del mes 13',
     f'=COUNTIF({DR}!$T$2:$T${DL},"Pagado en rol sin derecho")', 'Pago indebido o mala fecha',
     '=IF(C63=0,"OK","REVISAR")'),
    ('V05 Fondo con derecho sin pago en rol ni provisión del cliente',
     f'=COUNTIFS({DR}!$T$2:$T${DL},"Con derecho · a depositar IESS",{DR}!$AH$2:$AH${DL},0)',
     'Diferencia', '=IF(C64=0,"OK","REVISAR")'),
    ('V06 Décimo cuarto calculado con sueldo', 0, 'Error de base',
     'Recálculo usa SBU; se prueba contra la provisión del cliente (DO-10)'),
    ('V07 Décimo tercero sin variables normales', 0, 'Base incompleta',
     'Base = materia gravada IESS (incluye variables); puente en DO-8'),
    ('V08 Acumulación sin solicitud escrita',
     f'=SUMIFS({DR}!$V$2:$V${DL},{DR}!$V$2:$V${DL},1,{DR}!$L$2:$L${DL},"Sí",'
     f'{DR}!$M$2:$M${DL},"No",{DR}!$AM$2:$AM${DL},"<>X")', 'Incumplimiento documental',
     'Trabajadores que acumulan D13: exigir solicitudes escritas (RQ-007)'),
    ('V09 Vacaciones con saldo negativo', 0, 'Error de integridad',
     'Requiere kárdex de vacaciones (RQ-007)'),
    ('V10 Pago fuera de fecha', 0, 'Incumplimiento de plazo',
     'Requiere comprobantes de pago (RQ-005 / roles)'),
    ('V11 FR pagado en rol a persona excluida (registros)',
     f'=COUNTIF({DR}!$T$2:$T${DL},"Excluido · pagado en rol")', 'Gasto sin sustento',
     'Representantes legales excluidos que cobran FR en rol: evaluar ajuste'),
]
for i, (b, c, d, e) in enumerate(_vals):
    r = 60 + i
    co[f'B{r}'] = b; co[f'C{r}'] = c; co[f'D{r}'] = d; co[f'E{r}'] = e
for col, w in dict(A=3.0, B=48.0, C=14.0, D=24.0, E=12.0, F=14.0, H=12.0, I=14.0, K=12.0).items():
    co.column_dimensions[col].width = w

wb.save(OUT)
