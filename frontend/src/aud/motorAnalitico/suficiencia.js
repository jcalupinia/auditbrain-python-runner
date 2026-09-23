/* Traduce la suficiencia del motor a algo que el auditor pueda leer.
   Regla de la firma: una prueba que no corrió NUNCA se muestra como
   «sin excepciones»; siempre dice por qué no corrió. */

export const ESTADOS = {
  corrio: "Corrió",
  noCorrio: "No corrió",
  sinDatos: "No disponible por falta de datos",
};

const ORDEN = [ESTADOS.corrio, ESTADOS.noCorrio, ESTADOS.sinDatos];
const sinBase = (b) => `Falta cargar ${b.join(", ")}`;
const sinColumna = (c) => `Falta la columna ${c.map((x) => x.split(".").pop()).join(", ")}`;

export function filasSuficiencia(suficiencia) {
  if (!suficiencia?.reglas) return [];
  const filas = Object.entries(suficiencia.reglas).map(([regla, v]) => {
    let estado = ESTADOS.corrio;
    let detalle = "";
    if (!v.disponible) {
      estado = ESTADOS.sinDatos;
      detalle = v.bases_faltantes?.length ? sinBase(v.bases_faltantes) : sinColumna(v.faltan || []);
    } else if (v.motivo_no_corrida) {
      estado = ESTADOS.noCorrio;
      detalle = v.motivo_no_corrida;
    } else if (v.evidencia_incompleta?.length) {
      detalle = `Sin el dato de ${v.evidencia_incompleta.map((x) => x.split(".").pop()).join(", ")} en la evidencia`;
    }
    return { regla, estado, detalle };
  });
  filas.sort((a, b) => ORDEN.indexOf(a.estado) - ORDEN.indexOf(b.estado) || a.regla.localeCompare(b.regla));
  return filas;
}

export function resumenLectura(lectura) {
  if (!lectura) return null;
  const n = (v) => Number(v || 0).toLocaleString("es-EC");
  return {
    filas: `${n(lectura.filas_leidas)} movimientos · ${n(lectura.filas_descartadas)} filas descartadas`,
    cuentas: `${n(lectura.cuentas)} cuentas`,
    periodo: (lectura.rango_fechas || []).join(" a "),
    hojas: (lectura.hojas_leidas || []).join(", "),
    columnas: Object.keys(lectura.columnas_detectadas || {}).join(", "),
    vacias: (lectura.columnas_vacias || []).join(", "),
    huella: lectura.sha256 ? `${lectura.sha256.slice(0, 16)}…` : "",
  };
}
