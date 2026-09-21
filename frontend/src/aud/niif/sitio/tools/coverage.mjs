// Puente entre los requerimientos de una Herramienta y el motor de cobertura.
//
// El Centro de trabajo y las Herramientas nacieron con modelos distintos:
// `items` allá, `requests` acá. En vez de duplicar la lógica de cobertura —que
// ya está probada en lib/requirement.mjs— se adaptan las formas.
//
// Así ambas entradas del menú aplican EL MISMO control: un requerimiento con
// componentes solo se cubre cuando llegan todos, un archivo en formato no
// declarado se rechaza, y un documento rechazado por el auditor no cubre.

import { coverage, gaps, checkUpload, FORMATS } from '../requirement.mjs';

/** Convierte el texto de formatos del requerimiento en la lista que valida. */
export function parseFormats(value) {
  const crudo = String(value ?? '').toLowerCase();
  const encontrados = FORMATS.filter(f => new RegExp(`(^|[^a-z])${f}([^a-z]|$)`).test(crudo));
  // jpg y jpeg son el mismo formato para el auditor; "imágenes" los implica.
  if (/imagen|imágenes|imagenes/.test(crudo)) return [...new Set([...encontrados, 'png', 'jpg', 'jpeg', 'webp'])];
  return encontrados;
}

/** Requerimientos de Herramienta vistos como ítems del motor de cobertura. */
export function requestsAsItems(requests = []) {
  return requests.map(r => ({
    id: r.id,
    text: r.document || r.id,
    formats: Array.isArray(r.formats) && r.formats.length ? r.formats : parseFormats(r.format),
    required: r.required !== false,
    components: Array.isArray(r.components) ? r.components : [],
    group: r.group || '',
  }));
}

/**
 * Archivos de Herramienta vistos como documentos del motor. `rejected` es el
 * conjunto de identificadores que el auditor marcó como rechazados.
 */
export function filesAsDocs(files = [], rejected = []) {
  const fuera = new Set(rejected);
  return files.map(f => ({
    kind: 'source',
    itemId: f.requestId,
    component: f.component || undefined,
    state: fuera.has(f.id) ? 'rechazado' : undefined,
  }));
}

/** Qué impide validar la documentación de una Herramienta. */
export function toolGaps(requests, files, rejected) {
  return gaps(requestsAsItems(requests), filesAsDocs(files, rejected));
}

/** Estado de cobertura por requerimiento, para mostrarlo en pantalla. */
export function toolCoverage(requests, files, rejected) {
  return coverage(requestsAsItems(requests), filesAsDocs(files, rejected));
}

/** Valida un archivo contra el requerimiento al que se lo vincula. */
export function checkToolUpload(requests, requestId, component, filename) {
  return checkUpload(requestsAsItems(requests), requestId, component, filename);
}

// Comprobación ejecutable: node lib/tools/coverage.mjs
if (typeof process !== 'undefined' && process.argv?.[1]?.endsWith('coverage.mjs')) {
  const assert = (ok, msg) => { if (!ok) throw new Error('FALLA: ' + msg); };

  assert(parseFormats('XLSX / CSV').join() === 'xlsx,csv', 'lee los formatos del texto');
  assert(parseFormats('XLSX / DOCX / CSV / XML / PDF / TXT / ZIP / imágenes').includes('png'),
    'imágenes implica png, jpg y webp');
  assert(parseFormats('').length === 0, 'texto vacío no declara formatos');

  const requests = [
    { id: 'RQ-001', document: 'Mayor general', format: 'XLSX / CSV', required: true, components: ['enero', 'febrero'] },
    { id: 'RQ-002', document: 'Políticas contables', format: 'PDF', required: true },
    { id: 'RQ-003', document: 'Fotos de bodega', format: 'imágenes', required: false },
  ];
  const unArchivo = [{ id: 'f1', requestId: 'RQ-001', component: 'enero' }, { id: 'f2', requestId: 'RQ-002' }];

  // El control anterior daba esto por cubierto: un archivo por requerimiento.
  const faltan = toolGaps(requests, unArchivo, []);
  assert(faltan.length === 1 && faltan[0].includes('febrero'), 'detecta el componente faltante');

  const completo = [...unArchivo, { id: 'f3', requestId: 'RQ-001', component: 'febrero' }];
  assert(toolGaps(requests, completo, []).length === 0, 'sin huecos cuando está todo');
  assert(toolGaps(requests, completo, ['f3']).length === 1, 'un archivo rechazado reabre el hueco');

  let fallo = '';
  try { checkToolUpload(requests, 'RQ-002', undefined, 'politicas.xlsx'); } catch (e) { fallo = e.message; }
  assert(fallo.includes('PDF'), 'rechaza formato no declarado');
  checkToolUpload(requests, 'RQ-001', 'enero', 'mayor.csv');

  console.log('tools/coverage.mjs: todas las comprobaciones pasaron');
}
