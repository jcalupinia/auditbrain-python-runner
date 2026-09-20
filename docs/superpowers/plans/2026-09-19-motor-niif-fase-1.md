# Motor de cálculo NIIF · Fase 1 — plan de implementación

> **Para quien ejecute esto:** SUB-SKILL OBLIGATORIA: usar `superpowers:subagent-driven-development` (recomendada) o `superpowers:executing-plans` para implementar tarea por tarea. Los pasos usan casillas (`- [ ]`) para seguimiento.

**Objetivo:** dejar el motor de series ejecutable de punta a punta en el sitio y añadir la primitiva de flujos irregulares con fechas, que es la que hace falta para medir un arrendamiento real.

**Arquitectura:** el motor es declarativo y vive en tres sitios que no pueden divergir: `lib/tools/domain.mjs` (autoridad, BigInt escala 1e6), `public/engine/audit_engine.py` (Pyodide en el navegador, `Decimal`) y `lib/tools/portable-engine.mjs` (copia generada por `toString()` que viaja dentro del HTML descargado). Cada primitiva nueva se implementa en los tres y se prueba contra un caso de referencia calculado aparte.

**Herramientas:** Node 22 con `node:test` (no hay script `test` en `package.json`; se invoca `node --test <archivo>`), Python 3 de sistema para el contraste cruzado, esbuild para montar las rutas de API en las pruebas de integración, D1/SQLite en memoria.

**Spec:** `docs/superpowers/specs/2026-09-19-motor-calculo-niif-design.md`

**Raíz de trabajo:** `C:\Users\jcalu\Desktop\PROYECTOS CLAUDE\auditbrain-site`. Todas las rutas son relativas a ella salvo indicación contraria.

---

## Corrección de orden respecto de la spec

La spec lista «D1, D2, D3, luego el espejo en Python». Al planificar se ve que **el espejo en Python tiene que ir antes que D2**: simetrizar el contraste sobre un Python que no sabe de series convertiría un fallo silencioso en un bloqueo total. Orden real: D1 → espejo → D2 → D3 → flujos.

---

## Estructura de archivos

| Archivo | Responsabilidad | Acción |
|---|---|---|
| `scripts/export-portable-engine.mjs` | Genera el motor portátil desde `domain.mjs` | Modificar: exportar `portableSource()` para que la prueba use la misma fuente |
| `tests/tools/portable.test.mjs` | Falla si el portátil quedó desincronizado | Crear |
| `package.json` | Script `engine:export` | Modificar |
| `public/engine/audit_engine.py` | Motor Python: series, totales y excepciones | Modificar |
| `tests/tools/series-cross.test.mjs` | Contrasta JS contra Python real, fila a fila y cuadro a cuadro | Crear |
| `app/api/tools/route.ts` | Contraste simétrico servidor/Python | Modificar (líneas 69-71) |
| `lib/tools/domain.mjs` | Motor autoridad: población de flujos y descuento por días | Modificar |
| `lib/tools/exports.mjs` | Cédula `13_Cuadro` desde `run.schedule` | Modificar |
| `lib/tools/workbook-presentation.mjs` | Etiqueta y anchos de la cédula nueva | Modificar |
| `tests/tools/schedule-sheet.test.mjs` | La cédula aparece solo si hay serie | Crear |
| `tests/tools/flows.test.mjs` | Casos de referencia de flujos con fechas | Crear |

---

## Task 0: Control de versiones en la réplica

La réplica tiene `.gitignore` pero **nunca se inicializó git**. Un cambio de este tamaño sin historial es imprudente, y las tareas siguientes terminan en commit.

**Archivos:**
- Crear: `.git/` (por `git init`)

- [ ] **Paso 1: Comprobar que no hay repositorio**

```bash
git -C "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" rev-parse --is-inside-work-tree
```

Esperado: `fatal: not a git repository`

- [ ] **Paso 2: Inicializar y comprobar que node_modules queda fuera**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && git init -q && git add -A && git status --short | grep -c node_modules
```

Esperado: `0` (el `.gitignore` existente ya excluye `/node_modules`, `dist` y `.wrangler`)

- [ ] **Paso 3: Primer commit**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && git commit -q -m "chore: estado inicial de la replica antes del motor NIIF fase 1" && git log --oneline -1
```

---

## Task 1 · D1: el motor portátil no puede divergir en silencio

Hoy `lib/tools/portable-engine.mjs` se regenera a mano y nada avisa cuando queda viejo. Se desincronizó el 19-sep al añadir las series.

**Archivos:**
- Modificar: `scripts/export-portable-engine.mjs`
- Modificar: `package.json` (bloque `scripts`)
- Crear: `tests/tools/portable.test.mjs`

- [ ] **Paso 1: Escribir la prueba que falla**

Crear `tests/tools/portable.test.mjs`:

```js
import test from 'node:test';import assert from 'node:assert/strict';
import {portableSource} from '../../scripts/export-portable-engine.mjs';
import {PORTABLE_ENGINE_SOURCE} from '../../lib/tools/portable-engine.mjs';

test('el motor portatil esta sincronizado con domain.mjs', () => {
  assert.equal(portableSource(), PORTABLE_ENGINE_SOURCE,
    'El motor portatil quedo desincronizado. Corre: npm run engine:export');
});
```

- [ ] **Paso 2: Correr la prueba y ver que falla**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/portable.test.mjs
```

Esperado: FAIL — `portableSource is not a function` (el script todavía no la exporta)

- [ ] **Paso 3: Refactorizar el script para exportar la fuente**

Reescribir `scripts/export-portable-engine.mjs` completo:

```js
import {writeFile} from 'node:fs/promises';
import {SHEETS,ENGINE_VERSION,MAX_ROWS,MAX_PERIODS,decimal,rounded,formatted,validDate,seriesOrder,seriesKeys,validateSeries,validateDefinition,validateRows,checkBuckets,runSeries,calculate} from '../lib/tools/domain.mjs';

/** Fuente del motor portatil. La usan el generador y la prueba de sincronia. */
export function portableSource(){
 const fns=[decimal,formatted,validDate,seriesOrder,seriesKeys,validateSeries,validateDefinition,validateRows,checkBuckets,runSeries,calculate];
 return `const ENGINE_VERSION=${JSON.stringify(ENGINE_VERSION)},MAX_ROWS=${MAX_ROWS},MAX_PERIODS=${MAX_PERIODS},SCALE=1000000n,SHEETS=${JSON.stringify(SHEETS)};`
  +`const rounded=${rounded.toString()};${fns.map(f=>f.toString()).join('\n')}`;
}

if(process.argv[1]&&process.argv[1].endsWith('export-portable-engine.mjs')){
 await writeFile(new URL('../lib/tools/portable-engine.mjs',import.meta.url),
  '// Generado por scripts/export-portable-engine.mjs. Los nombres estables sobreviven a la minificacion.\n'
  +'export const PORTABLE_ENGINE_SOURCE='+JSON.stringify(portableSource())+';\n');
}
```

**`runSeries` depende de `OP` y `apply`, que son constantes de módulo y no se exportan.** Sin ellas el portátil lanza `OP is not defined`. Por eso el preámbulo las lleva literales; el `return` queda así:

```js
 return `const ENGINE_VERSION=${JSON.stringify(ENGINE_VERSION)},MAX_ROWS=${MAX_ROWS},MAX_PERIODS=${MAX_PERIODS},SCALE=1000000n,SHEETS=${JSON.stringify(SHEETS)};`
  +`const rounded=${rounded.toString()};`
  +`const OP={add:(a,b)=>a+b,subtract:(a,b)=>a-b,multiply:(a,b)=>rounded(a*b,SCALE),divide:(a,b)=>rounded(a*SCALE,b),min:(a,b)=>a<b?a:b,max:(a,b)=>a>b?a:b};`
  +`function apply(rule,resolve){const n=OP[rule.op](resolve(rule.a),resolve(rule.b));if(n>999999999999999999n||n< -999999999999999999n)throw Error('Resultado fuera del rango admitido.');return decimal(formatted(n,rule.precision));}`
  +fns.map(f=>f.toString()).join('\n');
```

Si `domain.mjs` cambia `OP` o `apply`, hay que cambiarlos aquí también. La prueba del paso 6 **no** detecta eso —compara el portátil contra sí mismo—, así que el paso 5 es el que importa.

- [ ] **Paso 4: Regenerar y añadir el script a package.json**

En `package.json`, dentro de `"scripts"`, añadir después de `"db:generate"`:

```json
    "engine:export": "node scripts/export-portable-engine.mjs"
```

Luego:

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && npm run engine:export
```

- [ ] **Paso 5: Comprobar que el portátil realmente ejecuta**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node -e "import('./lib/tools/portable-engine.mjs').then(({PORTABLE_ENGINE_SOURCE:s})=>{const f=new Function(s+';return {calculate,MAX_PERIODS};')();console.log('MAX_PERIODS',f.MAX_PERIODS,'| calculate',typeof f.calculate);})"
```

Esperado: `MAX_PERIODS 600 | calculate function` — sin `OP is not defined`

- [ ] **Paso 6: Correr la prueba y ver que pasa**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/portable.test.mjs
```

Esperado: `# pass 1  # fail 0`

- [ ] **Paso 7: Commit**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && git add scripts/export-portable-engine.mjs lib/tools/portable-engine.mjs package.json tests/tools/portable.test.mjs && git commit -q -m "fix(D1): el motor portatil se regenera con npm run engine:export y una prueba detecta la divergencia"
```

---

## Task 2: Espejo de las series en `audit_engine.py`

Sin esto, toda herramienta con serie falla la ejecución con «La ejecución Python no coincide».

**Archivos:**
- Modificar: `public/engine/audit_engine.py`
- Crear: `tests/tools/series-cross.test.mjs`

- [ ] **Paso 1: Escribir la prueba cruzada que falla**

Crear `tests/tools/series-cross.test.mjs`:

```js
import test from 'node:test';import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {calculate} from '../../lib/tools/domain.mjs';

const f=(k,l,t='number')=>({key:k,label:l,type:t});
const r=(key,label,op,a,b,precision=2)=>({key,label,op,a,b,precision});

// NIIF 16.26 y 36: cinco pagos anuales vencidos de 10.000 al 5%.
const definition={id:'custom',name:'Arrendamiento',area:'Arrendamientos',
 fields:[f('id','Contrato','text'),f('pago','Pago'),f('tasa','Tasa'),f('n','Periodos')],
 series:{count:'n',
  backward:[r('acum','Saldo mas pago','add','@apertura','pago',6),
            r('uno_mas','Uno mas la tasa','add','tasa','#1',6),
            r('apertura','Pasivo al inicio','divide','acum','uno_mas',6)],
  forward:[r('interes','Interes del periodo','multiply','apertura','tasa',2),
           r('con_interes','Pasivo mas interes','add','apertura','interes',6),
           r('cierre','Pasivo al cierre','subtract','con_interes','pago',2)]},
 rules:[r('pasivo_inicial','Pasivo en el reconocimiento','add','apertura_inicial','#0')],
 control:'pago',primary:'pasivo_inicial'};
const rows=[{id:'L-001',pago:'10000',tasa:'0.05',n:'5'}];

function python(payload){
 const out=spawnSync('python',['-c',
  "import runpy,sys; m=runpy.run_path('public/engine/audit_engine.py'); print(m['dispatch'](sys.stdin.read()))"],
  {input:JSON.stringify(payload),encoding:'utf8'});
 assert.equal(out.status,0,out.stderr);
 return JSON.parse(out.stdout);
}

test('NIIF 16: el pasivo inicial es 43294.77 y el cuadro cierra en cero', () => {
  const js=calculate(definition,rows);
  assert.equal(js.rows[0].pasivo_inicial,'43294.77');
  assert.equal(js.schedule.length,5);
  assert.equal(js.schedule[4].cierre,'0.00');
});

test('Python devuelve exactamente las mismas filas y el mismo cuadro que el servidor', () => {
  const js=calculate(definition,rows);
  const py=python({definition,rows,parameters:{}});
  assert.equal(py.engine,js.engine);
  assert.deepEqual(py.rows,js.rows);
  assert.deepEqual(py.schedule,js.schedule);
});
```

- [ ] **Paso 2: Correr y ver que falla**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/series-cross.test.mjs
```

Esperado: la primera prueba PASA (el motor JS ya tiene series); la segunda FALLA porque `py.rows` no trae `apertura_inicial` ni existe `py.schedule`.

- [ ] **Paso 3: Portar las series a Python**

En `public/engine/audit_engine.py`, insertar antes de `def calculate(payload):`:

```python
MAX_PERIODS = 600

def _quantize(n, precision):
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
    return _quantize(n, rule['precision'])

def _series_order(d):
    return d['series'].get('order', ['backward', 'forward'])

def _series_keys(d):
    listas = {'backward': d['series'].get('backward', []), 'forward': d['series'].get('forward', [])}
    return [x['key'] for p in _series_order(d) for x in listas[p]]

def run_series(d, row, values):
    n = int(values[d['series']['count']])
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
                        sd = semillas.get(k)
                        if sd is None: return Decimal(0)
                        return Decimal(sd[1:]) if sd[0] == '#' else propio.get(sd, values.get(sd, Decimal(0)))
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
```

Y dentro de `calculate`, justo después de construir `values` y antes del bloque `if d['id'] == 'pce'`:

```python
            if 'series' in d:
                filas, agregados = run_series(d, row, values)
                schedule.extend(filas)
                values.update(agregados)
                for k, v in agregados.items():
                    out[k] = format(_quantize(v, 2), 'f')
```

Declarar `schedule = []` junto a `result = []`, y devolver `{'engine': VERSION, 'rows': result, 'schedule': schedule}`.

- [ ] **Paso 4: Correr y ver que pasa**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/series-cross.test.mjs
```

Esperado: `# pass 2  # fail 0`. Si la segunda prueba falla por un dígito, el culpable casi siempre es `_quantize`: JavaScript redondea a 6 decimales y **después** a la precisión de la regla; Python tiene que hacer exactamente lo mismo, en ese orden.

- [ ] **Paso 5: Regenerar el portátil y correr todas las pruebas**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && npm run engine:export && node --test tests/tools/ tests/console/ 2>&1 | tail -8
```

Esperado: `# fail 0`

- [ ] **Paso 6: Commit**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && git add public/engine/audit_engine.py tests/tools/series-cross.test.mjs lib/tools/portable-engine.mjs && git commit -q -m "feat: series por periodos en el motor Python, contrastadas contra el servidor"
```

---

## Task 3 · D2: contraste simétrico

Hoy `app/api/tools/route.ts` compara solo `rows`, y solo las claves del servidor. `totals` y `exceptions` —que sostienen la sumaria del Excel y el bloqueo de aprobación— nunca se contrastan.

**Decisión de alcance:** Python calcula `totals` y los **códigos e importes** de las excepciones, no sus mensajes. Los mensajes son texto en español del servidor; duplicarlos en Python sería duplicar literales sin ganar control.

**Archivos:**
- Modificar: `public/engine/audit_engine.py`
- Modificar: `app/api/tools/route.ts:69-71`
- Modificar: `tests/tools/integration.test.mjs`

- [ ] **Paso 1: Escribir la prueba que falla**

En `tests/tools/integration.test.mjs`, después de la línea 36 (la que muta `impairment` y espera un 400), añadir:

```js
 assert.ok((await action('execute',{python:{...computed,totals:{...computed.totals,impairment:'999.00'}}})).status>=400,'un total alterado debe rechazarse');
 assert.ok((await action('execute',{python:{...computed,rows:computed.rows.map(r=>({...r,clave_inventada:'1'}))}})).status>=400,'una clave extra de Python debe rechazarse');
```

- [ ] **Paso 2: Correr y ver que falla**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/integration.test.mjs
```

Esperado: FAIL en ambas aserciones — hoy el servidor acepta un total alterado y una clave extra.

- [ ] **Paso 3: Que Python devuelva totales y códigos de excepción**

En `public/engine/audit_engine.py`, dentro de `calculate`, acumular mientras se recorren las reglas:

```python
    totals = {}
    ...
                if r['precision'] == 2:
                    totals[r['key']] = totals.get(r['key'], Decimal(0)) + values[r['key']]
```

Y tras el bucle de filas, sumar el campo de conciliación y devolver:

```python
    if any(f['key'] == d['control'] for f in d['fields']):
        for row in rows:
            totals[d['control']] = totals.get(d['control'], Decimal(0)) + Decimal(str(row[d['control']]))
    return {'engine': VERSION, 'rows': result, 'schedule': schedule,
            'totals': {k: format(_quantize(v, 2), 'f') for k, v in totals.items()}}
```

- [ ] **Paso 4: Comparar la unión de claves y los totales en el servidor**

En `app/api/tools/route.ts`, sustituir el bloque de comparación de las líneas 69-71 por:

```ts
 const next=transition(t,action,a.role);const run=calculate(t.definition,t.rows,t.parameters);
 const desigual=(a:any,b:any)=>{const claves=new Set([...Object.keys(a||{}),...Object.keys(b||{})]);return [...claves].some(k=>String(a?.[k])!==String(b?.[k]));};
 if(!b.python||b.python.engine!==run.engine||b.python.rows?.length!==run.rows.length
  ||run.rows.some((r:any,i:number)=>desigual(r,b.python.rows[i]))
  ||desigual(run.totals,b.python.totals))
  throw Error('La ejecución Python no coincide con el verificador. No se guardaron resultados.');
```

`desigual` recorre la **unión** de claves, así que una clave extra de Python ya no pasa inadvertida.

- [ ] **Paso 5: Correr y ver que pasa**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/integration.test.mjs
```

Esperado: `# fail 0`

- [ ] **Paso 6: Commit**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && git add public/engine/audit_engine.py app/api/tools/route.ts tests/tools/integration.test.mjs && git commit -q -m "fix(D2): el contraste recorre la union de claves e incluye los totales"
```

---

## Task 4 · D3: cédula propia del cuadro

`run.schedule` se calcula, se guarda y no lo lee nadie.

**Archivos:**
- Modificar: `lib/tools/domain.mjs` (constante `SHEETS`)
- Modificar: `lib/tools/workbook-presentation.mjs` (`labels`)
- Modificar: `lib/tools/exports.mjs` (`workbookSheets`)
- Crear: `tests/tools/schedule-sheet.test.mjs`

- [ ] **Paso 1: Escribir la prueba que falla**

Crear `tests/tools/schedule-sheet.test.mjs`:

```js
import test from 'node:test';import assert from 'node:assert/strict';
import {catalog,calculate} from '../../lib/tools/domain.mjs';
import {workbookSheets,sheetNames} from '../../lib/tools/exports.mjs';

const base={version:1,country:'Ecuador',engagement:{client:'X',cutoff:'2025-12-31',year:'2025'},
 parameters:{},reconciliation:{ledger:'0',tolerance:'0',difference:'0',within:true,acceptance:''},
 program:[],sources:[],events:[],notes:[],rows:[]};

test('una herramienta sin serie no lleva cedula de cuadro', () => {
  assert.ok(!sheetNames(catalog.vnr).includes('13_Cuadro'));
});

test('una herramienta con serie lleva la cedula y una fila por periodo', () => {
  const definition={...catalog.vnr,sheets:['02_Programa','13_Cuadro'],
    series:{count:'quantity',forward:[{key:'unidad',label:'Unidad',op:'add',a:'periodo',b:'#0',precision:2}]}};
  const nombres=sheetNames(definition);
  assert.ok(nombres.includes('13_Cuadro'));
  const t={...base,definition,rows:[{id:'A',description:'x',quantity:'3',unit_cost:'1',selling_price:'2',
    completion_cost:'0',selling_cost:'0',recorded_allowance:'0'}]};
  t.run=calculate(definition,t.rows);
  const hojas=workbookSheets(t);
  const cuadro=hojas[nombres.indexOf('13_Cuadro')];
  assert.equal(cuadro.length-4,3,'tres periodos mas las cuatro filas de encabezado');
});
```

- [ ] **Paso 2: Correr y ver que falla**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/schedule-sheet.test.mjs
```

Esperado: FAIL — `13_Cuadro` no existe en `SHEETS`.

- [ ] **Paso 3: Declarar la cédula**

En `lib/tools/domain.mjs`, añadir `'13_Cuadro'` al final del arreglo `SHEETS`.

En `lib/tools/workbook-presentation.mjs`, añadir `'Cuadro de períodos'` al final de `labels`.

En `lib/tools/exports.mjs`, dentro de `workbookSheets`, después del bloque que arma `s[11]`:

```js
 s[12]=intro('Cuadro de períodos',['Identificador','Período','De','Cálculo','Valor']);
 for(const fila of t.run?.schedule||[]){
  for(const [clave,valor] of Object.entries(fila)){
   if(['id','periodo','periodos'].includes(clave))continue;
   s[12].push([fila.id||'',numeric(fila.periodo),numeric(fila.periodos),clave,numeric(valor)]);
  }
 }
```

En `sheetPlan`, la cédula solo entra cuando la definición la declara o cuando hay serie. Cambiar el valor por defecto:

```js
 if(!pick)return SHEETS.map((_,i)=>i).filter(i=>SHEETS[i]!=='13_Cuadro'||!!d?.series);
```

- [ ] **Paso 4: Correr y ver que pasa**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/schedule-sheet.test.mjs tests/tools/exports.test.mjs
```

Esperado: `# fail 0`

- [ ] **Paso 5: Comprobar que Excel abre el libro**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node verif-niif16.mjs | tail -3 && node lib/tools/exports.mjs
```

Esperado: `TODAS LAS COMPROBACIONES PASARON` y `tools/exports.mjs: todas las comprobaciones pasaron`

- [ ] **Paso 6: Commit**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && git add lib/tools/domain.mjs lib/tools/workbook-presentation.mjs lib/tools/exports.mjs tests/tools/schedule-sheet.test.mjs lib/tools/portable-engine.mjs && git commit -q -m "feat(D3): cedula 13_Cuadro alimentada desde run.schedule"
```

---

## Task 5a: Población de flujos con fechas — modelo y validación

Un arrendamiento real tiene rentas escalonadas y meses de gracia: no es una anualidad. La definición declara una **segunda población** con el calendario de pagos.

**Archivos:**
- Modificar: `lib/tools/domain.mjs`
- Crear: `tests/tools/flows.test.mjs`

- [ ] **Paso 1: Escribir la prueba que falla**

Crear `tests/tools/flows.test.mjs`:

```js
import test from 'node:test';import assert from 'node:assert/strict';
import {validateDefinition,validateFlows} from '../../lib/tools/domain.mjs';

const base={id:'custom',name:'Arrendamiento',area:'Arrendamientos',
 fields:[{key:'id',label:'Contrato',type:'text'},{key:'tasa',label:'Tasa',type:'number'}],
 rules:[{key:'vp',label:'Valor presente',op:'add',a:'flujos_vp',b:'#0',precision:2}],
 control:'tasa',primary:'vp'};

test('una definicion con flujos declara la fecha de medicion y la tasa', () => {
  const d=validateDefinition({...base,flows:{date:'inicio',rate:'tasa'}});
  assert.equal(d.flows.rate,'tasa');
});

test('rechaza una tasa que no es un campo numerico', () => {
  assert.throws(()=>validateDefinition({...base,flows:{date:'inicio',rate:'inexistente'}}),/tasa/i);
});

test('rechaza una fecha invalida en la poblacion de flujos', () => {
  assert.throws(()=>validateFlows([{id:'L-1',fecha:'2025-13-45',importe:'100'}]),/fecha/i);
});

test('rechaza un flujo sin contrato que lo ampare', () => {
  assert.throws(()=>validateFlows([{id:'',fecha:'2025-01-31',importe:'100'}]),/contrato|identificador/i);
});
```

- [ ] **Paso 2: Correr y ver que falla**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/flows.test.mjs
```

Esperado: FAIL — `validateFlows is not exported`

- [ ] **Paso 3: Implementar el modelo**

En `lib/tools/domain.mjs`, añadir antes de `validateDefinition`:

```js
export const MAX_FLOWS=20000;
/** Calendario de pagos del cliente: una fila por contrato y fecha. */
export function validateFlows(flows){
 if(!Array.isArray(flows)||!flows.length||flows.length>MAX_FLOWS)throw Error(`Cargue entre 1 y ${MAX_FLOWS} flujos.`);
 for(const x of flows){
  if(!String(x?.id??'').trim())throw Error('Cada flujo debe indicar el identificador del contrato.');
  if(!validDate(x?.fecha))throw Error(`Fecha inválida en el flujo de ${x.id}: use AAAA-MM-DD.`);
  decimal(String(x?.importe??''));
 }
 return flows;
}
```

Y dentro de `validateDefinition`, junto a la validación de `series`:

```js
 if(d.flows!==undefined){
  const fl=d.flows;
  if(!fl||typeof fl!=='object')throw Error('La declaración de flujos debe ser un objeto.');
  if(!d.fields.some(f=>f.key===fl.rate&&f.type==='number'))throw Error('La tasa de descuento de los flujos debe ser un campo numérico del contrato.');
  if(!d.fields.some(f=>f.key===fl.date&&f.type==='date')&&fl.date!==undefined)throw Error('La fecha de medición debe ser un campo de fecha del contrato.');
  for(const suf of ['_vp','_total','_dias']){keys.add('flujos'+suf);numeric.add('flujos'+suf);}
 }
```

- [ ] **Paso 4: Correr y ver que pasa**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/flows.test.mjs
```

Esperado: `# pass 4  # fail 0`

- [ ] **Paso 5: Commit**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && git add lib/tools/domain.mjs tests/tools/flows.test.mjs && git commit -q -m "feat: modelo y validacion de la poblacion de flujos con fechas"
```

---

## Task 5b: Descuento por días reales

**Convención única y explícita: `actual/365`.** Es la regla del punto 5 de la spec.

**Archivos:**
- Modificar: `lib/tools/domain.mjs`
- Modificar: `public/engine/audit_engine.py`
- Modificar: `tests/tools/flows.test.mjs`

- [ ] **Paso 1: Escribir la prueba con el caso de referencia**

Añadir a `tests/tools/flows.test.mjs`:

```js
import {calculate} from '../../lib/tools/domain.mjs';

// NIIF 16.27: rentas escalonadas con un mes de gracia. Valor presente calculado
// aparte con actual/365: suma de importe / (1+i)^(dias/365).
test('descuenta por dias reales, no por periodos enteros', () => {
  const d={...base,flows:{date:'inicio',rate:'tasa'},
    fields:[{key:'id',label:'Contrato',type:'text'},{key:'tasa',label:'Tasa',type:'number'},
            {key:'inicio',label:'Fecha de medicion',type:'date'}]};
  const rows=[{id:'L-1',tasa:'0.06',inicio:'2025-01-01'}];
  const flows=[{id:'L-1',fecha:'2025-04-01',importe:'5000'},
               {id:'L-1',fecha:'2025-07-01',importe:'5000'},
               {id:'L-1',fecha:'2026-01-01',importe:'8000'}];
  const esperado=[[90,5000],[181,5000],[365,8000]]
    .reduce((t,[dias,imp])=>t+imp/Math.pow(1.06,dias/365),0);
  const out=calculate(d,rows,{},flows);
  assert.ok(Math.abs(Number(out.rows[0].vp)-esperado)<=0.02,
    `vp ${out.rows[0].vp} vs ${esperado.toFixed(2)}`);
});
```

- [ ] **Paso 2: Correr y ver que falla**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/flows.test.mjs
```

Esperado: FAIL — `calculate` ignora el cuarto argumento y `flujos_vp` no existe.

- [ ] **Paso 3: Implementar el descuento**

El descuento por días exige una potencia fraccionaria, que con BigInt no es directa. Se resuelve con la **misma recurrencia del resto del motor**: el factor de un flujo es `(1+i)^(dias/365)`, y se calcula como `exp((dias/365)·ln(1+i))` mediante series de Taylor sobre enteros escalados, con número fijo de términos para que los tres motores coincidan.

En `lib/tools/domain.mjs`:

```js
const LN_TERMS=40,EXP_TERMS=40;
/** ln(x) para x>0, en escala 1e6, por serie de atanh con termino fijo. */
function lnScaled(x){
 const z=rounded((x-SCALE)*SCALE,x+SCALE);let term=z,sum=z;
 for(let k=1;k<LN_TERMS;k++){term=rounded(rounded(term*z,SCALE)*z,SCALE);sum+=rounded(term*SCALE,BigInt(2*k+1)*SCALE);}
 return 2n*sum;
}
/** exp(x) en escala 1e6, serie de Taylor con termino fijo. */
function expScaled(x){
 let term=SCALE,sum=SCALE;
 for(let k=1;k<EXP_TERMS;k++){term=rounded(rounded(term*x,SCALE)*SCALE,BigInt(k)*SCALE);sum+=term;}
 return sum;
}
/** Valor presente de un calendario de pagos, convencion actual/365. */
export function presentValue(flows,rate,onDate){
 const i=SCALE+rate;const lnI=lnScaled(i);let total=0n,dias=0n;
 for(const f of flows){
  const d=BigInt(Math.round((Date.parse(f.fecha)-Date.parse(onDate))/86400000));
  dias+=d;
  const exponente=rounded(d*SCALE*SCALE,365n*SCALE);
  const factor=expScaled(rounded(exponente*lnI,SCALE));
  total+=rounded(decimal(String(f.importe))*SCALE,factor);
 }
 return {vp:total,dias};
}
```

Y en `calculate(d,rows,p={},flows=[])`, antes de las reglas del contrato:

```js
 if(d.flows){
  const propios=flows.filter(f=>String(f.id)===String(row.id));
  if(!propios.length)throw Error(`El contrato ${row.id} no tiene flujos cargados.`);
  const {vp,dias}=presentValue(propios,values[d.flows.rate],row[d.flows.date]);
  values.flujos_vp=vp;values.flujos_total=propios.reduce((t,f)=>t+decimal(String(f.importe)),0n);
  values.flujos_dias=dias*SCALE/BigInt(propios.length);
  r.flujos_vp=formatted(vp,2);r.flujos_total=formatted(values.flujos_total,2);
 }
```

- [ ] **Paso 4: Correr y ver que pasa**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/flows.test.mjs
```

Esperado: `# fail 0`. Si el valor se desvía más de dos centavos, subir `LN_TERMS` y `EXP_TERMS` **en los tres motores a la vez**: son parte del contrato de determinismo.

- [ ] **Paso 5: Espejar en Python**

En `public/engine/audit_engine.py`, con `Decimal` la potencia fraccionaria es directa y no hace falta la serie, **pero el resultado tiene que coincidir con el de JavaScript**. Implementar la misma serie de Taylor con los mismos términos:

```python
LN_TERMS, EXP_TERMS = 40, 40

def _ln(x):
    z = (x - 1) / (x + 1)
    term, total = z, z
    for k in range(1, LN_TERMS):
        term = term * z * z
        total += term / (2 * k + 1)
    return 2 * total

def _exp(x):
    term, total = Decimal(1), Decimal(1)
    for k in range(1, EXP_TERMS):
        term = term * x / k
        total += term
    return total

def present_value(flows, rate, on_date):
    ln_i = _ln(Decimal(1) + rate)
    total, dias = Decimal(0), 0
    base = date.fromisoformat(on_date)
    for f in flows:
        d = (date.fromisoformat(f['fecha']) - base).days
        dias += d
        total += Decimal(str(f['importe'])) / _exp(Decimal(d) / Decimal(365) * ln_i)
    return total, dias
```

- [ ] **Paso 6: Contrastar los dos motores sobre el mismo calendario**

Añadir a `tests/tools/series-cross.test.mjs`:

```js
test('el calendario de pagos da el mismo valor presente en los dos motores', () => {
  const d={id:'custom',name:'Arrendamiento',area:'Arrendamientos',flows:{date:'inicio',rate:'tasa'},
   fields:[f('id','Contrato','text'),f('tasa','Tasa'),{key:'inicio',label:'Medicion',type:'date'}],
   rules:[r('vp','Valor presente','add','flujos_vp','#0')],control:'tasa',primary:'vp'};
  const rows=[{id:'L-1',tasa:'0.06',inicio:'2025-01-01'}];
  const flows=[{id:'L-1',fecha:'2025-04-01',importe:'5000'},
               {id:'L-1',fecha:'2026-01-01',importe:'8000'}];
  const js=calculate(d,rows,{},flows);
  const py=python({definition:d,rows,parameters:{},flows});
  assert.deepEqual(py.rows,js.rows);
});
```

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/series-cross.test.mjs
```

Esperado: `# fail 0`

- [ ] **Paso 7: Regenerar el portátil y commit**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && npm run engine:export && node --test tests/tools/ 2>&1 | tail -6 && git add -A && git commit -q -m "feat: descuento por dias reales con convencion actual/365 en los tres motores"
```

---

## Task 5c: El calendario llega desde la pantalla

**Archivos:**
- Modificar: `app/api/tools/route.ts`
- Modificar: `lib/tools/python-client.ts`
- Modificar: `app/herramientas/tool-studio.tsx`

- [ ] **Paso 1: Escribir la prueba de integración que falla**

En `tests/tools/integration.test.mjs`, añadir un caso que cree una herramienta con `flows` declarados, suba el calendario en el `map_validate` y ejecute:

```js
 const conFlujos=good(await call('tools','POST',{engagementId,kind:'custom',country:'Ecuador',
   definition:{name:'Arrendamiento',area:'Arrendamientos',flows:{date:'inicio',rate:'tasa'},
     fields:[{key:'id',label:'Contrato',type:'text'},{key:'tasa',label:'Tasa',type:'number'},{key:'inicio',label:'Medicion',type:'date'}],
     rules:[{key:'vp',label:'Valor presente',op:'add',a:'flujos_vp',b:'#0',precision:2}],
     control:'tasa',primary:'vp'}}));
 assert.ok(conFlujos.id);
```

- [ ] **Paso 2: Correr y ver que falla**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/integration.test.mjs
```

Esperado: FAIL — el esquema de la ruta rechaza `flows`.

- [ ] **Paso 3: Aceptar el calendario en la API**

En `app/api/tools/route.ts`, añadir `validateFlows` al import desde `@/lib/tools/domain.mjs` y, dentro de la rama `map_validate`, tras guardar las filas:

```ts
 if(t.definition.flows)t.flows=validateFlows(b.flows||[]);
```

En la rama `execute`, cambiar la llamada al motor:

```ts
 const run=calculate(t.definition,t.rows,t.parameters,t.flows||[]);
```

En `lib/tools/python-client.ts` **no hay que tocar nada**: `executePython(payload)` reenvía el objeto tal cual. El cambio va en quien lo llama, `app/herramientas/tool-studio.tsx`, en `execute()`:

```ts
 const python=await executePython({definition:tool!.definition,rows:tool!.rows,parameters:tool!.parameters,flows:tool!.flows||[]});
```

Y en `public/engine/audit_engine.py`, que `calculate` lea el calendario y lo pase al descuento:

```python
    flows = payload.get('flows', [])
    ...
            if 'flows' in d:
                propios = [x for x in flows if str(x['id']) == str(row.get('id'))]
                if not propios:
                    raise ValueError('El contrato ' + str(row.get('id')) + ' no tiene flujos cargados.')
                vp, dias = present_value(propios, values[d['flows']['rate']], row[d['flows']['date']])
                values['flujos_vp'] = vp
                out['flujos_vp'] = format(_quantize(vp, 2), 'f')
```

- [ ] **Paso 4: Correr toda la batería**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/ 2>&1 | tail -8 && npx tsc --noEmit -p tsconfig.json && echo "tsc limpio"
```

Esperado: `# fail 0` y `tsc limpio`

- [ ] **Paso 5: Compilar y verificar en el navegador**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && rm -rf dist && npm run build 2>&1 | grep -iE "error|Build complete"
```

Esperado: `Build complete`

- [ ] **Paso 6: Commit y sincronizar con el checkout de Codex**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && git add -A && git commit -q -m "feat: el calendario de pagos viaja de la pantalla al motor"
```

Copiar los archivos cambiados a `C:\Users\jcalu\Documents\Codex\2026-09-17\sites-x20` y comprobar con `diff -rq` que no queda diferencia, según el procedimiento de `PENDIENTES_CODEX.md`.

---

## Task 6: Guardarraíl — el cuadro tiene que cerrar

La spec (§7) lo exige porque **la definición la escribe el auditor**: una serie mal planteada produce números con apariencia correcta. El motor debe avisar por su cuenta, sin que nadie se acuerde de mirarlo.

**Archivos:**
- Modificar: `lib/tools/domain.mjs`
- Crear: `tests/tools/guardarrail.test.mjs`

- [ ] **Paso 1: Escribir la prueba que falla**

Crear `tests/tools/guardarrail.test.mjs`:

```js
import test from 'node:test';import assert from 'node:assert/strict';
import {calculate} from '../../lib/tools/domain.mjs';

const f=(k,l,t='number')=>({key:k,label:l,type:t});
const r=(key,label,op,a,b,precision=2)=>({key,label,op,a,b,precision});
// Serie deliberadamente mal planteada: la apertura nunca se descuenta, asi que
// el cierre no llega a cero. Es el error tipico de quien no entiende la recurrencia.
const torcida={id:'custom',name:'Serie torcida',area:'Pruebas',
 fields:[f('id','Contrato','text'),f('pago','Pago'),f('n','Periodos')],
 series:{count:'n',forward:[
  {...r('apertura','Apertura','add','@apertura','pago',6),seed:'pago'},
  r('cierre','Cierre','add','apertura','#0',2)]},
 rules:[r('total','Total','add','apertura_final','#0')],control:'pago',primary:'total'};

test('una serie cuyo cierre no llega a cero levanta una excepcion del papel', () => {
  const out=calculate(torcida,[{id:'L-1',pago:'100',n:'3'}]);
  const aviso=out.exceptions.find(x=>x.code==='SERIES_NO_CIERRA');
  assert.ok(aviso,'debe avisar que el cuadro no cierra: '+JSON.stringify(out.exceptions));
  assert.match(aviso.message,/no cierra|revise la recurrencia/i);
});
```

- [ ] **Paso 2: Correr y ver que falla**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/guardarrail.test.mjs
```

Esperado: FAIL — no existe el código `SERIES_NO_CIERRA`.

- [ ] **Paso 3: Emitir la excepción**

En `lib/tools/domain.mjs`, dentro de `calculate`, en el bloque que ya llama a `runSeries`:

```js
  const ultimo=filas.at(-1);
  // Convencion barata que atrapa la recurrencia mal armada: si la serie declara
  // una clave `cierre`, su ultimo periodo deberia extinguirse.
  if(ultimo&&ultimo.cierre!==undefined&&decimal(ultimo.cierre)!==0n)
   exceptions.push({row:row._row||i+2,id:row.id,code:'SERIES_NO_CIERRA',
    message:'El cuadro no cierra en cero en el último período: revise la recurrencia y la semilla.',
    amount:ultimo.cierre});
```

- [ ] **Paso 4: Correr y ver que pasa**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && node --test tests/tools/guardarrail.test.mjs tests/tools/series-cross.test.mjs
```

Esperado: `# fail 0`. La serie correcta de NIIF 16 **no** debe levantar la excepción — si la levanta, el umbral está mal puesto.

- [ ] **Paso 5: Commit**

```bash
cd "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/auditbrain-site" && git add lib/tools/domain.mjs tests/tools/guardarrail.test.mjs && git commit -q -m "feat: el motor avisa cuando un cuadro de amortizacion no cierra en cero"
```

**Nota de alcance:** la vista previa obligatoria del Diseñador, que la spec §7 también pide, es trabajo de pantalla y va con el rediseño del Diseñador, en la fase 2. Lo que puede hacer el motor solo —la comprobación de cierre y el rechazo de colisiones de nombres— queda cubierto aquí.

---

## Cierre de la fase

- [ ] Registrar la fase como entrada nueva en `docs/pruebas/PENDIENTES_CODEX.md`, esperando publicación.
- [ ] Publicar con `codex exec`, **avisando que no hay migraciones nuevas** (esta fase no toca `db/schema.ts` ni `drizzle/`).
- [ ] Verificar que la URL responde `HTTP 401` y, con la sesión de ChatGPT, que una herramienta con serie **ejecuta** sin el error de contraste.
