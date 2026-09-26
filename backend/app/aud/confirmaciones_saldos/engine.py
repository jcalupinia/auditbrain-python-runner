"""Motor de circularización. No IA, red, ficheros, tipos flotantes ni envío real.

`calculate(payload)` valida la ficha y la muestra, asigna método por rubro, arma
las cartas, el manifiesto de envío y el control de respuestas. El envío efectivo lo
realiza el adaptador (correo del auditor o de la plataforma); el núcleo solo prepara.
"""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import re

from .plantillas import TYPES, METHODS, TYPE_LABEL_ES, LANGS, render_letter

VERSION = '1.0.0'
TOOL_ID = 'AUD.CONFIRMACIONES.SALDOS'
MAX_ROWS = 2000
CENT = Decimal('0.01')
ZERO = Decimal('0')
EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
# Rubros donde el importe es obligatorio cuando la carta declara la cifra.
AMOUNT_REQUIRED = ('cuentas_por_cobrar', 'proveedores')


def number(value, field, *, maximum=Decimal('1000000000000')):
    if value is None or isinstance(value, bool):
        raise ValueError(f'{field}: dato numérico requerido.')
    s = str(value).strip().replace(' ', '')
    if ',' in s and '.' in s:
        us = s.rfind('.') > s.rfind(',')
        pattern = r'\d{1,3}(,\d{3})+\.\d{1,6}' if us else r'\d{1,3}(\.\d{3})+,\d{1,6}'
        if not re.fullmatch(pattern, s):
            raise ValueError(f'{field}: agrupación de miles no válida.')
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


def optional(obj, key, limit=2000):
    value = obj.get(key)
    if value in (None, ''):
        return ''
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'{key}: texto no válido (máximo {limit} caracteres).')
    return value.strip()


def email(value, field):
    v = str(value or '').strip()
    if not EMAIL.fullmatch(v) or len(v) > 254:
        raise ValueError(f'{field}: correo electrónico no válido.')
    return v


def format_money(currency, amount):
    return f'{currency} {amount:,.2f}'


def letter_text(letter):
    """Cuerpo plano de la carta, para huella y exportaciones."""
    blocks = letter['blocks']
    parts = list(letter['salutation']) + ['']
    parts += [blocks[0]] if blocks else []
    parts += ['· ' + it for it in letter.get('items', [])]
    if len(blocks) > 1:
        parts += [''] + blocks[1:]
    parts += [''] + letter['signature']
    if letter['response_lines']:
        parts += ['', letter['response_title']] + letter['response_lines']
    return '\n'.join(parts)


def calculate(data):
    if not isinstance(data, dict):
        raise ValueError('Solicitud no válida.')
    context = dict(data.get('context') or {})
    defaults = dict(data.get('defaults') or {})
    for key in ('client', 'country', 'currency', 'cutoff', 'visit', 'preparer', 'reviewer',
                'firm', 'signatory', 'response_deadline'):
        required(context, key)
    context['client_ruc'] = optional(context, 'client_ruc', 30)
    context['signatory_role'] = optional(context, 'signatory_role', 200)
    context['auditor_address'] = optional(context, 'auditor_address', 300)
    context['auditor_phone'] = optional(context, 'auditor_phone', 60)
    context['auditor_email'] = email(context.get('auditor_email'), 'Correo del auditor')
    context['language'] = context.get('language') or 'es'
    if context['language'] not in LANGS:
        raise ValueError('Idioma no disponible.')
    context['place'] = optional(context, 'place', 120)
    context['letter_date'] = optional(context, 'letter_date', 20)
    context['period_start'] = optional(context, 'period_start', 20)
    context['include_response_slip'] = bool((data.get('defaults') or {}).get('include_response_slip'))
    if context['firm'] not in ('audit_consulting', 'partner_auditing'):
        raise ValueError('Firma no válida.')
    if context['visit'] not in ('Preliminar', 'Final'):
        raise ValueError('Visita no válida (Preliminar o Final).')
    if not re.fullmatch('[A-Z]{3}', context['currency']):
        raise ValueError('Moneda: código de tres letras.')
    try:
        cutoff = date.fromisoformat(context['cutoff'])
        year = int(context.get('year', 0))
        if not 2000 <= year <= 2100 or cutoff.year != year:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('Fecha de corte y ejercicio deben corresponder.') from None
    try:
        deadline = date.fromisoformat(context['response_deadline'])
        if deadline < cutoff:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('Fecha límite de respuesta no válida o anterior al corte.') from None
    context['request_round'] = context.get('request_round') or 'primera'
    if context['request_round'] not in ('primera', 'segunda'):
        raise ValueError('Vuelta de solicitud no válida (primera o segunda).')
    default_method = defaults.get('method')
    if default_method is not None and default_method not in METHODS:
        raise ValueError('Método por defecto no válido.')

    items = data.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ROWS:
        raise ValueError(f'Cargue entre 1 y {MAX_ROWS} elementos en la muestra.')

    out, letters, dispatch, register = [], [], [], []
    seen = set()
    by_type, by_method = {}, {}
    sampled = {}
    with_email = 0
    for index, row in enumerate(items, 1):
        if not isinstance(row, dict):
            raise ValueError(f'Elemento {index}: estructura no válida.')
        code = required(row, 'id', 100) if row.get('id') else required(row, 'code', 100)
        if code in seen:
            raise ValueError(f'Identificador duplicado: {code}. Use uno único por destinatario.')
        seen.add(code)
        rtype = row.get('type')
        if rtype not in TYPES:
            raise ValueError(f'{code}: tipo de confirmación no válido.')
        entity = required(row, 'entity', 300)
        contact_name = optional(row, 'contact_name', 200)
        contact_address = optional(row, 'contact_address', 300)
        account_ref = optional(row, 'account_ref', 120)
        reference = optional(row, 'reference', 300)
        notes = optional(row, 'notes', 500)
        method = row.get('method') or default_method or TYPES[rtype]['default_method']
        if method not in METHODS:
            raise ValueError(f'{code}: método de confirmación no válido.')
        contact_email = ''
        if row.get('contact_email') not in (None, ''):
            contact_email = email(row.get('contact_email'), f'{code}: correo del contacto')

        amount = None
        amount_text = None
        if row.get('amount') not in (None, ''):
            amount = money(number(row.get('amount'), f'{code}: saldo'))
            amount_text = format_money(context['currency'], amount)
        elif rtype in AMOUNT_REQUIRED and method != 'en_blanco':
            raise ValueError(f'{code}: indique el saldo o use el método en blanco para este rubro.')

        item = {
            'id': code, 'type': rtype, 'entity': entity, 'contact_name': contact_name,
            'contact_email': contact_email, 'contact_address': contact_address,
            'account_ref': account_ref, 'reference': reference, 'notes': notes,
            'method': method, 'amount': str(amount) if amount is not None else None,
        }
        letter = render_letter(context, item, amount_text)
        body = letter_text(letter)
        body_sha = hashlib.sha256(body.encode('utf-8')).hexdigest()
        letter['id'] = code
        letter['entity'] = entity
        letter['text'] = body
        letters.append(letter)

        by_type[rtype] = by_type.get(rtype, 0) + 1
        by_method[method] = by_method.get(method, 0) + 1
        if amount is not None:
            sampled[rtype] = sampled.get(rtype, ZERO) + amount
        envio_status = 'Listo para envío' if contact_email else 'Falta correo del contacto'
        if contact_email:
            with_email += 1

        out.append(item)
        dispatch.append({
            'id': code, 'type': rtype, 'entity': entity, 'to': contact_email,
            'subject': letter['subject'], 'method': method, 'status': envio_status,
            'body_sha256': body_sha,
        })
        register.append({
            'id': code, 'type_label': TYPE_LABEL_ES[rtype], 'entity': entity,
            'contact_name': contact_name, 'method': method,
            'amount': amount_text or '—', 'reference': reference or account_ref or '',
            'envio_status': envio_status, 'sent_date': '', 'response_date': '',
            'response_type': '', 'difference': '', 'second_request': '', 'resolution': '',
        })

    # Cobertura por rubro frente al mayor (opcional).
    tolerance = money(number(data.get('tolerance', '0.01'), 'Tolerancia'))
    coverage = []
    ledger_by_type = {}
    for entry in data.get('coverage') or []:
        if not isinstance(entry, dict) or entry.get('type') not in TYPES:
            raise ValueError('Cobertura: rubro no válido.')
        ledger_by_type[entry['type']] = money(number(entry.get('ledger_balance'), 'Saldo del mayor'))
    for rtype in sorted(set(by_type) | set(ledger_by_type)):
        s = money(sampled.get(rtype, ZERO))
        ledger = ledger_by_type.get(rtype)
        if ledger is not None:
            diff = money(ledger - s)
            pct = (s / ledger * 100) if ledger > 0 else ZERO
            coverage.append({
                'type': rtype, 'label': TYPE_LABEL_ES[rtype], 'sampled': str(s),
                'ledger': str(ledger), 'difference': str(diff),
                'coverage_pct': str(money(pct)), 'count': by_type.get(rtype, 0),
                'within_tolerance': abs(diff) <= tolerance,
            })
        else:
            coverage.append({
                'type': rtype, 'label': TYPE_LABEL_ES[rtype], 'sampled': str(s),
                'ledger': None, 'difference': None, 'coverage_pct': None,
                'count': by_type.get(rtype, 0), 'within_tolerance': None,
            })

    total_sampled = money(sum(sampled.values(), ZERO))
    fingerprint = hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return {
        'tool_id': TOOL_ID, 'version': VERSION, 'status': 'BORRADOR PARA REVISION',
        'input_sha256': fingerprint, 'context': context, 'defaults': defaults,
        'items': out, 'letters': letters, 'dispatch': dispatch, 'register': register,
        'coverage': coverage, 'tolerance': str(tolerance),
        'totals': {
            'count': len(out), 'with_email': with_email, 'without_email': len(out) - with_email,
            'total_sampled': str(total_sampled),
            'by_type': by_type, 'by_method': by_method,
        },
    }
