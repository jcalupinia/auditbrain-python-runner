export const FIELDS=[['code','Código / lote'],['description','Descripción'],['quantity','Cantidad'],['unit_cost','Costo unitario'],['selling_price','Precio de venta'],['completion_cost','Terminación unitaria'],['selling_cost','Venta unitaria'],['recorded_impairment','Deterioro registrado total'],['tax_base','Base fiscal total'],['source','Referencia de evidencia']];
export const SLOTS=[['inventory','Inventario valorado al corte',['code','description','quantity','unit_cost','recorded_impairment']],['prices','Lista de precios de venta',['code','selling_price']],['expenses','Gastos necesarios / estado de resultados',['code','completion_cost','selling_cost']],['policy','Políticas y soporte tributario',[]]];
export function applyTable(existing,table,mapping,slot,filename){
  const required=SLOTS.find(x=>x[0]===slot)?.[2]||[];
  if(!required.length)throw Error('Esta fuente es soporte documental. Revise su contenido.');
  for(const key of required)if(mapping[key]===undefined||mapping[key]==='')throw Error('Asigne la columna: '+FIELDS.find(x=>x[0]===key)?.[1]);
  const seen=new Set();
  const incoming=table.rows.map((r,i)=>{
    const row=Object.fromEntries(required.map(k=>[k,String(r[Number(mapping[k])]??'').trim()]));
    if(!row.code||seen.has(row.code))throw Error('Código vacío o duplicado en fila '+(i+2));
    seen.add(row.code);row.source=filename+' / '+table.name+' / fila '+(i+2);return row;
  });
  if(slot==='inventory')return incoming.map(r=>({...Object.fromEntries(FIELDS.map(([k])=>[k,''])),...r}));
  if(!existing.length)throw Error('Importe primero el inventario.');
  const matched=new Map(incoming.map(r=>[r.code,r]));
  const missing=existing.filter(r=>!matched.has(r.code));
  if(missing.length)throw Error('Faltan datos para: '+missing.slice(0,8).map(r=>r.code).join(', '));
  return existing.map(r=>({...r,...matched.get(r.code),source:r.source+'; '+matched.get(r.code).source}));
}
export function emptyRow(){return Object.fromEntries(FIELDS.map(([k])=>[k,'']));}
