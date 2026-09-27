import {describe, it, expect} from 'vitest';
import {mapSample, normalizeType, DEFAULT_METHOD} from './logic';

describe('Confirmaciones · mapeo de la muestra', () => {
  const table = {name: 'muestra', headers: ['id', 'tipo', 'entidad', 'correo', 'saldo'],
    rows: [['C-01', 'Clientes', 'Distribuidora Sur', 'p@dsur.ec', '48200'],
           ['P-01', 'Proveedores', 'Importadora Global', 'c@global.com', '']]};
  const mapping = {id: 0, type: 1, entity: 2, contact_email: 3, amount: 4};

  it('mapea por columna, no por posición fija', () => {
    const items = mapSample(table, mapping);
    expect(items).toHaveLength(2);
    expect(items[0].type).toBe('cuentas_por_cobrar');
    expect(items[1].type).toBe('proveedores');
    expect(items[0].contact_email).toBe('p@dsur.ec');
  });

  it('exige id, tipo y entidad', () =>
    expect(() => mapSample(table, {id: 0})).toThrow('identificador'));

  it('rechaza identificadores duplicados', () =>
    expect(() => mapSample({rows: [['A', 'banco', 'X'], ['A', 'banco', 'Y']]},
      {id: 0, type: 1, entity: 2})).toThrow('duplicado'));

  it('normaliza etiquetas del cliente a claves internas', () => {
    expect(normalizeType('Banco Pichincha')).toBe('bancos');
    expect(normalizeType('cuentas por pagar')).toBe('proveedores');
    expect(normalizeType('Póliza')).toBe('seguros');
    expect(normalizeType('desconocido')).toBe('');
  });

  it('proveedores usa método en blanco por defecto', () =>
    expect(DEFAULT_METHOD.proveedores).toBe('en_blanco'));
});
