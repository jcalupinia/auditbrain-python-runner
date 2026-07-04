// Alineación de períodos por IDENTIDAD para balances resumidos/detallados.
//
// El modelo de fusión por año (cargarInternos) asume períodos anuales y se
// desalinea cuando el Balance (ESF) y el Estado de Resultados (ERI) traen distinto
// número de columnas — p.ej. ESF: [may-26, 2025, 2024, 2023] (4) y ERI:
// [may-26, may-25, 2025, 2024, 2023] (5). El corte parcial extra (may-25) corría
// todo (el ER de 2024 quedaba pegado al balance de 2023).
//
// Aquí cada período se identifica por (año, mes): parcial → año*100+mes, anual →
// año*100+12. El EJE lo define el Balance (los saldos son el "backbone"); cada
// columna toma su valor ESF y el valor ER del período del ERI con la MISMA
// identidad (may-26↔may-26, 2025↔2025). Los períodos que solo existen en el ERI
// (may-25) NO entran al eje del dashboard — se usan aparte en las Comparaciones.

import { ESF_SCHEMA, ER_SCHEMA, INPUT_KEYS } from "../tax/seed.js";

const ESF_KEYS = new Set(ESF_SCHEMA.filter((r) => r[0] === "in" || r[0] === "det").map((r) => r[1]));
const ER_KEYS = new Set(ER_SCHEMA.filter((r) => r[0] === "in" || r[0] === "det").map((r) => r[1]));
const ALL_KEYS = INPUT_KEYS.concat(["dna"]);

const num = (v) => (v == null ? 0 : (+v || 0));

// Identidad numérica ordenable de un período {label,tipo,meses,anio} del backend.
export function identidadPeriodo(p) {
  const mes = p && p.tipo === "parcial" ? (p.meses || 1) : 12;
  return (p ? p.anio : 0) * 100 + mes;
}

// ¿El resultado trae la metadata de períodos que permite alinear por identidad?
export function tienePeriodosTipados(res) {
  return !!(res && ((res.periodos_esf && res.periodos_esf.length) || (res.periodos_eri && res.periodos_eri.length)));
}

// Alinea UN resultado del backend a un eje basado en el Balance.
// Devuelve { D, periodos } donde D[clave] = [valor por período] y periodos =
// [{label, labelESF, labelER, meses, anio, tipo}] ordenado ascendente por fecha.
export function alinearPorIdentidad(res) {
  const perEsf = (res.periodos_esf || []).map((p, i) => ({ ...p, _i: i, id: identidadPeriodo(p) }));
  const perEri = (res.periodos_eri || []).map((p, j) => ({ ...p, _j: j, id: identidadPeriodo(p) }));
  const data = res.data || {};

  // Eje = períodos del balance; si no hay balance, los del ERI.
  const eje = (perEsf.length ? perEsf : perEri).slice().sort((a, b) => a.id - b.id);
  const eriPorId = new Map(perEri.map((p) => [p.id, p]));
  const esfPorId = new Map(perEsf.map((p) => [p.id, p]));

  const D = {};
  ALL_KEYS.forEach((k) => (D[k] = []));
  const periodos = [];

  eje.forEach((p) => {
    const eEsf = esfPorId.get(p.id);
    const eEri = eriPorId.get(p.id);
    ALL_KEYS.forEach((k) => {
      let v = 0;
      if (ESF_KEYS.has(k)) v = eEsf ? num((data[k] || [])[eEsf._i]) : 0;
      else v = eEri ? num((data[k] || [])[eEri._j]) : 0; // ER_KEYS + dna
      D[k].push(v);
    });
    periodos.push({
      label: p.label,
      labelESF: (eEsf || {}).label || p.label,
      labelER: (eEri || {}).label || p.label,
      meses: p.tipo === "parcial" ? (p.meses || 12) : 12,
      anio: p.anio,
      tipo: p.tipo,
    });
  });
  return { D, periodos };
}
