"""AuditBrain Decimal engine. Only reviewed declarative operators; never eval client input."""
import json
from decimal import Decimal, ROUND_HALF_UP, localcontext
from datetime import date
VERSION = '3.0.0'
MAX_PERIODS = 600
# domain.mjs corta en ±999999999999999999 sobre enteros de escala 1e6; en
# decimales es el mismo tope. Sin el tope, con importes absurdos el servidor
# abortaría con su mensaje y Python devolvería un número: el contraste lo
# marcaría como discrepancia en vez de explicar la causa.
MAX_VALUE = Decimal('999999999999.999999')


def _quantize(n, precision):
    # Same two-step boundary as domain.mjs: the BigInt operators land on six
    # decimals and only then `formatted` rounds to the declared precision.
    n = n.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    n = n.quantize(Decimal('0.01') if precision == 2 else Decimal('0.000001'), rounding=ROUND_HALF_UP)
    return abs(n) if n == 0 else n


def _apply(rule, resolve):
    a, b = resolve(rule['a']), resolve(rule['b'])
    op = rule['op']
    if op == 'add': n = a + b
    elif op == 'subtract': n = a - b
    elif op == 'multiply': n = a * b
    elif op == 'divide': n = a / b
    elif op == 'min': n = min(a, b)
    elif op == 'max': n = max(a, b)
    else: raise ValueError('Operador no autorizado')
    # El tope se comprueba en el mismo punto que domain.mjs: sobre el resultado
    # ya llevado a seis decimales, antes de redondear a la precisión declarada.
    n = n.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    if n > MAX_VALUE or n < -MAX_VALUE:
        raise ValueError('Resultado fuera del rango admitido. Divida la población en lotes.')
    return _quantize(n, rule['precision'])


def _series_order(d):
    return d['series'].get('order', ['backward', 'forward'])


def _series_keys(d):
    listas = {'backward': d['series'].get('backward', []), 'forward': d['series'].get('forward', [])}
    return [x['key'] for p in _series_order(d) for x in listas[p]]


def run_series(d, row, values):
    # `backward` walks n..1 —that is what carries a discount to present value—
    # and `forward` walks 1..n over those same period rows.
    # domain.mjs derives n from `formatted(count, 2)` and then takes the integer
    # part, so it rounds to two decimals BEFORE truncating: 5.996 is six periods,
    # not five. Truncating straight away would drift from the authority.
    n = int(values[d['series']['count']].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    if n < 1 or n > MAX_PERIODS:
        raise ValueError('Periodos fuera de rango')
    filas = [{'id': row.get('id'), 'periodo': str(i + 1), 'periodos': str(n)} for i in range(n)]
    celdas = [{'periodo': Decimal(i + 1), 'periodos': Decimal(n)} for i in range(n)]
    listas = {'backward': d['series'].get('backward', []), 'forward': d['series'].get('forward', [])}
    for nombre in _series_order(d):
        lista = listas[nombre]
        semillas = {x['key']: x['seed'] for x in lista if 'seed' in x}
        orden = range(n - 1, -1, -1) if nombre == 'backward' else range(n)
        anterior = None
        for i in orden:
            propio = celdas[i]
            for rule in lista:
                def resolve(x, propio=propio, anterior=anterior):
                    if x[0] == '#': return Decimal(x[1:])
                    if x[0] == '@':
                        k = x[1:]
                        if anterior is not None: return anterior.get(k, Decimal(0))
                        # No previous period at the edge of a pass. Without a seed
                        # @key is zero —right for an annuity—; with a seed it starts
                        # there, which is what a single payment at maturity needs.
                        sd = semillas.get(k)
                        if sd is None: return Decimal(0)
                        if sd[0] == '#': return Decimal(sd[1:])
                        return propio.get(sd, values.get(sd, Decimal(0)))
                    if x[0] == '^':
                        k = x[1:]
                        return celdas[0].get(k, propio.get(k, Decimal(0)))
                    return propio.get(x, values.get(x))
                v = _apply(rule, resolve)
                propio[rule['key']] = v
                filas[i][rule['key']] = format(v, 'f')
            anterior = propio
    agregados = {}
    for k in _series_keys(d):
        agregados[k + '_inicial'] = celdas[0].get(k, Decimal(0))
        agregados[k + '_final'] = celdas[n - 1].get(k, Decimal(0))
        agregados[k + '_total'] = sum((c.get(k, Decimal(0)) for c in celdas), Decimal(0))
    return filas, agregados


# --- Flujos irregulares con fechas (NIIF 16.26/16.27, NIC 36.31, NIC 37.45) ---
# Espejo exacto de domain.mjs. Aqui NO se usa Decimal ni `**`: el descuento corre
# sobre enteros de Python, que son identicos a BigInt, con el mismo algoritmo y el
# mismo numero de terminos. Si un motor aproximara con serie y el otro usara la
# potencia nativa, discreparian en el ultimo decimal y el servidor rechazaria toda
# ejecucion con flujos.
#
#   (1+i)^(d/365) = (1+i)^q * exp(ln(1+i)*r/365),   con d = 365q + r
#
# Los factores viven en escala 1e18 porque 1e6 no alcanza: a 90 dias el factor se
# desviaria 1.4e-6, mas de un centavo sobre un flujo de 8.000.
SCALE6 = 10 ** 6
FLOW_SCALE = 10 ** 18
LN_TERMS = 40
EXP_TERMS = 40
MAX_FLOWS = 100000
MAX_FLOW_DAYS = 36500


def _rounded(n, d):
    """Mismo redondeo que `rounded` de domain.mjs: al alejado del cero."""
    if d == 0:
        raise ValueError('División por cero.')
    neg = (n < 0) != (d < 0)
    n, d = abs(n), abs(d)
    q = (n + d // 2) // d
    return -q if neg else q


def _scaled(v):
    """Un importe o una tasa del cliente, en entero de escala 1e6."""
    return int(Decimal(str(v)).scaleb(6).to_integral_value(rounding=ROUND_HALF_UP))


def _ln_big(x):
    if x <= 0:
        raise ValueError('La tasa de descuento debe ser mayor que -1.')
    z = _rounded((x - FLOW_SCALE) * FLOW_SCALE, x + FLOW_SCALE)
    term = z
    total = z
    for k in range(1, LN_TERMS):
        term = _rounded(term * z * z, FLOW_SCALE * FLOW_SCALE)
        total += _rounded(term, 2 * k + 1)
    return 2 * total


def _exp_big(x):
    term = FLOW_SCALE
    total = FLOW_SCALE
    for k in range(1, EXP_TERMS):
        term = _rounded(term * x, k * FLOW_SCALE)
        total += term
    return total


def _pow_big(base, dias, ln):
    q, r = divmod(dias, 365)
    p = FLOW_SCALE
    for _ in range(q):
        p = _rounded(p * base, FLOW_SCALE)
    return _rounded(p * _exp_big(_rounded(ln * r, 365)), FLOW_SCALE) if r else p


def run_flows(d, row, values, mios):
    medicion = date.fromisoformat(str(row[d['flows']['date']]))
    base = FLOW_SCALE + _scaled(values[d['flows']['rate']]) * (FLOW_SCALE // SCALE6)
    ln = _ln_big(base)
    alto = 0
    total = 0
    ponderado = 0
    for x in mios:
        dias = (date.fromisoformat(str(x['fecha'])) - medicion).days
        if dias < 0 or dias > MAX_FLOW_DAYS:
            raise ValueError('Flujo fuera del plazo admitido desde la fecha de medición.')
        importe = _scaled(x['importe'])
        alto += _rounded(importe * FLOW_SCALE * SCALE6, _pow_big(base, dias, ln))
        total += importe
        ponderado += importe * dias
    dias_prom = 0 if total == 0 else _rounded(ponderado * SCALE6, total)
    return {'flujos_vp': Decimal(_rounded(alto, SCALE6)).scaleb(-6),
            'flujos_total': Decimal(total).scaleb(-6),
            'flujos_dias': Decimal(dias_prom).scaleb(-6)}


def _by_contract(rows, flows):
    if not isinstance(flows, list) or not flows or len(flows) > MAX_FLOWS:
        raise ValueError('Calendario de pagos fuera de rango.')
    grupos = {}
    for x in flows:
        grupos.setdefault(str(x['id']).strip(), []).append(x)
    ids = {str(r.get('id', '')).strip() for r in rows}
    for k in grupos:
        if k not in ids:
            raise ValueError('El flujo de %s no tiene contrato que lo ampare en la población.' % k)
    return grupos


def calculate(payload):
    d, rows, p = payload['definition'], payload['rows'], payload.get('parameters', {})
    flows = payload.get('flows', [])
    por_contrato = _by_contract(rows, flows) if 'flows' in d and rows else None
    result = []
    schedule = []
    # `totals` replica calculate() de domain.mjs: solo las reglas de dos
    # decimales y, además, el campo de conciliación cuando es un campo del
    # contrato. Los agregados de la serie no entran.
    totals = {}
    control = d['control'] if any(f['key'] == d['control'] for f in d['fields']) else None
    with localcontext() as ctx:
        ctx.prec = 50
        for row in rows:
            out = dict(row)
            values = {f['key']: Decimal(str(row[f['key']])) for f in d['fields'] if f['type'] == 'number'}
            if 'series' in d:
                filas, agregados = run_series(d, row, values)
                schedule.extend(filas)
                values.update(agregados)
                for k, v in agregados.items():
                    out[k] = format(_quantize(v, 2), 'f')
            if 'flows' in d:
                mios = por_contrato.get(str(row.get('id', '')).strip())
                if not mios:
                    raise ValueError('Sin calendario de pagos para %s.' % row.get('id', 'la fila'))
                ag = run_flows(d, row, values, mios)
                values.update(ag)
                for k, v in ag.items():
                    out[k] = format(_quantize(v, 2), 'f')
            if d['id'] == 'pce':
                days = max((date.fromisoformat(p['cutoff']) - date.fromisoformat(row['due_date'])).days, 0)
                bucket = next(b for b in p['buckets'] if days >= b['min'] and (b['max'] is None or days <= b['max']))
                out['days'], out['rate'] = str(days), str(bucket['rate'])
                values['rate'] = Decimal(str(bucket['rate']))
                out['bucket'] = str(bucket['min']) + '–' + (str(bucket['max']) if bucket['max'] is not None else '∞')
            for r in d['rules']:
                # Mismo operador, mismo redondeo y mismo tope que la serie: una
                # sola implementación, como en domain.mjs.
                n = _apply(r, lambda x: Decimal(x[1:]) if x[0] == '#' else values[x])
                out[r['key']] = format(n, 'f')
                values[r['key']] = n
                if r['precision'] == 2:
                    totals[r['key']] = totals.get(r['key'], Decimal(0)) + n
            if control is not None:
                totals[control] = totals.get(control, Decimal(0)) + values[control]
            result.append(out)
    return {'engine': VERSION, 'rows': result, 'schedule': schedule,
            'totals': {k: format(_quantize(v, 2), 'f') for k, v in totals.items()}}

def dispatch(text):
    return json.dumps(calculate(json.loads(text)), ensure_ascii=False)
