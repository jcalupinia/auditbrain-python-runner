# -*- coding: utf-8 -*-
from backend.app.aud.niif.procesadores.nomina import rutas as _R
"""DO-3 Resumen de Planillas IESS.

Calca la cédula de referencia ``referencia/cedulas/DO-3_Resumen_Planillas_IESS.xlsx``
(4 hojas: «DO3 Resumen de Planillas», «Parámetros», «Detalle RQ-003», «Controles»).

Fuentes de datos (en runtime, nada del cliente va escrito en el código):
  - Consolidado IESS crudo (RQ-003) desde ``_R.CTX.consolidado``, hoja
    ``detallePlanillaConsolidado`` — TODAS las columnas del detalle y la fila
    «Totales :» (que el motor saltea) para los «Valor B» de la hoja Controles.
  - Anexo de nómina (RQ-002) desde ``_R.CTX.anexo`` para los dos cruces
    informativos con la sumaria DO-2 (aporte patronal del gasto; sueldos+HE+bono).

Los rangos de las fórmulas crecen con la población real del cliente (no fijos a
un tamaño de población). El recálculo de auditoría (columnas O..U) replica las fórmulas de la
referencia (ROUND/VLOOKUP/IF) contra la hoja «Parámetros»; la lista de
«EXCEPCIONES POR TRABAJADOR» se deriva del mismo recálculo hecho en Python.
"""
import datetime
import re
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from backend.app.aud.niif.procesadores.nomina import motor
from backend.app.aud.niif.procesadores.nomina.cedulas_nuevas import leer_anexo, _concepto_do2

OUT = (_R.CTX.out + '/DO-3_Resumen_Planillas_IESS.xlsx')
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

# ---- estilos
N2D = '#,##0.00;[RED]\\-#,##0.00;\\-'      # detalle / controles
N2 = '#,##0.00'                            # resumen
PC = '0.00%'
THIN = Side(style='thin', color='B0B0B0')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HFILL = PatternFill('solid', fgColor='0A2342')
TFILL = PatternFill('solid', fgColor='DCE6F1')
HF = Font(bold=True, color='FFFFFF', size=10)
BF = Font(bold=True, size=10)
BF11 = Font(bold=True, size=11)
TITLE = Font(bold=True, color='FFFFFF', size=13)
IT = Font(italic=True, size=9)
CEN = Alignment(horizontal='center', vertical='center', wrap_text=True)
CENL = Alignment(horizontal='center', vertical='center')
LEFTW = Alignment(horizontal='left', vertical='center', wrap_text=True)
TASAS = [('06', 'Código del Trabajo', 0.1115, 0.0945, 0.01,
          'Tasas generales del Seguro General Obligatorio'),
         ('16', 'Tiempo y/o jornada parcial', 0.1115, 0.0945, 0.01,
          'Mismas tasas, base proporcional'),
         ('74', 'Pasantes / internos / becarios', 0.0, 0.176, 0.0,
          'Esquema aplicado por la planilla; confirmar base legal')]
_TMAP = {c: (p, i, cc) for c, _n, p, i, cc, _f in TASAS}


# ------------------------------------------------------------------ lectura
def _leer_consolidado(path):
    """Devuelve (filas, totales). ``filas`` = registros trabajador-mes; ``totales``
    = valores de la fila «Totales :» del reporte (base, patronal, individual,
    valor CCC, total aporte)."""
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)['detallePlanillaConsolidado']
    filas, totales = [], {}
    for r in ws.iter_rows(min_row=3, values_only=True):
        c1 = r[1] if len(r) > 1 else None
        if c1 is None:
            continue
        if str(c1).strip().lower().startswith('total'):
            totales = dict(base=motor.num(r[5]), pat=motor.num(r[7]), ind=motor.num(r[8]),
                           ccc=motor.num(r[12]), total=motor.num(r[13]))
            continue
        periodo = str(c1).strip()
        try:
            mes = int(periodo.split('-')[-1])
        except (ValueError, IndexError):
            mes = motor.mnum(c1) or 0
        filas.append(dict(
            periodo=periodo, mes=mes, ced=str(r[2]).strip(), nombre=str(r[3]).strip(),
            rel=str(r[4] or '').strip(), base=motor.num(r[5]), dias=motor.num(r[6]),
            pat=motor.num(r[7]), ind=motor.num(r[8]), adic=motor.num(r[9]),
            cesantia=motor.num(r[10]), pct_ccc=motor.num(r[11]), ccc=motor.num(r[12]),
            total=motor.num(r[13])))
    return filas, totales


def _cruces_do2(anexo_path):
    """Valores «Según DO-2» (en azul) de los cruces informativos, desde el anexo
    RQ-002, agrupando el gasto por concepto de la sumaria DO-2."""
    if not anexo_path:
        return 0.0, 0.0
    try:
        _pas, gas = leer_anexo(anexo_path)
    except Exception:
        return 0.0, 0.0
    por = {}
    for _cod, desc, _s24, s25 in gas:
        por[_concepto_do2(desc)] = por.get(_concepto_do2(desc), 0.0) + s25
    patronal = round(por.get('Aporte Patronal', 0.0), 2)
    base_sue = round(por.get('Sueldos', 0.0) + por.get('Horas Extras', 0.0)
                     + por.get('Bono Desempeño', 0.0), 2)
    return patronal, base_sue


# ------------------------------------------------------------------ datos
filas, tot = _leer_consolidado(_R.CTX.consolidado)
# orden del reporte: por nombre y, dentro de cada trabajador, por mes ascendente
filas.sort(key=lambda d: (d['nombre'], d['mes']))
n = len(filas)
last = n + 1                       # última fila de datos del Detalle (fila 1 = encabezado)
anio = filas[0]['periodo'].split('-')[0] if filas else str(_R.CTX.ejercicio or '')

# recálculo en Python para la lista de excepciones por trabajador (mismo criterio
# que la fórmula de la columna U del Detalle)
tol = 0.01
_exc = {}
for d in filas:
    code = (d['rel'] or '')[:2]
    if code not in _TMAP:
        continue
    tp, ti, tc = _TMAP[code]
    dp = round(round(d['base'] * tp, 2) - d['pat'], 2)
    di = round(round(d['base'] * ti, 2) - d['ind'], 2)
    dc = round(round(d['base'] * tc, 2) - d['ccc'], 2)
    if max(abs(dp), abs(di), abs(dc)) > tol:
        _exc.setdefault(d['ced'], (d['nombre'], d['rel']))
exc = sorted(_exc.items(), key=lambda kv: kv[1][0])   # por nombre
n_ced = len({d['ced'] for d in filas})                # trabajadores únicos

do2_patronal, do2_base = _cruces_do2(_R.CTX.anexo)

# encabezado de la ficha (de _R.CTX; con placeholder si la ficha no lo trae)
_cliente = (_R.CTX.cliente or '').strip() or '[desde Ficha del encargo]'
_periodo_term = (_R.CTX.corte or '').strip() or '[desde Ficha del encargo]'
_prep = (_R.CTX.preparado or '').strip()
_prep = '[desde Ficha]' if _prep in ('', '[auditor]') else _prep
_rev = (_R.CTX.revisado or '').strip()
_rev = '[desde Ficha]' if _rev in ('', '[socio]') else _rev


# ------------------------------------------------------------------ libro
wb = openpyxl.Workbook()
wb.remove(wb.active)
R3 = "'Detalle RQ-003'"
DO3 = "'DO3 Resumen de Planillas'"

# ===================================================== 1) DO3 Resumen de Planillas
rs = wb.create_sheet('DO3 Resumen de Planillas')
rs.merge_cells('B1:G2')
rs['B1'] = 'OBLIGACIONES ACUMULADAS'; rs['B1'].font = TITLE
rs['B1'].fill = HFILL; rs['B1'].alignment = CEN
rs.merge_cells('B3:G3')
rs['B3'] = 'Resumen Planilla IESS'; rs['B3'].font = BF11; rs['B3'].alignment = CENL
rs['B4'] = 'Nombre del cliente:'; rs['C4'] = _cliente
rs['F4'] = 'Período terminado:'; rs['G4'] = _periodo_term
rs['B5'] = 'Preparado por:'; rs['C5'] = _prep
rs['D5'] = 'Revisado:'; rs['E5'] = _rev
rs['F5'] = 'Fecha:'; rs['G5'] = '[desde Ficha]'
rs['H5'] = 'Referencia de PT'; rs['J5'] = 'DO-3'
for c in ('B4', 'F4', 'B5', 'D5', 'F5', 'H5', 'J5'):
    rs[c].font = BF
# bloque de título: identidad del encargo (de la ficha, NUNCA un nombre fijo).
_MESES_ES = ('', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
             'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
_corte_dt = None
_m = re.match(r'(\d{4})-(\d{2})-(\d{2})', _R.CTX.corte or '')
if _m:
    _corte_dt = datetime.datetime(int(_m.group(1)), int(_m.group(2)), int(_m.group(3)))
_al_corte = (f'Al {_corte_dt.day} de {_MESES_ES[_corte_dt.month]} del {_corte_dt.year}'
             if _corte_dt else '[desde Ficha del encargo]')
rs['C11'] = 'EO'
rs['B12'] = _cliente; rs['C12'] = _corte_dt
rs['B13'] = 'Análisis de nómina'
rs['B14'] = _al_corte
# cabecera de la tabla mensual (dos filas)
rs.merge_cells('B19:B21')
rs['B19'] = 'MES'; rs['B19'].font = BF; rs['B19'].alignment = CEN
rs['C19'] = 'Planillas'; rs['C19'].font = BF; rs['E19'] = ' '
for c, t in zip('CDEFGHIJ', ['No.', 'Base ', 'Apor Personal', 'Aporte ', 'Valor ',
                             'Fondos de ', 'Dias ', 'Total Aporte']):
    rs[f'{c}20'] = t; rs[f'{c}20'].font = BF; rs[f'{c}20'].alignment = CEN
for c, t in zip('CDEFGHI', ['Empleados', 'Imponible', 0.0945, 'patronal', 'ccc',
                            'Reserva', 'Laborados']):
    rs[f'{c}21'] = t
    if isinstance(t, str):
        rs[f'{c}21'].font = BF
    rs[f'{c}21'].alignment = CEN
# filas mensuales (fórmulas que crecen con la población)
for m in range(1, 13):
    r = 21 + m
    rs[f'B{r}'] = MESES[m - 1]
    rs[f'C{r}'] = f'=COUNTIFS({R3}!$B$2:$B${last},{m})'
    rs[f'D{r}'] = f'=SUMIFS({R3}!$F$2:$F${last},{R3}!$B$2:$B${last},{m})'
    rs[f'E{r}'] = f'=SUMIFS({R3}!$I$2:$I${last},{R3}!$B$2:$B${last},{m})'
    rs[f'F{r}'] = f'=SUMIFS({R3}!$H$2:$H${last},{R3}!$B$2:$B${last},{m})'
    rs[f'G{r}'] = f'=SUMIFS({R3}!$M$2:$M${last},{R3}!$B$2:$B${last},{m})'
    rs[f'H{r}'] = 0
    rs[f'I{r}'] = f'=SUMIFS({R3}!$G$2:$G${last},{R3}!$B$2:$B${last},{m})'
    rs[f'J{r}'] = f'=SUM(E{r}:G{r})'
    for c in 'DEFGHIJ':
        rs[f'{c}{r}'].number_format = N2
# fila de totales
rs['B34'] = 'Σ  '
for c in 'CDEFGHIJ':
    rs[f'{c}34'] = f'=SUM({c}22:{c}33)'; rs[f'{c}34'].font = BF
    rs[f'{c}34'].number_format = N2
rs['C35'] = '∏'; rs['D35'] = '∏'
for c in 'EFGH':
    rs[f'{c}35'] = 'a)'
rs['J35'] = '∏'
rs['B36'] = ('Fondos de Reserva: no forman parte del Consolidado IESS; se verifican '
             'contra los comprobantes de pago (RQ-005) en DO-9.')
rs['C37'] = '=+C33*4%'
rs['D37'] = ('Mínimo de empleados con discapacidad (4% del personal a diciembre); '
             'verificar contra el Bloque F del checklist DO-1.')
rs['B41'] = 'Objetivo:'; rs['B41'].font = BF
rs['B42'] = ('Verificar la razonabilidad de las cuentas que conforman la base para '
             'aportación de planillas de IESS')
rs['B44'] = 'Procedimiento:'; rs['B44'].font = BF
rs['B45'] = 'º'
rs['B46'] = ('Se solicitó al departamento de Contabilidad las planillas de pago al '
             'IESS de Enero a Diciembre 2025')
rs['B47'] = ('Se recalcularon sobre el 100% de los registros (trabajador-mes) los '
             'aportes personal, patronal y CCC según la relación de trabajo, y se '
             'compararon contra lo aportado según planillas (ver hojas Detalle RQ-003 '
             'y Controles).')
rs['B48'] = ('=IF(Controles!C26=0,"Conclusión (borrador): no se determinaron '
             'diferencias en el recálculo de aportes.","Conclusión (borrador): se '
             'determinaron "&Controles!C26&" registros con diferencias; ver Controles. '
             'Sujeto a revisión del auditor.")')
rs['B50'] = 'Marcas:'; rs['B50'].font = BF
for r, (mk, txt) in zip(range(51, 56), [
        ('√', 'Verificado, comprobado, cotejado (con libros).'),
        ('∏', 'Verificado, comprobado, cotejado (con planillas)'),
        ('a)', 'Recálculo de auditoría'),
        ('Σ  ', 'Sumado, totalizado'),
        ('‡ ', 'Diferencia determinada.')]):
    rs[f'A{r}'] = mk; rs[f'B{r}'] = txt
rs['A63'] = ('Año auditado 2026. Cédula construida con datos de la plantilla 2025; se '
             'reemplazan con la información 2026 del cliente.')
for col, w in dict(A=4.4, B=22.1, C=15.7, D=15.1, E=15.3, F=16.1, G=14.9, H=14.3,
                   I=9.1, J=11.4).items():
    rs.column_dimensions[col].width = w

# ===================================================== 2) Parámetros
pa = wb.create_sheet('Parámetros')
pa['B2'] = f'PARÁMETROS DE RECÁLCULO — APORTES IESS {anio}'; pa['B2'].font = BF11
for c, t in zip('BCDEFG', ['Código', 'Relación de trabajo', 'Patronal', 'Individual',
                           'CCC', 'Fuente / observación']):
    pa[f'{c}4'] = t; pa[f'{c}4'].font = HF; pa[f'{c}4'].fill = HFILL
for i, (cod, rel, p, ind, cc, fuente) in enumerate(TASAS):
    r = 5 + i
    pa[f'B{r}'] = cod; pa[f'C{r}'] = rel
    pa[f'D{r}'] = p; pa[f'E{r}'] = ind; pa[f'F{r}'] = cc
    pa[f'G{r}'] = fuente
    for c in 'DEF':
        pa[f'{c}{r}'].number_format = PC
pa['B9'] = f'SBU {anio} (USD)'; pa['C9'] = motor.SBU_2025
pa['B10'] = 'Tolerancia de diferencia (USD)'; pa['C10'] = tol
pa['B12'] = ('Valores en azul: parámetros editables. Todo recálculo de las hojas toma '
             'estas tasas.'); pa['B12'].font = IT
for col, w in dict(A=3.0, B=10.0, C=30.0, D=11.0, F=9.0, G=52.0).items():
    pa.column_dimensions[col].width = w

# ===================================================== 3) Detalle RQ-003
de = wb.create_sheet('Detalle RQ-003')
hdr = ['Período', 'Mes', 'Cédula', 'Nombre', 'Relación de trabajo', 'Base imponible',
       'Días', 'Patronal', 'Individual', 'Aporte adic.', 'Cesantía', '% CCC',
       'Valor CCC', 'Total aporte IESS', 'Recálc. patronal', 'Recálc. individual',
       'Recálc. CCC', 'Dif. patronal', 'Dif. individual', 'Dif. CCC', 'Estado']
for j, h in enumerate(hdr, 1):
    de.cell(1, j, h).font = BF
_numcols = set('FHIJKMN')
for idx, d in enumerate(filas, 2):
    de.cell(idx, 1, d['periodo']); de.cell(idx, 2, d['mes']); de.cell(idx, 3, d['ced'])
    de.cell(idx, 4, d['nombre']); de.cell(idx, 5, d['rel'])
    de.cell(idx, 6, d['base']); de.cell(idx, 7, d['dias']); de.cell(idx, 8, d['pat'])
    de.cell(idx, 9, d['ind']); de.cell(idx, 10, d['adic']); de.cell(idx, 11, d['cesantia'])
    de.cell(idx, 12, d['pct_ccc']); de.cell(idx, 13, d['ccc']); de.cell(idx, 14, d['total'])
    de.cell(idx, 15, f'=ROUND(F{idx}*VLOOKUP(LEFT(E{idx},2),Parámetros!$B$5:$F$7,3,0),2)')
    de.cell(idx, 16, f'=ROUND(F{idx}*VLOOKUP(LEFT(E{idx},2),Parámetros!$B$5:$F$7,4,0),2)')
    de.cell(idx, 17, f'=ROUND(F{idx}*VLOOKUP(LEFT(E{idx},2),Parámetros!$B$5:$F$7,5,0),2)')
    de.cell(idx, 18, f'=ROUND(O{idx}-H{idx},2)')
    de.cell(idx, 19, f'=ROUND(P{idx}-I{idx},2)')
    de.cell(idx, 20, f'=ROUND(Q{idx}-M{idx},2)')
    de.cell(idx, 21, f'=IF(MAX(ABS(R{idx}),ABS(S{idx}),ABS(T{idx}))>Parámetros!$C$10,"‡ REVISAR","OK")')
    for c in 'FHIJKMNOPQRST':
        de[f'{c}{idx}'].number_format = N2D
# fila de totales (SUBTOTAL para respetar filtros del auditor)
tr = last + 1
de.cell(tr, 4, 'Σ TOTALES').font = BF
for c in 'FHIJKMNOPQRST':
    de[f'{c}{tr}'] = f'=SUBTOTAL(9,{c}2:{c}{last})'
    de[f'{c}{tr}'].font = BF; de[f'{c}{tr}'].number_format = N2D
de.freeze_panes = 'E2'
for col, w in dict(A=9.0, B=5.0, C=12.0, D=38.0, E=34.0, F=13.0, G=6.0, H=11.0,
                   J=9.0, L=7.0, M=10.0, N=12.0, Q=11.0, T=10.0, U=12.0).items():
    de.column_dimensions[col].width = w

# ===================================================== 4) Controles
co = wb.create_sheet('Controles')
co['B2'] = 'CONTROLES DE INTEGRIDAD Y RECÁLCULO — DO-3'; co['B2'].font = BF11
for c, t in zip('BCDEF', ['Control', 'Valor A', 'Valor B', 'Diferencia', 'Estado']):
    co[f'{c}4'] = t; co[f'{c}4'].font = HF; co[f'{c}4'].fill = HFILL


def _ctrl(r, desc, a, b):
    co[f'B{r}'] = desc; co[f'C{r}'] = a; co[f'D{r}'] = b
    co[f'E{r}'] = f'=ROUND(C{r}-D{r},2)'
    co[f'F{r}'] = f'=IF(ABS(E{r})<=Parámetros!$C$10,"OK","REVISAR")'
    co[f'F{r}'].alignment = CENL
    for c in 'CDE':
        co[f'{c}{r}'].number_format = N2D


# Valor B = fila «Totales :» del Consolidado (dato del cliente), salvo el conteo
_ctrl(5, 'Registros trasladados vs reporte IESS', f"=COUNTA({R3}!$C$2:$C${last})", n)
_ctrl(6, 'Base imponible: detalle vs fila Totales del reporte', f"=SUM({R3}!$F$2:$F${last})", round(tot.get('base', 0.0), 2))
_ctrl(7, 'Patronal: detalle vs fila Totales del reporte', f"=SUM({R3}!$H$2:$H${last})", round(tot.get('pat', 0.0), 2))
_ctrl(8, 'Individual: detalle vs fila Totales del reporte', f"=SUM({R3}!$I$2:$I${last})", round(tot.get('ind', 0.0), 2))
_ctrl(9, 'Valor CCC: detalle vs fila Totales del reporte', f"=SUM({R3}!$M$2:$M${last})", round(tot.get('ccc', 0.0), 2))
_ctrl(10, 'Total aporte IESS: detalle vs fila Totales del reporte', f"=SUM({R3}!$N$2:$N${last})", round(tot.get('total', 0.0), 2))
_ctrl(11, 'Total aporte IESS = Patronal + Individual', f"=SUM({R3}!$N$2:$N${last})",
      f"=SUM({R3}!$H$2:$H${last})+SUM({R3}!$I$2:$I${last})")
_ctrl(12, 'DO-3 Base imponible = detalle', f"={DO3}!D34", f"=SUM({R3}!$F$2:$F${last})")
_ctrl(13, 'DO-3 Aporte personal = detalle', f"={DO3}!E34", f"=SUM({R3}!$I$2:$I${last})")
_ctrl(14, 'DO-3 Aporte patronal = detalle', f"={DO3}!F34", f"=SUM({R3}!$H$2:$H${last})")
_ctrl(15, 'DO-3 Valor CCC = detalle', f"={DO3}!G34", f"=SUM({R3}!$M$2:$M${last})")
_ctrl(16, 'DO-3 Total aporte (E+F+G) cuadra', f"={DO3}!J34",
      f"={DO3}!E34+{DO3}!F34+{DO3}!G34")
_ctrl(17, 'Registros-empleado DO-3 = registros detalle', f"={DO3}!C34",
      f"=COUNTA({R3}!$C$2:$C${last})")

# Bloque recálculo de auditoría
co['B20'] = 'RESULTADO DEL RECÁLCULO DE AUDITORÍA (a)'; co['B20'].font = BF
for c, t in zip('BCDE', ['Concepto', 'Según planilla', 'Recálculo', 'Diferencia ‡']):
    co[f'{c}21'] = t; co[f'{c}21'].font = BF
for r, (desc, va, vb) in zip(range(22, 25), [
        ('Aporte patronal', f"=SUM({R3}!$H$2:$H${last})", f"=SUM({R3}!$O$2:$O${last})"),
        ('Aporte individual', f"=SUM({R3}!$I$2:$I${last})", f"=SUM({R3}!$P$2:$P${last})"),
        ('Valor CCC', f"=SUM({R3}!$M$2:$M${last})", f"=SUM({R3}!$Q$2:$Q${last})")]):
    co[f'B{r}'] = desc; co[f'C{r}'] = va; co[f'D{r}'] = vb
    co[f'E{r}'] = f'=ROUND(D{r}-C{r},2)'
    for c in 'CDE':
        co[f'{c}{r}'].number_format = N2D
co['B25'] = 'Registros revisados'; co['C25'] = f"=COUNTA({R3}!$C$2:$C${last})"
co['B26'] = 'Registros con diferencia (‡ REVISAR)'
co['C26'] = f'=COUNTIF({R3}!$U$2:$U${last},"‡ REVISAR")'
co['B27'] = 'Trabajadores únicos'; co['C27'] = n_ced

# Excepciones por trabajador (lista derivada del recálculo)
co['B30'] = 'EXCEPCIONES POR TRABAJADOR'; co['B30'].font = BF
for c, t in zip('BCDEFGHI', ['Nombre', 'Cédula', 'Relación', 'Registros ‡', 'Base',
                             'Dif. patronal', 'Dif. individual', 'Dif. CCC']):
    co[f'{c}31'] = t; co[f'{c}31'].font = BF
er = 32
for ced, (nom, rel) in exc:
    co[f'B{er}'] = nom; co[f'C{er}'] = ced; co[f'D{er}'] = rel
    co[f'E{er}'] = (f"=COUNTIFS({R3}!$C$2:$C${last},C{er},{R3}!$U$2:$U${last},\"‡ REVISAR\")")
    for c, col in zip('FGHI', ['F', 'R', 'S', 'T']):
        co[f'{c}{er}'] = (f"=SUMIFS({R3}!${col}$2:${col}${last},{R3}!$C$2:$C${last},C{er},"
                          f"{R3}!$U$2:$U${last},\"‡ REVISAR\")")
        co[f'{c}{er}'].number_format = N2D
    er += 1
co[f'B{er}'] = 'Σ'; co[f'B{er}'].font = BF
for c in 'EFGHI':
    co[f'{c}{er}'] = f'=SUM({c}32:{c}{er-1})'; co[f'{c}{er}'].font = BF
    if c != 'E':
        co[f'{c}{er}'].number_format = N2D

# Cruces informativos con la sumaria DO-2 (Valor B «Según DO-2» = dato del anexo)
xr = er + 3
co[f'B{xr}'] = 'CRUCES INFORMATIVOS CON LA SUMARIA DO-2 (valores de DO-2 en azul)'
co[f'B{xr}'].font = BF
for c, t in zip('BCDEF', ['Concepto', 'Según IESS', 'Según DO-2', 'Diferencia',
                          'Se resuelve en']):
    co[f'{c}{xr+1}'] = t; co[f'{c}{xr+1}'].font = BF
co[f'B{xr+2}'] = 'Patronal + CCC vs gasto Aporte Patronal'
co[f'C{xr+2}'] = f"={DO3}!F34+{DO3}!G34"; co[f'D{xr+2}'] = do2_patronal
co[f'E{xr+2}'] = f'=ROUND(C{xr+2}-D{xr+2},2)'; co[f'F{xr+2}'] = 'DO-6 / DO-7'
co[f'B{xr+3}'] = 'Base imponible vs Sueldos + Horas Extras + Bono Desempeño'
co[f'C{xr+3}'] = f"={DO3}!D34"; co[f'D{xr+3}'] = do2_base
co[f'E{xr+3}'] = f'=ROUND(C{xr+3}-D{xr+3},2)'; co[f'F{xr+3}'] = 'DO-8'
for r in (xr + 2, xr + 3):
    for c in 'CDE':
        co[f'{c}{r}'].number_format = N2D
for col, w in dict(A=3.0, B=52.0, C=15.0, E=14.0, F=13.0, I=11.0).items():
    co.column_dimensions[col].width = w

wb.save(OUT)
