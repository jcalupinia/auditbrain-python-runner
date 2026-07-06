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
import { PARSER_TO_DASH } from "./finModel.js";

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

// Alinea UNO o VARIOS resultados tipados a un eje por identidad, preservando el
// detalle por cuenta (drill-down). Soporta el caso en que ESF y ERI vienen en
// archivos SEPARADOS (el detallado codificado: un archivo ESF + un archivo ERI)
// o en un mismo archivo. Devuelve { D, periodos, cuentas }.
//
// - Fuente ESF = primer res con `periodos_esf`; fuente ERI = primero con `periodos_eri`.
// - `data` combinada: claves ESF desde la fuente ESF (índice periodos_esf),
//   claves ER desde la fuente ERI (índice periodos_eri).
// - `cuentas`: cada cuenta trae `vals` en el orden de columnas de SU archivo;
//   se remapea al eje por identidad año-mes. Las cuentas de resultado usan la
//   identidad del ERI; las de balance, la del ESF. Los períodos solo-ERI (may-25)
//   no entran al eje (se usan en Comparaciones), igual que en `alinearPorIdentidad`.
export function alinearMultiarchivo(items) {
  const reses = (items || []).map((it) => (it && it.res ? it.res : it)).filter(Boolean);
  const esfSrc = reses.find((r) => (r.periodos_esf || []).length) || null;
  const eriSrc = reses.find((r) => (r.periodos_eri || []).length) || null;
  const perEsf = esfSrc ? esfSrc.periodos_esf : [];
  const perEri = eriSrc ? eriSrc.periodos_eri : [];

  const data = {};
  ALL_KEYS.forEach((k) => {
    const src = ESF_KEYS.has(k) ? esfSrc : eriSrc; // ER_KEYS + dna -> ERI
    data[k] = src && src.data && Array.isArray(src.data[k]) ? src.data[k] : [];
  });
  const { D, periodos } = alinearPorIdentidad({ periodos_esf: perEsf, periodos_eri: perEri, data });

  // Detalle por cuenta remapeado al eje por identidad.
  const idEsf = new Map(perEsf.map((p, i) => [identidadPeriodo(p), i]));
  const idEri = new Map(perEri.map((p, j) => [identidadPeriodo(p), j]));
  const ejeIds = periodos.map((p) => identidadPeriodo(p));
  const cuentas = [];
  reses.forEach((r) => {
    (r.detalle || []).forEach((acc) => {
      const dk = PARSER_TO_DASH[acc.key] || acc.key;
      const idxById = acc.sec === "resultado" ? idEri : idEsf;
      const vals = ejeIds.map((id) => {
        const col = idxById.get(id);
        return col == null ? 0 : Math.round(num((acc.vals || [])[col]));
      });
      if (vals.some((v) => v !== 0)) {
        cuentas.push({ sec: acc.sec, key: dk, codigo: acc.codigo || "", nombre: acc.nombre, vals });
      }
    });
  });
  return { D, periodos, cuentas };
}
