# -*- coding: utf-8 -*-
from backend.app.aud.niif.procesadores.nomina import rutas as _R
"""DO-2 Cédula Sumaria de Nómina.

Calca la cédula de referencia ``referencia/cedulas/DO-2_Cedula_Sumaria_Nomina.xlsx``
(2 hojas, en este orden: «DO2 Cedula Sumaria» y «Controles»).

Es la SUMARIA de las cuentas de nómina del cliente: cruza los saldos contables del
cierre anterior y del corte (anexo RQ-002) por cuenta, con la variación, los ajustes
del auditor y el saldo auditado. Fuentes de datos (en runtime; NADA del cliente va
escrito en el código):

  - Anexo de nómina (RQ-002) desde ``_R.CTX.anexo``: se reproduce su layout físico
    (pasivo acumulado 5BS.212.. y gasto de nómina, con las filas en blanco que separan
    los grupos). De ahí salen el código, la descripción y los dos saldos (anterior y
    al corte) de cada cuenta; la variación, el porcentaje y el saldo auditado son
    fórmulas. Las dos fechas de comparación salen de la fila de encabezados del propio
    anexo (no se teclean).
  - Mayor de gastos (RQ-004) desde ``mayores.py`` (ya cargado por el orquestador): el
    bloque «cuentas de gasto del mayor que no figuran en el anexo» agrupa esas cuentas
    por concepto con la clasificación por concepto del mayor (``mayores.G['concepto']``),
    NO con el papel del equipo (condición §4.2). El control «suma del mayor» es el total
    del mayor en runtime.

La agrupación del gasto por concepto (columna P, oculta, que alimenta el RESUMEN POR
CONCEPTO) sale de la clasificación por concepto del anexo/mayor
(``cedulas_nuevas._concepto_do2``), no de una lista tecleada a mano.

La identidad del encargo (cliente, período, preparado/revisado/fecha) sale de la ficha
vía ``_R.CTX`` con placeholder ``[desde Ficha del encargo]`` / ``[desde Ficha]`` si la
ficha viene vacía; NUNCA se copia el bloque de título heredado de la plantilla. Los
rangos de las fórmulas y los bloques crecen con la población real del anexo y del
mayor (no son fijos)."""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from backend.app.aud.niif.procesadores.nomina import mayores
from backend.app.aud.niif.procesadores.nomina.cedulas_nuevas import _concepto_do2, CONCEPTOS_DO2

OUT = (_R.CTX.out + '/DO-2_Cedula_Sumaria_Nomina.xlsx')

N2 = '#,##0.00'
PCT = '0.00%'
DATEF = 'd\\-mmm\\-yy'
ARIAL = Font(name='Arial', size=10)
BF = Font(name='Arial', size=10, bold=True)
HWHITE = Font(name='Arial', size=10, bold=True, color='FFFFFF')
H11WHITE = Font(name='Arial', size=11, bold=True, color='FFFFFF')
B11 = Font(name='Arial', size=11, bold=True)
WING = Font(name='Wingdings', size=10, bold=True, color='FFFF0000')
REDBF = Font(name='Arial', size=10, bold=True, color='FFFF0000')
NOTE = Font(name='Arial', size=8, italic=True)
NOTERED = Font(name='Arial', size=8, italic=True, color='FFC00000')
SMALL = Font(name='Arial', size=9)
FILL_HDR = PatternFill('solid', fgColor='0B1F3A')
FILL_HDR2 = PatternFill('solid', fgColor='0F2341')
FILL_TOT = PatternFill('solid', fgColor='D9E1F2')
CEN = Alignment(horizontal='center', vertical='center', wrap_text=True)
CENL = Alignment(horizontal='center')


def _es(n):
    """Formato numérico con coma decimal (configuración regional del equipo)."""
    s = f'{n:,.2f}'
    return s.replace(',', '\x00').replace('.', ',').replace('\x00', '.')


# ------------------------------------------------------------------ lectura del anexo
def _leer_anexo_layout(path):
    """Layout físico del anexo RQ-002: fechas de comparación y los ítems del pasivo y
    del gasto preservando las filas en blanco que separan los grupos. Cada ítem es
    ``('acct', cod, desc, s24, s25)`` o ``('blank',)``. Las filas de rótulo
    («Pasivo acumulado», «Gasto de nómina») se descartan."""
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    d24 = d25 = None
    if len(rows) > 1:
        d24, d25 = rows[1][2], rows[1][5]   # fila de fechas: col C (anterior), F (corte)
    pas, gas = [], []
    seen_gasto = False
    for r in rows[2:]:
        cod = r[0] if r else None
        if isinstance(cod, str) and cod.strip()[:1] == '5':
            cod = cod.strip()
            desc = str(r[1] or '')
            s24 = r[2] if isinstance(r[2], (int, float)) else 0
            s25 = r[5] if isinstance(r[5], (int, float)) else 0
            if cod.startswith('5BS.212'):
                pas.append(('acct', cod, desc, s24, s25))
            else:
                seen_gasto = True
                gas.append(('acct', cod, desc, s24, s25))
        elif all(v in (None, '') for v in (r or [])):
            (gas if seen_gasto else pas).append(('blank',))
        # cualquier otra fila (rótulo de sección) se descarta
    return d24, d25, pas, gas


d24, d25, pas_items, gas_items = _leer_anexo_layout(_R.CTX.anexo)
n_pas = sum(1 for it in pas_items if it[0] == 'acct')
n_gas = sum(1 for it in gas_items if it[0] == 'acct')
n_total = n_pas + n_gas

# cuentas del anexo (pasivo + gasto) para el bloque «solo en el mayor»
anexo_all = {it[1] for it in (pas_items + gas_items) if it[0] == 'acct'}
anexo_gas = {it[1] for it in gas_items if it[0] == 'acct'}

# totales de control (derivados del anexo; «Esperado»)
p24 = round(sum(it[3] for it in pas_items if it[0] == 'acct'), 2)
p25 = round(sum(it[4] for it in pas_items if it[0] == 'acct'), 2)
g24 = round(sum(it[3] for it in gas_items if it[0] == 'acct'), 2)
g25 = round(sum(it[4] for it in gas_items if it[0] == 'acct'), 2)

# bloque «cuentas del mayor RQ-004 que no figuran en el anexo» (agrupado por concepto
# del mayor; NO del papel del equipo — condición §4.2)
mayor_only = []        # [(concepto, nº ctas, saldo al corte)]
mayor_total = 0.0
mayor_ctas = set()
try:
    G = mayores.G
    mayor_ctas = set(G.cta.unique())
    mayor_total = round(float(G.Importe.sum()), 2)
    solo = G[~G.cta.isin(anexo_all)]
    grp = solo.groupby('concepto').agg(nct=('cta', 'nunique'), imp=('Importe', 'sum'))
    for con in sorted(grp.index):
        mayor_only.append((con, int(grp.loc[con, 'nct']), round(float(grp.loc[con, 'imp']), 2)))
except Exception:
    pass
n_mayor_only = len(mayor_ctas - anexo_all)
n_comunes = len(anexo_gas & mayor_ctas)

# identidad del encargo (de _R.CTX; placeholder si la ficha viene vacía)
_cliente = (_R.CTX.cliente or '').strip() or '[desde Ficha del encargo]'
_periodo = (_R.CTX.corte or '').strip() or '[desde Ficha del encargo]'
_prep = (_R.CTX.preparado or '').strip()
_prep = '[desde Ficha]' if _prep in ('', '[auditor]') else _prep
_rev = (_R.CTX.revisado or '').strip()
_rev = '[desde Ficha]' if _rev in ('', '[socio]') else _rev

S = "'DO2 Cedula Sumaria'"


# ------------------------------------------------------------------ libro
wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'DO2 Cedula Sumaria'


def _mark(coord):
    ws[coord] = 'ü'
    ws[coord].font = WING
    ws[coord].alignment = CENL


def fila(r, cod, desc, s24, s25, concepto=None, ref=None):
    ws[f'B{r}'] = cod; ws[f'B{r}'].font = ARIAL
    ws[f'C{r}'] = desc; ws[f'C{r}'].font = ARIAL
    ws[f'D{r}'] = s24; ws[f'D{r}'].number_format = N2; ws[f'D{r}'].font = ARIAL
    ws[f'E{r}'] = f'=+G{r}-D{r}'; ws[f'E{r}'].number_format = N2; ws[f'E{r}'].font = ARIAL
    ws[f'F{r}'] = f'=IF(D{r}=0,0,E{r}/ABS(D{r}))'; ws[f'F{r}'].number_format = PCT; ws[f'F{r}'].font = ARIAL
    ws[f'G{r}'] = s25; ws[f'G{r}'].number_format = N2; ws[f'G{r}'].font = ARIAL
    _mark(f'H{r}')
    ws[f'I{r}'] = 0; ws[f'I{r}'].number_format = N2; ws[f'I{r}'].font = ARIAL
    ws[f'J{r}'] = 0; ws[f'J{r}'].number_format = N2; ws[f'J{r}'].font = ARIAL
    _mark(f'K{r}')
    ws[f'L{r}'] = f'=G{r}+I{r}-J{r}'; ws[f'L{r}'].number_format = N2; ws[f'L{r}'].font = ARIAL
    _mark(f'M{r}')
    if ref is not None:
        ws[f'N{r}'] = ref; ws[f'N{r}'].font = REDBF; ws[f'N{r}'].alignment = CENL
    if concepto is not None:
        ws[f'P{r}'] = concepto


def _emit(items, start, gasto):
    """Escribe los ítems (cuentas + blancos) desde ``start``, con exactamente una fila
    en blanco antes del Total. Devuelve ``(total_row, otros_rows)``."""
    items = list(items)
    while items and items[0][0] == 'blank':
        items = items[1:]
    while items and items[-1][0] == 'blank':
        items = items[:-1]
    items = items + [('blank',)]
    otros_rows = []
    r = start
    first_ref = True
    for it in items:
        if it[0] == 'acct':
            _, cod, desc, s24, s25 = it
            con = _concepto_do2(desc) if gasto else None
            # la primera cuenta del pasivo lleva la referencia cruzada a DO-8
            ref = 'D8' if (not gasto and first_ref) else None
            fila(r, cod, desc, s24, s25, concepto=con, ref=ref)
            first_ref = False
            if gasto and con == 'Otros gastos de nómina':
                otros_rows.append(r)
        r += 1
    total_row = r
    return total_row, otros_rows


# --- banda de título e identidad
ws.merge_cells('B1:J2'); ws.merge_cells('B3:J3'); ws.merge_cells('H4:J4')
ws['B1'] = 'OBLIGACIONES ACUMULADAS'; ws['B1'].font = BF; ws['B1'].alignment = CEN
ws['B3'] = 'Sumaria'; ws['B3'].font = BF; ws['B3'].alignment = CENL
ws['B4'] = 'Nombre del cliente:'; ws['C4'] = _cliente
ws['F4'] = 'Período terminado:'; ws['H4'] = _periodo
ws['B5'] = 'Preparado por:'; ws['C5'] = _prep
ws['D5'] = 'Revisado:'; ws['E5'] = _rev
ws['F5'] = 'Fecha:'; ws['G5'] = '[desde Ficha]'
ws['I5'] = 'Referencia de PT'; ws['J5'] = 'DO-2'
for c in ('B4', 'F4', 'B5', 'D5', 'F5', 'I5'):
    ws[c].font = BF
ws['J5'].font = REDBF
for c in ('C4', 'H4', 'C5', 'E5', 'G5'):
    ws[c].font = ARIAL

# --- encabezados de la tabla (filas 9-10)
for mc in ('B9:B10', 'C9:C10', 'E9:E10', 'F9:F10', 'H9:H10', 'I9:J9', 'K9:K10', 'M9:M10', 'N9:N10'):
    ws.merge_cells(mc)
for c, t in [('B9', 'Código'), ('C9', 'Descripción'), ('D9', 'Saldo'), ('E9', 'Variación'),
             ('F9', 'Porcentaje'), ('G9', 'Saldo'), ('I9', 'Ajustes y/o reclasificaciones'),
             ('L9', 'Saldo '), ('N9', 'Referencia')]:
    ws[c] = t; ws[c].font = BF; ws[c].alignment = CEN
if d24 is not None:
    ws['D10'] = d24; ws['D10'].number_format = DATEF
if d25 is not None:
    ws['G10'] = d25; ws['G10'].number_format = DATEF
for c, t in [('D10', d24), ('G10', d25), ('I10', 'Debe'), ('J10', 'Haber'), ('L10', 'Auditado')]:
    ws[c].font = BF; ws[c].alignment = CENL
ws['I10'] = 'Debe'; ws['J10'] = 'Haber'; ws['L10'] = 'Auditado'

# --- pasivo (fila 11..), Total
pt, _ = _emit(pas_items, 11, gasto=False)
ws.merge_cells(f'B{pt}:C{pt}')
ws[f'B{pt}'] = 'Total'; ws[f'B{pt}'].font = BF; ws[f'B{pt}'].alignment = CENL
for col in 'DEGIJL':
    ws[f'{col}{pt}'] = f'=SUM({col}11:{col}{pt - 1})'
    ws[f'{col}{pt}'].font = BF; ws[f'{col}{pt}'].number_format = N2
for col in 'FHK':
    ws[f'{col}{pt}'] = 'Σ  '; ws[f'{col}{pt}'].font = REDBF; ws[f'{col}{pt}'].alignment = CENL

# --- gasto (dos filas después del Total del pasivo), Total
g0 = pt + 2
gt, otros_rows = _emit(gas_items, g0, gasto=True)
ws.merge_cells(f'B{gt}:C{gt}')
ws[f'B{gt}'] = 'Total'; ws[f'B{gt}'].font = BF; ws[f'B{gt}'].alignment = CENL
for col in 'DEGIJL':
    ws[f'{col}{gt}'] = f'=SUM({col}{g0}:{col}{gt - 1})'
    ws[f'{col}{gt}'].font = BF; ws[f'{col}{gt}'].number_format = N2
for col in 'FHK':
    ws[f'{col}{gt}'] = 'Σ  '; ws[f'{col}{gt}'].font = REDBF; ws[f'{col}{gt}'].alignment = CENL

# rango con nombre: columna de conceptos del gasto (alimenta el RESUMEN)
from openpyxl.workbook.defined_name import DefinedName
wb.defined_names.add(DefinedName('resumen_concepto', attr_text=f"{S}!$P${g0}:$P${gt - 1}"))

# --- RESUMEN DEL GASTO POR CONCEPTO
rb = gt + 2
ws[f'B{rb}'] = 'RESUMEN DEL GASTO POR CONCEPTO (para cruce con pruebas siguientes)'
ws[f'B{rb}'].font = BF
ws[f'B{rb + 1}'] = 'Marcas:'; ws[f'B{rb + 1}'].font = REDBF
hr = rb + 2
for c, t in [('B', 'Concepto'), ('C', 'Nº ctas'), ('D', 'Saldo 31-dic-24'),
             ('G', 'Saldo 31-dic-25'), ('L', 'Saldo auditado')]:
    ws[f'{c}{hr}'] = t; ws[f'{c}{hr}'].font = H11WHITE if c == 'B' else HWHITE
    ws[f'{c}{hr}'].fill = FILL_HDR; ws[f'{c}{hr}'].alignment = CENL
r0 = hr + 1
r = r0
for con in CONCEPTOS_DO2:
    ws[f'B{r}'] = con; ws[f'B{r}'].font = ARIAL; ws[f'B{r}'].alignment = CENL
    ws[f'C{r}'] = f'=COUNTIF(resumen_concepto,B{r})'; ws[f'C{r}'].font = ARIAL
    ws[f'D{r}'] = f'=SUMIF(resumen_concepto,B{r},$D${g0}:$D${gt - 1})'
    ws[f'G{r}'] = f'=SUMIF(resumen_concepto,B{r},$G${g0}:$G${gt - 1})'
    ws[f'L{r}'] = f'=SUMIF(resumen_concepto,B{r},$L${g0}:$L${gt - 1})'
    for c in 'DGL':
        ws[f'{c}{r}'].number_format = N2; ws[f'{c}{r}'].font = ARIAL
    r += 1
rt = r
ws[f'B{rt}'] = 'Total gasto'; ws[f'B{rt}'].font = B11; ws[f'B{rt}'].fill = FILL_TOT
for c in 'CDGL':
    ws[f'{c}{rt}'] = f'=SUM({c}{r0}:{c}{rt - 1})'; ws[f'{c}{rt}'].font = B11
    ws[f'{c}{rt}'].fill = FILL_TOT
    if c != 'C':
        ws[f'{c}{rt}'].number_format = N2

# --- conclusión y nota
rc = rt + 2
ws[f'B{rc}'] = ('Conclusión: [borrador - se emite cuando no queden diferencias ni '
                'variaciones sin explicar; firma del auditor].')
ws[f'B{rc}'].font = SMALL
rn = rt + 4
ws[f'A{rn}'] = ('Año auditado 2026. Cédula construida con datos de la plantilla 2025; se '
                'reemplazan con la información 2026 del cliente.')
ws[f'A{rn}'].font = NOTERED

# --- bloque: cuentas del mayor RQ-004 que no figuran en el anexo
mb = rt + 6
ws[f'B{mb}'] = 'CUENTAS DE GASTO DEL MAYOR RQ-004 QUE NO FIGURAN EN EL ANEXO RQ-002'
ws[f'B{mb}'].font = BF
mh = mb + 1
for c, t in [('B', 'Concepto'), ('C', 'Nº ctas'), ('G', 'Saldo 31-dic-25 (mayor)')]:
    ws[f'{c}{mh}'] = t; ws[f'{c}{mh}'].font = HWHITE; ws[f'{c}{mh}'].fill = FILL_HDR2
m0 = mh + 1
r = m0
for con, nct, imp in mayor_only:
    ws[f'B{r}'] = con; ws[f'B{r}'].font = ARIAL
    ws[f'C{r}'] = nct; ws[f'C{r}'].font = ARIAL
    ws[f'G{r}'] = imp; ws[f'G{r}'].number_format = N2
    ws[f'G{r}'].font = Font(name='Arial', size=10, color='FF0000FF')
    r += 1
mt = r
ws[f'B{mt}'] = 'Total no incluido en el anexo'; ws[f'B{mt}'].font = BF
ws[f'G{mt}'] = f'=SUM(G{m0}:G{mt - 1})'; ws[f'G{mt}'].font = BF; ws[f'G{mt}'].number_format = N2
# médicas a tiempo parcial (en el anexo, no en el mayor) = conceptos «Otros» del gasto
rmed = mt + 1
ws[f'B{rmed}'] = '(−) Aporte A.Médicas tiempo parcial: en el anexo, no en el mayor de gastos'
ws[f'B{rmed}'].font = ARIAL
_med = '=-(' + '+'.join(f'G{x}' for x in otros_rows) + ')' if otros_rows else 0
ws[f'G{rmed}'] = _med; ws[f'G{rmed}'].number_format = N2; ws[f'G{rmed}'].font = ARIAL
ran = mt + 2
ws[f'B{ran}'] = f'Gasto de nómina según anexo RQ-002 (G{gt})'; ws[f'B{ran}'].font = ARIAL
ws[f'G{ran}'] = f'=G{gt}'; ws[f'G{ran}'].number_format = N2; ws[f'G{ran}'].font = ARIAL
rma = mt + 3
ws[f'B{rma}'] = 'Gasto de nómina según Mayor de gastos RQ-004'; ws[f'B{rma}'].font = BF
ws[f'G{rma}'] = f'=G{ran}+G{mt}+G{rmed}'; ws[f'G{rma}'].font = BF; ws[f'G{rma}'].number_format = N2
rco = mt + 4
ws[f'B{rco}'] = 'Control: suma del mayor'; ws[f'B{rco}'].font = ARIAL
ws[f'G{rco}'] = mayor_total; ws[f'G{rco}'].number_format = N2
ws[f'G{rco}'].font = Font(name='Arial', size=10, color='FF0000FF')
# nota (importes y conteos calculados en runtime)
medicas = round(sum(it[4] for it in gas_items if it[0] == 'acct' and _concepto_do2(it[2]) == 'Otros gastos de nómina'), 2)
rno = mt + 5
ws.merge_cells(f'B{rno}:L{rno + 1}')
ws[f'B{rno}'] = (f'El anexo de nómina (RQ-002) omite {n_mayor_only} cuentas de gasto '
                 f'(vacaciones, comisiones, premios, estipendio de pasantes y bono familiar) que '
                 f'sí están en el mayor; las {n_comunes} cuentas comunes coinciden. Las pruebas '
                 f'DO-6 a DO-10 ya usan el mayor para esas cuentas. El aporte de asistencia médica '
                 f'a tiempo parcial ({_es(medicas)}) está en el anexo pero no en el mayor de '
                 f'gastos entregado.')
ws[f'B{rno}'].font = NOTE; ws[f'B{rno}'].alignment = Alignment(vertical='top', wrap_text=True)

ws.column_dimensions['P'].hidden = True
for col, w in dict(A=4.0, B=22.26, C=28.0, D=16.84, E=11.85, F=11.39, G=18.87, H=5.0,
                   I=16.12, J=11.39, K=4.73, L=22.15, M=4.73, N=19.86, O=2.73, P=11.39).items():
    ws.column_dimensions[col].width = w


# ===================================================== 2) Controles
co = wb.create_sheet('Controles')
for c, t in [('A1', 'Control'), ('B1', 'Sumaria'), ('C1', 'Esperado'),
             ('D1', 'Diferencia'), ('E1', 'Resultado')]:
    co[c] = t; co[c].font = HWHITE; co[c].fill = FILL_HDR


def _ctrl(r, desc, a, b):
    co[f'A{r}'] = desc; co[f'A{r}'].font = ARIAL
    co[f'B{r}'] = a; co[f'C{r}'] = b
    co[f'B{r}'].number_format = co[f'C{r}'].number_format = N2
    co[f'D{r}'] = f'=ROUND(B{r}-C{r},2)'; co[f'D{r}'].number_format = N2
    co[f'E{r}'] = f'=IF(D{r}=0,"OK","REVISAR")'


_ctrl(2, 'Cuentas trasladadas del anexo', n_total, n_total)
_ctrl(3, 'Pasivo 31-dic-2024', f'={S}!D{pt}', p24)
_ctrl(4, 'Pasivo 31-dic-2025', f'={S}!G{pt}', p25)
_ctrl(5, 'Gasto 31-dic-2024', f'={S}!D{gt}', g24)
_ctrl(6, 'Gasto 31-dic-2025', f'={S}!G{gt}', g25)
_ctrl(7, 'Subtotales por concepto = total gasto 2025', f'={S}!G{rt}', f'={S}!G{gt}')
_ctrl(8, 'Cuentas en subtotales = cuentas de gasto', f'={S}!C{rt}', n_gas)
_ctrl(9, 'Pasivo auditado = 2025 + Debe - Haber', f'={S}!L{pt}',
      f'={S}!G{pt}+{S}!I{pt}-{S}!J{pt}')
_ctrl(10, 'Gasto auditado = 2025 + Debe - Haber', f'={S}!L{gt}',
      f'={S}!G{gt}+{S}!I{gt}-{S}!J{gt}')
_ctrl(11, 'Asiento cuadrado (Debe = Haber)', f'={S}!I{pt}+{S}!I{gt}',
      f'={S}!J{pt}+{S}!J{gt}')
_ctrl(12, 'Gasto según mayor RQ-004 = anexo + cuentas no incluidas − asistencia médica',
      f'={S}!G{rma}', f'={S}!G{rco}')
for col, w in dict(A=44.0, B=18.0, D=13.0, E=11.0).items():
    co.column_dimensions[col].width = w

wb.save(OUT)
