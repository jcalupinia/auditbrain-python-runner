export const ENGINE_VERSION='3.0.0';
export const MAX_ROWS=100000;
const f=(key,label,type='number',positive=false)=>({key,label,type,required:true,positive});
const rule=(key,label,op,a,b,precision=2)=>({key,label,op,a,b,precision});
const IAS2={organization:'IFRS Foundation',document:'IAS 2 Inventories',url:'https://www.ifrs.org/content/dam/ifrs/publications/html-standards/english/2024/issued/ias2.html',type:'Norma contable',date:'2026-09-19'};
const IFRS9={organization:'IFRS Foundation',document:'IFRS 9 Financial Instruments',url:'https://www.ifrs.org/content/dam/ifrs/publications/html-standards/english/2024/issued/ifrs9.html',type:'Norma contable',date:'2026-09-19'};
export const catalog={
 vnr:{id:'vnr',name:'Valor neto de realización',area:'Inventarios',description:'Compara el costo con el precio estimado de venta menos los costos de terminación y venta, por partida.',source:IAS2,fields:[f('id','Código / lote','text'),f('description','Descripción','text'),f('quantity','Cantidad','number',true),f('unit_cost','Costo unitario'),f('selling_price','Precio de venta unitario'),f('completion_cost','Costo de terminación unitario'),f('selling_cost','Costo necesario de venta unitario'),f('recorded_allowance','Deterioro registrado total')],rules:[rule('net_price','Precio menos terminación','subtract','selling_price','completion_cost',6),rule('nrv_unit','VNR unitario','subtract','net_price','selling_cost',6),rule('nrv_floor','VNR recuperable (mínimo cero)','max','nrv_unit','#0',6),rule('carrying_unit','Menor entre costo y VNR','min','unit_cost','nrv_floor',6),rule('cost','Costo total','multiply','quantity','unit_cost'),rule('recoverable','Valor recuperable total','multiply','quantity','carrying_unit'),rule('impairment','Deterioro requerido','subtract','cost','recoverable'),rule('adjustment','Ajuste frente a deterioro registrado','subtract','impairment','recorded_allowance')],control:'cost',primary:'impairment'},
 pce:{id:'pce',name:'Pérdidas crediticias esperadas',area:'Cuentas por cobrar',description:'Matriz de provisión con tasas y rangos de mora aprobados. Los cobros posteriores se muestran como evidencia, sin descontarlos automáticamente.',source:IFRS9,fields:[f('id','Documento / cliente','text'),f('due_date','Fecha de vencimiento','date'),f('exposure','Exposición al corte'),f('recorded_allowance','Provisión registrada'),f('subsequent_collection','Cobros posteriores (evidencia)')],rules:[rule('impairment','Pérdida estimada','multiply','exposure','rate'),rule('adjustment','Ajuste frente a provisión registrada','subtract','impairment','recorded_allowance')],control:'exposure',primary:'impairment'}
};
// Cedulas posibles de un papel de trabajo. Una herramienta declara en
// `definition.sheets` cuales lleva; sin declararlas, lleva las doce primeras.
// La trece, el cuadro de periodos, solo existe si la herramienta tiene serie.
export const SHEETS=['01_Caratula','02_Programa','03_Parametros','04_Fuentes','05_Data_Original','06_Data_Procesada','07_Calculos','08_Pruebas','09_Excepciones','10_Sumaria','11_Conclusion','12_Control_Revision','13_Cuadro'];
// Series por periodos. Un contrato produce n filas de cuadro.
//
// No hace falta un operador de potencia: un valor presente es una recurrencia.
// Descontando hacia atras desde el ultimo periodo, saldo(t-1)=(saldo(t)+pago)/(1+i)
// llega al valor presente en un solo pase, y de camino deja el cuadro armado.
//
// Dos operandos nuevos, y solo dos:
//   @clave  el valor de esa clave en el periodo ANTERIOR del mismo pase (0 en el borde)
//   ^clave  el valor de esa clave en el PRIMER periodo (t=1)
// Mas dos valores automaticos en cada fila: `periodo` (t) y `periodos` (n).
export const MAX_PERIODS=600;
export const SERIES_OPS=['add','subtract','multiply','divide','min','max'];
export function validateSeriesRule(x,disponibles,vistas,delPase){
 if(!/^[a-z][a-z0-9_]{0,35}$/.test(x.key)||disponibles.has(x.key)||vistas.has(x.key)||['constructor','prototype','__proto__'].includes(x.key))throw Error('Cálculo de serie inválido o código repetido: '+x.key);
 if(!SERIES_OPS.includes(x.op)||![2,6].includes(x.precision))throw Error('Operación o decimales no admitidos en la serie: '+x.key);
 for(const a of [x.a,x.b]){
  if(typeof a!=='string')throw Error('Operando inválido en la serie: '+x.key);
  if(/^#-?\d{1,12}(\.\d{1,6})?$/.test(a))continue;
  const base=a[0]==='@'||a[0]==='^'?a.slice(1):a;
  if(!base)throw Error('Operando vacío en la serie: '+x.key);
  if(a[0]==='@'){if(!delPase.has(base))throw Error(`@${base} debe ser un cálculo del mismo pase de la serie.`);continue;}
  if(!disponibles.has(base)&&!vistas.has(base))throw Error(`Operando no disponible en la serie: ${a} (en ${x.key}).`);
 }
 if(x.seed!==undefined){
  const sd=x.seed;
  if(typeof sd!=='string'||sd[0]==='@'||sd[0]==='^')throw Error('La semilla debe ser un campo, un cálculo anterior o una constante: '+x.key);
  if(!/^#-?\d{1,12}(\.\d{1,6})?$/.test(sd)&&!disponibles.has(sd)&&!vistas.has(sd))throw Error('Semilla no disponible: '+sd+' (en '+x.key+').');
 }
}
export function seriesOrder(d){
 const o=d.series?.order;
 if(o===undefined)return ['backward','forward'];
 if(!Array.isArray(o)||!o.length||o.length>2||new Set(o).size!==o.length||o.some(x=>!['backward','forward'].includes(x)))throw Error("El orden de la serie debe ser backward y forward, sin repetir.");
 return o;
}
export const seriesKeys=d=>{const l={backward:d.series?.backward||[],forward:d.series?.forward||[]};return seriesOrder(d).flatMap(p=>l[p]).map(x=>x.key);};
export function validateSeries(d){
 const s=d.series;
 if(!s||typeof s!=='object')throw Error('La serie debe ser un objeto con períodos y cálculos.');
 if(!d.fields.some(f=>f.key===s.count&&f.type==='number'))throw Error('La serie debe declarar en `count` un campo numérico con el número de períodos.');
 const backward=Array.isArray(s.backward)?s.backward:[],forward=Array.isArray(s.forward)?s.forward:[];
 if(!backward.length&&!forward.length)throw Error('Declare al menos un cálculo en la serie.');
 if(backward.length+forward.length>40)throw Error('Máximo 40 cálculos de serie.');
 // Disponibles en cualquier fila de periodo: los campos numericos del contrato,
 // los calculos por fila ya definidos, y los dos automaticos.
 const disponibles=new Set([...d.fields.filter(f=>f.type==='number').map(f=>f.key),'periodo','periodos']);
 const vistas=new Set();
 // El orden de los pases importa: un descuento va hacia atrás, pero un flujo que
 // crece se arma hacia adelante y solo después se descuenta. Por defecto,
 // primero hacia atrás, que es lo que pide un cuadro de amortización.
 const orden=seriesOrder(d);
 const listas={backward,forward},claves={backward:new Set(backward.map(x=>x.key)),forward:new Set(forward.map(x=>x.key))};
 for(const pase of orden)for(const x of listas[pase]){validateSeriesRule(x,disponibles,vistas,claves[pase]);vistas.add(x.key);}
 return d;
}
// Flujos irregulares con fechas. NIIF 16.26 mide el pasivo al valor presente de
// los pagos que no se han pagado a esa fecha, y 16.27 enumera pagos de naturaleza
// distinta: un arrendamiento real tiene rentas escalonadas, meses de gracia y
// pagos anticipados y vencidos mezclados. No es una anualidad. Por eso el
// calendario entra como SEGUNDA poblacion —filas {id,fecha,importe}, `id` el
// contrato al que pertenecen— y no como periodos nivelados.
//
// Convencion, no negociable: actual/365. El factor de un flujo a `d` dias es
// (1+i)^(d/365) y las fechas viajan AAAA-MM-DD.
//
// Aqui no hay potencias fraccionarias: toda la aritmetica es BigInt. Y el motor
// Python tiene que dar EL MISMO DIGITO —el servidor contrasta y rechaza la
// ejecucion si difieren—, asi que el descuento se resuelve con ENTEROS y no con
// Decimal: `int` de Python es identico a BigInt, luego los dos motores corren el
// mismo algoritmo con los mismos terminos.
//
//   (1+i)^(d/365) = (1+i)^q * exp(ln(1+i)*r/365),   con d = 365q + r
//
// La potencia entera se hace multiplicando (q <= 100 por MAX_FLOW_DAYS) y solo la
// fraccion r/365 pasa por series de Taylor de termino fijo, con exponente menor
// que ln(1+i): converge en pocos terminos y nunca diverge, a diferencia de
// exp(ln(1+i)*anios) directo, que con plazos largos se rompe.
//
// La escala 1e6 NO alcanza para los factores. Medido contra Math.log/Math.exp:
// ln(1.06) sale 0.058268 en vez de 0.058268908 y el factor a 90 dias se desvia
// 1.4e-6 —1,1 centavos sobre un solo flujo de 8.000, y suma por flujo—. Los
// factores viven en escala FLOW_SCALE=1e18, donde el error contra el doble de
// JavaScript es cero. El importe se descuenta en escala 1e12 y solo al final baja
// a 1e6, para que la acumulacion del calendario no pierda el centavo.
// ponytail: un factor por flujo, sin cache. Medido: 100.000 flujos —el tope—
// tardan ~4 s en el servidor y ~6 s en Python. Si un encargo real se acerca al
// tope, memorizar el factor por (tasa, dias) antes que bajar MAX_FLOWS.
export const MAX_FLOWS=100000;
export const MAX_FLOW_DAYS=36500;
export const FLOW_SCALE=10n**18n;
export const LN_TERMS=40,EXP_TERMS=40;
export const FLOW_KEYS=['flujos_vp','flujos_total','flujos_dias'];
/** La segunda población: el calendario {id,fecha,importe}. La usan el mapeo del
 * archivo en el servidor y la pantalla, para no describir la misma forma dos veces. */
export const FLOW_FIELDS=[{key:'id',label:'Contrato',type:'text'},{key:'fecha',label:'Fecha del pago',type:'date'},{key:'importe',label:'Importe',type:'number'}];
/** ln(x) en escala FLOW_SCALE, x>0, por serie de atanh con termino fijo. */
export function lnBig(x){
 if(x<=0n)throw Error('La tasa de descuento debe ser mayor que -1.');
 const z=rounded((x-FLOW_SCALE)*FLOW_SCALE,x+FLOW_SCALE);let term=z,sum=z;
 for(let k=1;k<LN_TERMS;k++){term=rounded(term*z*z,FLOW_SCALE*FLOW_SCALE);sum+=rounded(term,BigInt(2*k+1));}
 return 2n*sum;
}
/** exp(x) en escala FLOW_SCALE, serie de Taylor con termino fijo. */
export function expBig(x){
 let term=FLOW_SCALE,sum=FLOW_SCALE;
 for(let k=1;k<EXP_TERMS;k++){term=rounded(term*x,BigInt(k)*FLOW_SCALE);sum+=term;}
 return sum;
}
/** base^(dias/365) en escala FLOW_SCALE. `ln` es lnBig(base), calculado una vez. */
export function powBig(base,dias,ln){
 const q=Math.trunc(dias/365),r=dias%365;let p=FLOW_SCALE;
 for(let k=0;k<q;k++)p=rounded(p*base,FLOW_SCALE);
 return r?rounded(p*expBig(rounded(ln*BigInt(r),365n)),FLOW_SCALE):p;
}
/** Dias calendario entre dos fechas AAAA-MM-DD. El mismo entero que date-date en Python. */
export function flowDays(desde,hasta){return Math.round((Date.parse(hasta)-Date.parse(desde))/86400000);}
export function validateFlows(flows){
 if(!Array.isArray(flows)||!flows.length||flows.length>MAX_FLOWS)throw Error(`Cargue entre 1 y ${MAX_FLOWS} flujos en el calendario de pagos.`);
 for(const x of flows){
  const id=String(x?.id??'').trim();
  if(!id||id.length>1000)throw Error('Cada flujo debe llevar el identificador del contrato al que pertenece.');
  if(!validDate(x?.fecha))throw Error(`Fecha de flujo inválida en ${id}: use una fecha válida AAAA-MM-DD.`);
  decimal(x?.importe);
 }
 return flows;
}
export function validateFlowsBlock(d){
 const s=d.flows;
 if(!s||typeof s!=='object')throw Error('El bloque de flujos debe declarar la fecha de medición y la tasa de descuento.');
 if(!d.fields.some(f=>f.key===s.date&&f.type==='date'))throw Error('Los flujos deben declarar en `date` un campo de tipo fecha con la fecha de medición.');
 if(!d.fields.some(f=>f.key===s.rate&&f.type==='number'))throw Error('Los flujos deben declarar en `rate` un campo numérico con la tasa de descuento.');
 return d;
}
/**
 * Descuenta el calendario de un contrato y devuelve los tres agregados que las
 * reglas del contrato pueden usar: `flujos_vp` (valor presente), `flujos_total`
 * (suma nominal) y `flujos_dias` (plazo promedio en dias, ponderado por importe).
 */
export function runFlows(d,row,values,mios){
 const medicion=String(row[d.flows.date]??'');
 if(!validDate(medicion))throw Error(`Fecha de medición de ${row.id||'la fila'}: use una fecha válida AAAA-MM-DD.`);
 const base=FLOW_SCALE+values[d.flows.rate]*(FLOW_SCALE/SCALE),ln=lnBig(base);
 let alto=0n,total=0n,ponderado=0n;
 for(const x of mios){
  const dias=flowDays(medicion,x.fecha);
  if(dias<0)throw Error(`Flujo del ${x.fecha} en ${x.id}: es anterior a la fecha de medición, que mide solo los pagos no pagados a esa fecha.`);
  if(dias>MAX_FLOW_DAYS)throw Error(`Flujo del ${x.fecha} en ${x.id}: excede los ${MAX_FLOW_DAYS} días admitidos desde la fecha de medición.`);
  const importe=decimal(x.importe);
  alto+=rounded(importe*FLOW_SCALE*SCALE,powBig(base,dias,ln));
  total+=importe;ponderado+=importe*BigInt(dias);
 }
 return {flujos_vp:rounded(alto,SCALE),flujos_total:total,flujos_dias:total===0n?0n:rounded(ponderado*SCALE,total)};
}
export function validateDefinition(d){
 if(!d||typeof d!=='object'||!String(d.name||'').trim()||!String(d.area||'').trim())throw Error('Indique nombre y rubro de la herramienta.');
 if(!Array.isArray(d.fields)||d.fields.length<2||d.fields.length>25||!Array.isArray(d.rules)||!d.rules.length||d.rules.length>25)throw Error('Defina de 2 a 25 campos y de 1 a 25 cálculos.');
 const keys=new Set();for(const x of d.fields){if(!/^[a-z][a-z0-9_]{0,35}$/.test(x.key)||keys.has(x.key)||['constructor','prototype','__proto__'].includes(x.key)||!['number','date','text'].includes(x.type)||!String(x.label||'').trim())throw Error('Campos duplicados o inválidos. Use códigos en minúsculas sin espacios.');keys.add(x.key);}
 if(!d.fields.some(x=>x.key==='id'&&x.type==='text'))throw Error('Incluya un campo de texto con código id para identificar cada registro.');
 if(d.id==='pce'){keys.add('rate');keys.add('days');}
 const numeric=new Set(d.fields.filter(x=>x.type==='number').map(x=>x.key));if(d.id==='pce'){numeric.add('rate');numeric.add('days');}
 // La serie corre antes que las reglas del contrato y publica tres agregados por
 // cálculo: el primer período, el último y la suma. Un solo sentido, sin ciclos.
 if(d.series!==undefined){validateSeries(d);for(const k of seriesKeys(d))for(const suf of ['_inicial','_final','_total']){if(keys.has(k+suf))throw Error('Código reservado por la serie: '+k+suf);keys.add(k+suf);numeric.add(k+suf);}}
 if(d.flows!==undefined){validateFlowsBlock(d);for(const k of FLOW_KEYS){if(keys.has(k))throw Error('Código reservado por los flujos: '+k);keys.add(k);numeric.add(k);}}
 for(const x of d.rules){if(!/^[a-z][a-z0-9_]{0,35}$/.test(x.key)||keys.has(x.key)||['constructor','prototype','__proto__'].includes(x.key)||!['add','subtract','multiply','divide','min','max'].includes(x.op)||![2,6].includes(x.precision))throw Error('Cálculo inválido o código repetido.');for(const a of [x.a,x.b]){if(typeof a!=='string'||!(numeric.has(a)||/^#-?\d{1,12}(\.\d{1,6})?$/.test(a)))throw Error('Cada operando debe ser numérico: campo, cálculo anterior o constante (#0).');}keys.add(x.key);numeric.add(x.key);}
 if((d.id==='custom'&&!d.fields.some(f=>f.key===d.control&&f.type==='number'))||!numeric.has(d.control)||!d.rules.some(x=>x.key===d.primary))throw Error('Seleccione campo de conciliación y resultado principal válidos.');
  if(d.sheets!==undefined&&(!Array.isArray(d.sheets)||!d.sheets.length||d.sheets.some(x=>!SHEETS.includes(x))))throw Error('Las cedulas declaradas deben ser nombres de SHEETS, al menos una.');
 return d;
}
const SCALE=1000000n;
export function decimal(v){const s=String(v??'').trim();if(!/^-?\d{1,12}(\.\d{1,6})?$/.test(s))throw Error('Número inválido: use punto decimal, sin separadores de miles y hasta 6 decimales.');if(s.replace(/[^0-9]/g,'').replace(/^0+/,'').replace(/0+$/,'').length>15)throw Error('Máximo 15 dígitos significativos para compatibilidad con Excel.');const neg=s.startsWith('-');const [a,b='']=s.replace('-','').split('.');return (BigInt(a)*SCALE+BigInt(b.padEnd(6,'0')))*(neg?-1n:1n);}
export const rounded=(n,d)=>{if(d===0n)throw Error('División por cero.');let neg=(n<0n)!==(d<0n);n=n<0n?-n:n;d=d<0n?-d:d;return ((n+d/2n)/d)*(neg?-1n:1n);};
export function formatted(n,p=2){const q=10n**BigInt(6-p);const v=rounded(n,q);const abs=v<0n?-v:v;return `${v<0n?'-':''}${abs/(10n**BigInt(p))}.${String(abs%(10n**BigInt(p))).padStart(p,'0')}`;}
export const amount=(v)=>formatted(decimal(v));
export function validDate(v){return /^\d{4}-\d{2}-\d{2}$/.test(String(v))&&!isNaN(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;}
export function validateRows(d,rows){
 validateDefinition(d);if(!Array.isArray(rows)||rows.length===0||rows.length>MAX_ROWS)throw Error(`Cargue entre 1 y ${MAX_ROWS} registros.`);
 const errors=[],warnings=[],seen=new Map(),ids=new Set();
 rows.forEach((r,i)=>{const row=r._row||i+2;const signature=JSON.stringify(d.fields.map(f=>String(r[f.key]??'').trim()));if(seen.has(signature))errors.push({row,code:'DUPLICATE',message:`Duplicado exacto de fila ${seen.get(signature)}. No se eliminó.`});else seen.set(signature,row);
 if(ids.has(String(r.id)))warnings.push({row,code:'REPEATED_ID',message:'Identificador repetido: compruebe lotes o partidas.'});ids.add(String(r.id));
 for(const field of d.fields){const v=String(r[field.key]??'').trim();if(v==='FORMULA_SIN_VALOR_GUARDADO'||v.startsWith('ERROR_EXCEL:')){errors.push({row,field:field.key,code:'CELL_ERROR',message:'Corrija el error o recalcule y guarde el Excel de origen.'});continue;}if(!v){errors.push({row,field:field.key,code:'REQUIRED',message:`Falta ${field.label}.`});continue;}if(v.length>1000){errors.push({row,field:field.key,code:'LENGTH',message:'Texto demasiado largo.'});continue;}if(field.type==='number'){try{const n=decimal(v);if(n<0n||field.positive&&n===0n)errors.push({row,field:field.key,code:'AMOUNT',message:`${field.label}: monto incompatible con el campo.`});}catch{errors.push({row,field:field.key,code:'NUMBER',message:`${field.label}: número inválido.`});}}if(field.type==='date'&&!validDate(v))errors.push({row,field:field.key,code:'DATE',message:`${field.label}: use una fecha válida AAAA-MM-DD.`});}
 if(/^(total|subtotal)(\b|\s)/i.test(String(r.id)))errors.push({row,code:'TOTAL_ROW',message:'Fila de total/subtotal. Prepare un archivo de detalle y conserve el original como evidencia.'});
 });return {records:rows.length,errors,warnings,ok:errors.length===0};
}
export function checkBuckets(p){
 if(!validDate(p.cutoff)||!Array.isArray(p.buckets)||!p.buckets.length||p.buckets.length>30)throw Error('Defina fecha de corte y rangos con tasas aprobadas.');
 let next=0;for(let i=0;i<p.buckets.length;i++){const b=p.buckets[i];if(!Number.isInteger(b.min)||b.min!==next||b.max!==null&&(!Number.isInteger(b.max)||b.max<b.min)||b.max===null&&i!==p.buckets.length-1)throw Error('Los rangos deben cubrir desde cero, sin vacíos ni superposiciones; el último termina sin límite.');const rate=decimal(b.rate);if(rate<0n||rate>SCALE)throw Error('Cada tasa debe estar entre 0 y 1.');next=b.max===null?Infinity:b.max+1;}if(next!==Infinity)throw Error('El último rango debe tener límite superior vacío.');
}
export const OP={add:(a,b)=>a+b,subtract:(a,b)=>a-b,multiply:(a,b)=>rounded(a*b,SCALE),divide:(a,b)=>rounded(a*SCALE,b),min:(a,b)=>a<b?a:b,max:(a,b)=>a>b?a:b};
export function apply(rule,resolve){
 const n=OP[rule.op](resolve(rule.a),resolve(rule.b));
 if(n>999999999999999999n||n< -999999999999999999n)throw Error('Resultado fuera del rango admitido. Divida la población en lotes.');
 return decimal(formatted(n,rule.precision));
}
/**
 * Expande un contrato en sus n filas de período y devuelve, además, los tres
 * agregados por cálculo (primer período, último y suma) para las reglas del
 * contrato. `backward` recorre de n a 1 —así el descuento llega al valor
 * presente— y `forward` de 1 a n sobre esas mismas filas.
 */
export function runSeries(d,row,values){
 const n=Number(formatted(values[d.series.count],2).split('.')[0]);
 if(!Number.isInteger(n)||n<1||n>MAX_PERIODS)throw Error(`Períodos de ${row.id||'la fila'}: indique un entero entre 1 y ${MAX_PERIODS}.`);
 const filas=Array.from({length:n},(_,i)=>({id:row.id,periodo:String(i+1),periodos:String(n)}));
 const celdas=filas.map(()=>Object.create(null));
 filas.forEach((f,i)=>{celdas[i].periodo=decimal(String(i+1));celdas[i].periodos=decimal(String(n));});
 // En el primer período de cada pase no hay anterior. Sin semilla, @clave vale
 // cero —que es lo correcto para una anualidad—; con semilla, arranca en ella,
 // que es lo que exige un flujo único al vencimiento.
 const pase=(lista,orden)=>{
  const semillas=Object.fromEntries(lista.filter(x=>x.seed!==undefined).map(x=>[x.key,x.seed]));
  let anterior=null;
  for(const i of orden){
   const propio=celdas[i];
   for(const rule of lista){
    const resolve=x=>{
     if(x[0]==='#')return decimal(x.slice(1));
     if(x[0]==='@'){
      const k=x.slice(1);
      if(anterior)return anterior[k]??0n;
      const sd=semillas[k];
      return sd===undefined?0n:sd[0]==='#'?decimal(sd.slice(1)):propio[sd]??values[sd]??0n;
     }
     if(x[0]==='^')return celdas[0][x.slice(1)]??propio[x.slice(1)]??0n;
     return propio[x]??values[x];
    };
    const v=apply(rule,resolve);propio[rule.key]=v;filas[i][rule.key]=formatted(v,rule.precision);
   }
   anterior=propio;
  }
 };
 const indices=filas.map((_,i)=>i);
 const listas={backward:d.series.backward||[],forward:d.series.forward||[]};
 for(const nombre of seriesOrder(d))pase(listas[nombre],nombre==='backward'?[...indices].reverse():indices);
 const agregados=Object.create(null);
 for(const k of seriesKeys(d)){
  agregados[k+'_inicial']=celdas[0][k]??0n;
  agregados[k+'_final']=celdas[n-1][k]??0n;
  agregados[k+'_total']=celdas.reduce((t,c)=>t+(c[k]??0n),0n);
 }
 return {filas,agregados};
}
export function calculate(d,rows,p={},flows=[]){
 validateDefinition(d);if(d.id==='pce')checkBuckets(p);if(rows.length){const validation=validateRows(d,rows);if(!validation.ok)throw Error('Resuelva los errores de validación antes de calcular.');}
 // El calendario se agrupa por contrato una sola vez. Un flujo huerfano no se
 // descarta en silencio: perder el calendario de un contrato es perder su pasivo.
 let porContrato=null;
 if(d.flows&&rows.length){validateFlows(flows);porContrato=new Map();
  for(const x of flows){const k=String(x.id).trim();if(!porContrato.has(k))porContrato.set(k,[]);porContrato.get(k).push(x);}
  const ids=new Set(rows.map(r=>String(r.id??'').trim()));
  for(const k of porContrato.keys())if(!ids.has(k))throw Error(`El flujo de ${k} no tiene contrato que lo ampare en la población.`);}
 const totals=Object.create(null),exceptions=[],schedule=[];const output=rows.map((row,i)=>{
 const r={...row};let values=Object.create(null);for(const f of d.fields)if(f.type==='number')values[f.key]=decimal(row[f.key]);
if(d.series){const {filas,agregados}=runSeries(d,row,values);schedule.push(...filas);Object.assign(values,agregados);for(const [k,v] of Object.entries(agregados))r[k]=formatted(v,2);
 // Guardarrail del cuadro: la definición la escribe el auditor y una recurrencia
 // mal armada devuelve números con apariencia correcta. Convención barata y
 // declarativa: si la serie declara una clave `cierre`, su último período
 // debería extinguirse. Se juzga el valor presentado —ya redondeado a la
 // precisión que el propio cálculo declara—, no el residuo interno de 1e-6:
 // esa precisión es la tolerancia que el auditor pidió para su papel.
 const ultimo=filas.at(-1);
 if(ultimo&&ultimo.cierre!==undefined&&decimal(ultimo.cierre)!==0n)
  exceptions.push({row:row._row||i+2,id:row.id,code:'SERIES_NO_CIERRA',
   message:'El cuadro no cierra en cero en el último período: revise la recurrencia y la semilla.',
   amount:ultimo.cierre});}
 if(d.flows){const mios=porContrato.get(String(row.id??'').trim());
  if(!mios||!mios.length)throw Error(`Sin calendario de pagos para ${row.id||'la fila'}: cargue al menos un flujo con ese identificador.`);
  const ag=runFlows(d,row,values,mios);Object.assign(values,ag);for(const [k,v] of Object.entries(ag))r[k]=formatted(v,2);}
 if(d.id==='pce'){r.days=String(Math.max(0,Math.round((Date.parse(p.cutoff)-Date.parse(row.due_date))/86400000)));const b=p.buckets.find(b=>Number(r.days)>=b.min&&(b.max===null||Number(r.days)<=b.max));r.rate=String(b.rate);values.rate=decimal(b.rate);r.bucket=`${b.min}–${b.max??'∞'}`;}
 for(const rule of d.rules){const val=x=>x.startsWith('#')?decimal(x.slice(1)):values[x];const a=val(rule.a),b=val(rule.b);let n;
 switch(rule.op){case'add':n=a+b;break;case'subtract':n=a-b;break;case'multiply':n=rounded(a*b,SCALE);break;case'divide':n=rounded(a*SCALE,b);break;case'min':n=a<b?a:b;break;case'max':n=a>b?a:b;break;}
 if(n>999999999999999999n||n< -999999999999999999n)throw Error('Resultado fuera del rango admitido. Divida la población en lotes.');
 r[rule.key]=formatted(n,rule.precision);values[rule.key]=decimal(r[rule.key]);if(rule.precision===2)totals[rule.key]=(totals[rule.key]||0n)+values[rule.key];}
 if(d.fields.some(f=>f.key===d.control))totals[d.control]=(totals[d.control]||0n)+values[d.control];
 if(d.id==='vnr'&&values.nrv_unit<0n)exceptions.push({row:row._row||i+2,id:row.id,code:'NEGATIVE_NRV',message:'VNR negativo: deterioro limitado al costo; evaluar obligaciones separadas.',amount:r.impairment});
 if(values[d.primary]>0n)exceptions.push({row:row._row||i+2,id:row.id,code:'RESULT',message:`${d.rules.find(x=>x.key===d.primary)?.label}: requiere evaluación.`,amount:r[d.primary]});
 if(values.adjustment<0n)exceptions.push({row:row._row||i+2,id:row.id,code:'REVERSAL',message:'Posible reversión: verificar límites y sustento antes de registrar.',amount:r.adjustment});
 return r;});return {engine:ENGINE_VERSION,rows:output,schedule,totals:Object.fromEntries(Object.entries(totals).map(([k,v])=>[k,formatted(v)])),exceptions};
}
export function reconcile(total,ledger,tolerance,acceptance=''){
 if(!/^-?\d{1,12}(\.\d{1,2})?$/.test(String(ledger))||!/^\d{1,12}(\.\d{1,2})?$/.test(String(tolerance)))throw Error('Saldo y tolerancia deben expresarse con máximo 2 decimales.');const delta=decimal(total)-decimal(ledger),t=decimal(tolerance);if(t<0n)throw Error('La tolerancia no puede ser negativa.');const within=(delta<0n?-delta:delta)<=t;return {total,ledger,tolerance,difference:formatted(delta),resolved:within||String(acceptance).trim().length>=15,acceptance:String(acceptance).trim(),within};
}
export const STATES=['PRUEBA_SELECCIONADA','PROGRAMA_PROPUESTO','PROGRAMA_APROBADO','REQUERIMIENTO_GENERADO','REQUERIMIENTO_APROBADO','DOCUMENTACION_RECIBIDA','DOCUMENTACION_VALIDADA','PRUEBA_CONFIGURADA','METODOLOGIA_APROBADA','PRUEBA_EJECUTADA','RESULTADOS_ANALIZADOS','EN_REVISION','APROBADO'];
export const CAN_APPROVE=['REVISOR','GERENTE','SOCIO','ADMIN'];
export function transition(t,action,role){
 if(t.state==='APROBADO')throw Error('La versión aprobada es inmutable. Cree una nueva versión.');
 const map={generate_program:['PRUEBA_SELECCIONADA','PROGRAMA_PROPUESTO'],approve_program:['PROGRAMA_PROPUESTO','PROGRAMA_APROBADO'],generate_request:['PROGRAMA_APROBADO','REQUERIMIENTO_GENERADO'],approve_request:['REQUERIMIENTO_GENERADO','REQUERIMIENTO_APROBADO'],validate:['DOCUMENTACION_RECIBIDA','DOCUMENTACION_VALIDADA'],configure:['DOCUMENTACION_VALIDADA','PRUEBA_CONFIGURADA'],approve_methodology:['PRUEBA_CONFIGURADA','METODOLOGIA_APROBADA'],execute:['METODOLOGIA_APROBADA','PRUEBA_EJECUTADA'],analyze:['PRUEBA_EJECUTADA','RESULTADOS_ANALIZADOS'],submit:['RESULTADOS_ANALIZADOS','EN_REVISION'],approve:['EN_REVISION','APROBADO']};
 if(!map[action]||map[action][0]!==t.state)throw Error('Acción no disponible en el estado actual.');
 if(action.startsWith('approve')&&!CAN_APPROVE.includes(role))throw Error('Su rol no permite aprobar. Solicite revisión.');
 if(action==='approve_program'&&(!t.program?.length||!t.sourcesVerified))throw Error('Verifique las fuentes y complete el programa antes de aprobar.');
 if(action==='validate'&&(!t.validation?.ok||!t.reconciliation?.resolved))throw Error('Resuelva validaciones y conciliación antes de aprobar información.');
 if(action==='execute'&&(!t.validation?.ok||!t.reconciliation?.resolved))throw Error('Los datos deben estar validados y conciliados.');
 if(action==='approve'&&(!t.run||!t.analysis?.trim()||!t.conclusion?.trim()||!t.conclusionReviewed||!t.validation?.ok||!t.reconciliation?.resolved||t.notes?.some(n=>n.status!=='RESUELTO'||!n.response?.trim())))throw Error('Cierre bloqueado: revise conclusión, ejecución, conciliaciones y respuesta de todos los puntos.');
 return map[action][1];
}
export function createProgram(d,engagement){
 const src=engagement.framework==='NIIF para las PYMES'?{organization:'IFRS Foundation',document:'NIIF para las PYMES — verificar edición aplicable y sección correspondiente',url:'https://www.ifrs.org/issued-standards/ifrs-for-smes/',type:'Norma contable',date:''}:d.source;
 return [
 ['01','Integridad de población','Población incompleta','Integridad','Conciliar la población con el saldo contable al corte.','Auxiliar y mayor contable','Diferencia dentro de tolerancia aprobada o aceptación documentada.'],
 // Una definición del Diseñador no trae `description`: sin respaldo, el procedimiento
 // quedaba vacío y `save_program` rechazaba el programa que el propio sitio generó.
 ['02','Valorar las partidas','Valoración incorrecta','Valoración',d.description||`Recalcular ${d.name} aplicando las reglas y parámetros declarados, partida por partida, y contrastar el resultado contra la evidencia del cliente.`,'Detalle por partida y sustento de parámetros','Aplicar las reglas y parámetros aprobados por partida.'],
 ['03','Evaluar evidencia y excepciones','Supuestos sin sustento','Exactitud','Verificar documentos y supuestos, evaluar excepciones y posibles ajustes.','Soportes de precios, tasas, estimaciones y saldos registrados','Resolver excepciones y documentar conclusión.']
 ].map(x=>({code:`${d.id.toUpperCase()}-${x[0]}`,objective:x[1],risk:x[2],assertion:x[3],procedure:x[4],evidence:x[5],criterion:x[6],source:src,state:'PROPUESTO'}));
}
export function createRequests(program,cutoff,definition){
 const rows=program.map((p,i)=>({id:`RQ-${String(i+1).padStart(3,'0')}`,document:p.evidence,period:cutoff,format:i===0?'XLSX / CSV':'XLSX / DOCX / CSV / XML / PDF / TXT / ZIP / imágenes',purpose:p.objective,procedure:p.code,required:true,status:'PENDIENTE'}));
 if(definition?.id==='vnr'&&rows.length>=3){rows[0].document=`Inventario valorado al ${cutoff}`;rows[1].document='Lista de precios de venta y evidencia de precios realizables';rows[2].document='Gastos de venta o estado de resultados, costos de terminación y sustento de asignación';rows.push({id:'RQ-VNR-04',document:'Política contable, deterioro registrado y sustento de reversos',period:cutoff,format:'XLSX / DOCX / CSV / PDF / TXT',purpose:'Contrastar deterioro calculado contra el saldo registrado y evaluar reversos',procedure:program.at(-1).code,required:true,status:'PENDIENTE'});}return rows;
}
export function preliminary(t){const r=t.run;return `CONCLUSIÓN PRELIMINAR — PENDIENTE DE REVISIÓN DEL AUDITOR\n\nAlcance: ${r.rows.length} registros de ${t.definition.name}. Motor ${r.engine}.\nResultados: ${Object.entries(r.totals).map(([k,v])=>`${k}: ${v}`).join('; ')}.\nConciliación: diferencia ${t.reconciliation.difference}; ${t.reconciliation.within?'dentro de tolerancia':'aceptación documentada: '+t.reconciliation.acceptance}.\nExcepciones identificadas: ${r.exceptions.length}.\nEl auditor debe evaluar el sustento de parámetros y cada excepción antes de concluir.\n\nConclusión del auditor: PENDIENTE.`;}

export function controlTotal(d,rows){let total=0n;for(const r of rows)total+=d.id==='vnr'?decimal(formatted(rounded(decimal(r.quantity)*decimal(r.unit_cost),SCALE))):decimal(r[d.control]);return formatted(total);}
