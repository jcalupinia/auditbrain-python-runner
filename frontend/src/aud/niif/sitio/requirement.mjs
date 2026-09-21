// Requerimiento de información estructurado en ítems.
//
// Un requerimiento deja de ser un texto libre y pasa a ser una lista de ítems
// con identidad. Cada ítem declara QUÉ se pide (por contenido, no por
// extensión), a qué FORMATOS debe acogerse el cliente, si es obligatorio y en
// cuántos COMPONENTES viene.
//
// Los componentes son la pieza que faltaba: un mayor general entregado por mes
// son doce componentes de un mismo ítem. Sin declararlos, doce archivos sueltos
// se ven igual que uno, y nadie nota que falta abril (Manual §08).

export const FORMATS = ['xlsx', 'csv', 'pdf', 'txt', 'md', 'xml', 'docx', 'zip', 'png', 'jpg', 'jpeg', 'webp'];

export const MAX_ITEMS = 40;
export const MAX_COMPONENTS = 60;

function clean(value, max) {
  const text = String(value ?? '').trim().replace(/\s+/g, ' ');
  if (!text || text.length > max) throw new Error(`Texto vacío o superior a ${max} caracteres.`);
  return text;
}

/** Normaliza y valida la lista de ítems que llega del formulario. */
export function parseItems(raw) {
  if (!Array.isArray(raw) || raw.length === 0 || raw.length > MAX_ITEMS) {
    throw new Error(`Defina entre 1 y ${MAX_ITEMS} ítems de requerimiento.`);
  }
  const seen = new Set();
  return raw.map((entry, index) => {
    const text = clean(entry?.text, 2000);
    const key = text.toLowerCase();
    if (seen.has(key)) throw new Error(`Ítem repetido: ${text}`);
    seen.add(key);

    const formats = [...new Set((entry?.formats ?? []).map(f => String(f).toLowerCase().replace(/^\./, '')))];
    if (!formats.length) throw new Error(`Indique al menos un formato aceptado para: ${text}`);
    const invalid = formats.find(f => !FORMATS.includes(f));
    if (invalid) throw new Error(`Formato no admitido (${invalid}) en: ${text}`);

    const components = [...new Set((entry?.components ?? []).map(c => clean(c, 120)))];
    if (components.length > MAX_COMPONENTS) throw new Error(`Máximo ${MAX_COMPONENTS} componentes en: ${text}`);

    const group = entry?.group ? clean(entry.group, 120) : '';
    const columns = [...new Set((entry?.columns ?? []).map(c => clean(c, 120)))];
    if (columns.length > 60) throw new Error(`Máximo 60 columnas en: ${text}`);
    const instructions = entry?.instructions ? clean(entry.instructions, 2000) : '';

    return { id: `i${index + 1}`, text, formats, required: entry?.required !== false, components, group, columns, instructions };
  });
}

/** Documentos que corresponden a un ítem (y opcionalmente a un componente). */
function matches(docs, itemId, component) {
  // Un documento rechazado por el auditor no cuenta como cobertura: sigue
  // guardado como evidencia de lo recibido, pero no tapa el hueco.
  return docs.filter(d => d.kind === 'source' && d.itemId === itemId && d.state !== 'rechazado'
    && (component === undefined || d.component === component));
}

/**
 * Estado de cobertura por ítem. `pending` lista lo que falta: el ítem completo
 * cuando no tiene componentes, o los componentes ausentes cuando sí los tiene.
 */
export function coverage(items = [], docs = []) {
  return items.map(item => {
    const received = matches(docs, item.id).length;
    if (!item.components.length) {
      return { id: item.id, text: item.text, required: item.required, received, expected: 1,
        pending: received ? [] : [item.text], complete: received > 0 };
    }
    const pending = item.components.filter(c => matches(docs, item.id, c).length === 0);
    return { id: item.id, text: item.text, required: item.required, received,
      expected: item.components.length, pending, complete: pending.length === 0 };
  });
}

// Un item sin componentes se nombra solo: repetir su texto como "componente
// faltante" no informa de nada.
const describe = c => c.expected === 1
  ? c.text
  : c.pending.length === c.expected
    ? `${c.text}: falta todo (0 de ${c.expected})`
    : `${c.text}: faltan ${c.pending.join(', ')}`;

/**
 * Qué impide avanzar. Los ítems opcionales nunca bloquean. Los ítems que
 * comparten `group` son fuentes alternativas: basta cubrir una para dar el
 * grupo por satisfecho (por ejemplo, costos por ítem O estado de resultados
 * con su base de asignación).
 */
export function gaps(items = [], docs = []) {
  const estado = coverage(items, docs).map((c, i) => ({ ...c, group: items[i].group || '' }));
  const sueltos = estado.filter(c => !c.group && c.required && !c.complete).map(describe);

  const grupos = new Map();
  for (const c of estado.filter(c => c.group)) {
    if (!grupos.has(c.group)) grupos.set(c.group, []);
    grupos.get(c.group).push(c);
  }
  const porGrupo = [];
  for (const [nombre, miembros] of grupos) {
    if (miembros.some(m => m.complete)) continue;
    if (!miembros.some(m => m.required)) continue;
    porGrupo.push(`${nombre}: entregue una de estas fuentes — ${miembros.map(m => m.text).join(' o ')}`);
  }
  return [...sueltos, ...porGrupo];
}

/**
 * Plantilla CSV con las columnas que el ítem espera. Se genera del propio
 * ítem: no hay archivos que mantener ni que se desactualicen.
 */
export function templateCsv(item) {
  if (!item?.columns?.length) return null;
  const NL = String.fromCharCode(10);
  const escape = v => '"' + String(v).split('"').join('""') + '"';
  const cabecera = item.columns.map(escape).join(',');
  const nota = item.instructions ? '# ' + item.instructions.split(NL).join(' ') + NL : '';
  return nota + cabecera + NL;
}

/** Valida un archivo contra el ítem al que se lo vincula. */
export function checkUpload(items, itemId, component, filename) {
  const item = items.find(i => i.id === itemId);
  if (!item) throw new Error('Vincule el archivo a un ítem del requerimiento.');
  const ext = String(filename).split('.').pop()?.toLowerCase() ?? '';
  if (!item.formats.includes(ext)) {
    throw new Error(`"${item.text}" admite ${item.formats.join(', ').toUpperCase()}. Recibido: ${ext || 'sin extensión'}.`);
  }
  if (item.components.length) {
    if (!component) throw new Error(`"${item.text}" se entrega por componentes. Indique cuál: ${item.components.join(', ')}.`);
    if (!item.components.includes(component)) throw new Error(`Componente no declarado en "${item.text}": ${component}.`);
  } else if (component) {
    throw new Error(`"${item.text}" no se entrega por componentes.`);
  }
  return item;
}

// Comprobación ejecutable: node lib/requirement.mjs
// Sin importar 'node:url': este módulo también corre dentro del Worker.
if (typeof process !== 'undefined' && process.argv?.[1]?.endsWith('requirement.mjs')) {
  const assert = (ok, msg) => { if (!ok) throw new Error('FALLA: ' + msg); };
  const items = parseItems([
    { text: 'Mayor general', formats: ['xlsx', 'csv'], components: ['enero', 'febrero', 'marzo'] },
    { text: 'Políticas contables', formats: ['pdf', 'md'] },
    { text: 'Fotos de bodega', formats: ['jpg'], required: false },
  ]);
  assert(items[0].components.length === 3, 'componentes declarados');
  assert(items[1].required === true, 'obligatorio por defecto');

  const docs = [
    { kind: 'source', itemId: 'i1', component: 'enero' },
    { kind: 'source', itemId: 'i1', component: 'marzo' },
  ];
  const faltantes = gaps(items, docs);
  assert(faltantes.some(g => g.includes('febrero')), 'detecta el mes faltante');
  assert(faltantes.some(g => g.includes('Políticas')), 'detecta el ítem sin evidencia');
  assert(faltantes.some(g => g === 'Políticas contables'), 'un ítem sin componentes se nombra una sola vez');
  assert(!faltantes.some(g => g.includes('Fotos')), 'el opcional no bloquea');

  const completos = [...docs, { kind: 'source', itemId: 'i1', component: 'febrero' },
    { kind: 'source', itemId: 'i2' }];
  assert(gaps(items, completos).length === 0, 'sin huecos cuando está todo');

  // Un archivo por ítem NO alcanza cuando hay componentes: es el bug que esto evita.
  assert(gaps(items, [{ kind: 'source', itemId: 'i1', component: 'enero' },
    { kind: 'source', itemId: 'i2' }]).length === 1, 'un archivo no cubre doce meses');

  let fallo = '';
  try { checkUpload(items, 'i1', 'enero', 'mayor.pdf'); } catch (e) { fallo = e.message; }
  assert(fallo.includes('XLSX, CSV'), 'rechaza formato no declarado');
  try { checkUpload(items, 'i1', 'abril', 'mayor.xlsx'); } catch (e) { fallo = e.message; }
  assert(fallo.includes('no declarado'), 'rechaza componente inexistente');
  checkUpload(items, 'i2', undefined, 'politicas.md');

  // --- B3.2 fuentes alternativas ---
  const alt = parseItems([
    { text: 'Costos de venta por ítem', formats: ['xlsx'], group: 'Costos necesarios para vender' },
    { text: 'Estado de resultados con base de asignación', formats: ['pdf'], group: 'Costos necesarios para vender' },
  ]);
  assert(gaps(alt, []).length === 1, 'el grupo sin cubrir reporta un solo hueco');
  assert(gaps(alt, [])[0].includes(' o '), 'el hueco nombra las dos alternativas');
  assert(gaps(alt, [{ kind: 'source', itemId: 'i2' }]).length === 0, 'una alternativa satisface el grupo');

  // --- B3.3 plantilla generada del propio ítem ---
  const conColumnas = parseItems([{ text: 'Inventario al corte', formats: ['csv'],
    columns: ['sku', 'cantidad', 'costo unitario'], instructions: 'Un renglón por SKU, sin totales.' }]);
  const csv = templateCsv(conColumnas[0]);
  assert(csv.includes('"sku","cantidad","costo unitario"'), 'la plantilla lleva las columnas');
  assert(csv.startsWith('# Un renglón'), 'la plantilla lleva las instrucciones');
  assert(templateCsv({ columns: [] }) === null, 'sin columnas no hay plantilla');

  // --- B3.4 un documento rechazado no tapa el hueco ---
  const unItem = parseItems([{ text: 'Mayor', formats: ['csv'], components: ['enero'] }]);
  assert(gaps(unItem, [{ kind: 'source', itemId: 'i1', component: 'enero' }]).length === 0, 'validado cubre');
  assert(gaps(unItem, [{ kind: 'source', itemId: 'i1', component: 'enero', state: 'rechazado' }]).length === 1,
    'rechazado NO cubre');

  console.log('requirement.mjs: todas las comprobaciones pasaron');
}
