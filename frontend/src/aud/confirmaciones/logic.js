// Lógica de la herramienta de confirmaciones: campos, tipos, métodos y mapeo de la muestra.
// Los valores por defecto se sincronizan con el backend vía /context; estos son respaldo.

export const TYPE_KEYS = ['bancos', 'cuentas_por_cobrar', 'proveedores', 'relacionados',
  'seguros', 'abogados', 'inventarios_terceros', 'inversiones'];

export const TYPE_LABEL = {
  bancos: 'Bancos e instituciones financieras',
  cuentas_por_cobrar: 'Clientes y cuentas por cobrar',
  proveedores: 'Proveedores y cuentas por pagar',
  relacionados: 'Partes relacionadas',
  seguros: 'Compañías de seguros y corredores',
  abogados: 'Abogados y asesores legales',
  inventarios_terceros: 'Inventarios en poder de terceros',
  inversiones: 'Inversiones y custodios de valores',
};

// Formato de la firma: en blanco (el tercero declara el saldo) para todos los rubros.
export const DEFAULT_METHOD = {
  bancos: 'en_blanco', cuentas_por_cobrar: 'en_blanco', proveedores: 'en_blanco',
  relacionados: 'en_blanco', seguros: 'en_blanco', abogados: 'en_blanco',
  inventarios_terceros: 'en_blanco', inversiones: 'en_blanco',
};

export const METHODS = [
  ['', 'Según el rubro (por defecto)'],
  ['en_blanco', 'En blanco (el tercero declara)'],
  ['positiva', 'Positiva (declara el saldo)'],
  ['negativa', 'Negativa (solo si difiere)'],
];

// Idiomas disponibles (respaldo; el backend devuelve la lista real en /context).
export const LANGUAGES = [['es', 'Español'], ['en', 'English'], ['fr', 'Français'], ['pt', 'Português']];

// Columnas que se pueden mapear desde la muestra cargada.
export const ITEM_FIELDS = ['id', 'type', 'entity', 'contact_name', 'contact_email',
  'contact_address', 'account_ref', 'amount', 'method', 'reference', 'notes'];

export const FIELD_HELP = {
  auditor_email: 'Correo al que responderán los terceros; se imprime en cada carta.',
  response_deadline: 'Fecha límite para la respuesta; no puede ser anterior al corte.',
  signatory: 'Funcionario del cliente que firma y autoriza la revelación.',
  method: 'Vacío usa el método propio del rubro (proveedores: en blanco; resto: positiva).',
  amount: 'Obligatorio para clientes y proveedores, salvo método en blanco.',
};

export function emptyItem() {
  return {id: '', type: 'cuentas_por_cobrar', entity: '', contact_name: '', contact_email: '',
    contact_address: '', account_ref: '', amount: '', method: '', reference: '', notes: ''};
}

// Normaliza etiquetas de tipo escritas por el cliente hacia las claves internas.
export function normalizeType(value) {
  const v = String(value || '').trim().toLowerCase();
  if (TYPE_KEYS.includes(v)) return v;
  if (/banc/.test(v)) return 'bancos';
  if (/cobrar|client/.test(v)) return 'cuentas_por_cobrar';
  if (/pagar|proveed/.test(v)) return 'proveedores';
  if (/relacion|intercomp/.test(v)) return 'relacionados';
  if (/segur|p[oó]liza/.test(v)) return 'seguros';
  if (/abogad|legal|jur/.test(v)) return 'abogados';
  if (/consign|dep[oó]sito|tercero/.test(v)) return 'inventarios_terceros';
  if (/inversi|custod|valor/.test(v)) return 'inversiones';
  return '';
}

// Construye la muestra a partir de una tabla extraída y un mapeo columna→campo.
export function mapSample(table, mapping) {
  if (!table || !table.rows) throw Error('No hay tabla para importar.');
  const idx = k => (mapping[k] === undefined || mapping[k] < 0 ? -1 : mapping[k]);
  if (idx('id') < 0 || idx('type') < 0 || idx('entity') < 0)
    throw Error('Asigne al menos las columnas identificador, tipo y entidad.');
  const items = [];
  const seen = new Set();
  for (const row of table.rows) {
    const get = k => (idx(k) >= 0 ? String(row[idx(k)] ?? '').trim() : '');
    const id = get('id');
    const entity = get('entity');
    if (!id && !entity) continue; // fila vacía
    if (seen.has(id)) throw Error('Identificador duplicado en la muestra: ' + id);
    seen.add(id);
    const item = emptyItem();
    item.id = id;
    item.type = normalizeType(get('type')) || 'cuentas_por_cobrar';
    item.entity = entity;
    for (const k of ['contact_name', 'contact_email', 'contact_address', 'account_ref', 'amount', 'reference', 'notes'])
      if (idx(k) >= 0) item[k] = get(k);
    const m = get('method').toLowerCase();
    item.method = ['positiva', 'negativa', 'en_blanco'].includes(m) ? m : '';
    items.push(item);
  }
  if (!items.length) throw Error('La tabla no contiene filas con datos.');
  return items;
}
