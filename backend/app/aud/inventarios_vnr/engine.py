"""Cálculo VNR puro. No IA, red, ficheros, tipos flotantes ni tasas implícitas."""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import re

VERSION = '1.0.0'
TOOL_ID = 'AUD.INVENTARIOS.VNR'
MAX_ROWS = 2000
CENT = Decimal('0.01')
ZERO = Decimal('0')


def number(value, field, *, maximum=Decimal('1000000000000')):
    if value is None or isinstance(value, bool):
        raise ValueError(f'{field}: dato numérico requerido.')
    s = str(value).strip().replace(' ', '')
    if ',' in s and '.' in s:
        us = s.rfind('.') > s.rfind(',')
        pattern = r'\d{1,3}(,\d{3})+\.\d{1,6}' if us else r'\d{1,3}(\.\d{3})+,\d{1,6}'
        if not re.fullmatch(pattern,s): raise ValueError(f'{field}: agrupación de miles no válida.')
        s = s.replace(',', '') if us else s.replace('.', '').replace(',', '.')
    elif ',' in s:
        if s.count(',') != 1 or len(s.split(',')[-1]) == 3:
            raise ValueError(f'{field}: use formato decimal inequívoco.')
        s = s.replace(',', '.')
    if not re.fullmatch(r'\d+(\.\d{1,6})?', s):
        raise ValueError(f'{field}: use un número no negativo, hasta seis decimales.')
    try:
        n = Decimal(s)
    except InvalidOperation:
        raise ValueError(f'{field}: número no válido.') from None
    if not n.is_finite() or n > maximum:
        raise ValueError(f'{field}: fuera de rango.')
    return n


def money(n):
    return n.quantize(CENT, rounding=ROUND_HALF_UP)


def required(obj, key, limit=2000):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{key}: complete el campo (máximo {limit} caracteres).')
    return value.strip()


def calculate(data):
    if not isinstance(data, dict):
        raise ValueError('Solicitud no válida.')
    context, policy, tax = data.get('context') or {}, dict(data.get('policy') or {}), dict(data.get('tax') or {})
    for key in ('client','country','currency','cutoff','visit','preparer','reviewer','firm','framework','edition','adoption','reuse_scope'):
        required(context,key)
    if context['framework'] not in ('full','sme'):
        raise ValueError('Seleccione NIIF completas o NIIF para las PYMES.')
    if context['framework']=='sme' and context['edition'] not in ('2015','2025'):
        raise ValueError('Seleccione edición PYMES 2015 o 2025 y documente su adopción.')
    if context['firm'] not in ('audit_consulting','partner_auditing') or context['visit'] not in ('Preliminar','Final'):
        raise ValueError('Firma o visita no válida.')
    if context['reuse_scope'] not in ('one','selected','all'):
        raise ValueError('Alcance de reutilización no válido.')
    if context['reuse_scope']=='selected': required(context,'selected_tests')
    if not re.fullmatch('[A-Z]{3}', context['currency']): raise ValueError('Moneda: código de tres letras.')
    try:
        cutoff=date.fromisoformat(context['cutoff']); year=int(context.get('year',0))
        if not 2000 <= year <= 2100 or cutoff.year != year: raise ValueError()
    except (TypeError, ValueError): raise ValueError('Fecha de corte y ejercicio deben corresponder.') from None
    for key in ('basis','normative_reference'): required(policy,key)
    if policy.get('reviewed') is not True or policy.get('evidence_reviewed') is not True:
        raise ValueError('Revise y confirme normativa, política y evidencia antes de procesar.')
    method=policy.get('selling_method')
    if method not in ('unit','ratio'): raise ValueError('Seleccione método de gastos de venta.')
    ratio=ZERO
    if method=='ratio':
        expenses=number(policy.get('eligible_expenses'),'Gastos necesarios')
        base=number(policy.get('sales_base'),'Ventas de la población')
        required(policy,'allocation_basis')
        if base<=0: raise ValueError('La base de ventas debe ser mayor que cero.')
        ratio=expenses/base
        policy['eligible_expenses']=str(expenses);policy['sales_base']=str(base)
    else:
        policy['eligible_expenses']='0';policy['sales_base']='0'
    rows=data.get('rows')
    if not isinstance(rows,list) or not 1<=len(rows)<=MAX_ROWS:
        raise ValueError(f'Cargue entre 1 y {MAX_ROWS} ítems de inventario.')
    enabled=tax.get('enabled') is True
    rate=ZERO
    if enabled:
        required(tax,'reference')
        rate=number(tax.get('rate'),'Tasa tributaria',maximum=Decimal('1'))
        tax['rate']=str(rate)
        if tax.get('recognize_dta') is True: required(tax,'recoverability')
    totals={k:ZERO for k in ('cost','nrv','impairment','recorded_impairment','adjustment','expense','reversal','carrying','dta','dtl')}
    out=[]; seen=set()
    for index,row in enumerate(rows,1):
        if not isinstance(row,dict): raise ValueError(f'Fila {index}: estructura no válida.')
        code=required(row,'code',100)
        if code in seen: raise ValueError(f'Código duplicado: {code}. Use identificador único por ítem/lote.')
        seen.add(code); description=required(row,'description',500); source=required(row,'source',1000)
        q=number(row.get('quantity'),f'{code}: cantidad',maximum=Decimal('1000000000'))
        unit=number(row.get('unit_cost'),f'{code}: costo')
        price=number(row.get('selling_price'),f'{code}: precio')
        completion=number(row.get('completion_cost'),f'{code}: terminación')
        selling=money(price*ratio) if method=='ratio' else number(row.get('selling_cost'),f'{code}: venta')
        recorded=number(row.get('recorded_impairment'),f'{code}: deterioro registrado')
        if recorded!=money(recorded): raise ValueError(f'{code}: deterioro registrado admite dos decimales.')
        cost=money(q*unit)
        if recorded>cost: raise ValueError(f'{code}: deterioro registrado superior al costo de la población al corte.')
        raw_nrv=price-completion-selling
        nrv_unit=max(ZERO,raw_nrv)
        nrv=money(q*nrv_unit)
        impairment=max(ZERO,cost-nrv)
        adjustment=impairment-recorded
        if adjustment<0: required(policy,'reversal_basis')
        carrying=cost-impairment
        dta=dtl=ZERO;tax_base=None
        if enabled:
            tax_base=number(row.get('tax_base'),f'{code}: base fiscal total')
            dta=money(max(ZERO,tax_base-carrying)*rate) if tax.get('recognize_dta') is True else ZERO
            dtl=money(max(ZERO,carrying-tax_base)*rate)
        computed=dict(cost=cost,nrv=nrv,impairment=impairment,recorded_impairment=recorded,adjustment=adjustment,expense=max(ZERO,adjustment),reversal=max(ZERO,-adjustment),carrying=carrying,dta=dta,dtl=dtl)
        for k,v in computed.items():totals[k]+=v
        out.append(dict(code=code,description=description,source=source,quantity=str(q),unit_cost=str(unit),selling_price=str(price),completion_cost=str(completion),selling_cost=str(selling),nrv_unit=str(money(nrv_unit)),raw_nrv_unit=str(raw_nrv),tax_base=str(tax_base) if tax_base is not None else None,**{k:str(money(v)) for k,v in computed.items()}))
    ledger=number(data.get('ledger_cost'),'Saldo contable bruto')
    ledger_impairment=number(data.get('ledger_impairment'),'Deterioro en mayor')
    tolerance=number(data.get('tolerance'),'Tolerancia')
    cost_diff=money(totals['cost']-ledger);imp_diff=money(totals['recorded_impairment']-ledger_impairment)
    for kind in ('dta','dtl'):
        recorded_tax=number(tax.get('recorded_'+kind),'Impuesto diferido registrado') if enabled else ZERO
        totals[kind+'_adjustment']=totals[kind]-recorded_tax
        if enabled:tax['recorded_'+kind]=str(recorded_tax)
    fingerprint=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return {'tool_id':TOOL_ID,'version':VERSION,'status':'BORRADOR PARA REVISION','input_sha256':fingerprint,'context':context,'policy':policy,'tax':tax,'rows':out,'totals':{k:str(money(v)) for k,v in totals.items()},'controls':{'cost_difference':str(cost_diff),'impairment_difference':str(imp_diff),'reconciled':abs(cost_diff)<=tolerance and abs(imp_diff)<=tolerance,'row_count':len(out)},'selling_ratio':str(ratio),'evidence':data.get('evidence',[]),'ledger_cost':str(ledger),'ledger_impairment':str(ledger_impairment),'tolerance':str(tolerance)}
