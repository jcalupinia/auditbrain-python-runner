// Lógica pura del panel «Pruebas sugeridas» (puente planificación → pruebas), sin
// React ni red, para probarla en aislamiento. El componente PruebasSugeridas.jsx solo
// orquesta estado y la llamada a la API (cicloPruebasSugeridas).

// ¿La prueba es de planificación? (el puente solo aplica a ella).
export function esPlanificacion(prueba) {
  return (prueba?.definicion?.processor || "") === "planificacion_nia";
}

// Totales para el encabezado del panel.
export function resumen(data) {
  const pruebas = data?.pruebas || [];
  const sinPrueba = data?.sin_prueba || [];
  return {
    nPruebas: pruebas.length,
    nConRiesgo: pruebas.filter((p) => p.con_riesgo).length,
    cuentas: data?.cuentas_a_revisar ?? 0,
    nSinPrueba: sinPrueba.length,
  };
}

export function hayContenido(data) {
  return (data?.pruebas?.length || 0) + (data?.sin_prueba?.length || 0) > 0;
}

// Formato de monto con separador de miles y dos decimales (determinista, sin Intl
// para no depender del locale del entorno de test).
export function formatoMonto(n) {
  if (n === null || n === undefined || n === "") return "—";
  const num = Number(n);
  if (!Number.isFinite(num)) return "—";
  const [ent, dec] = Math.abs(num).toFixed(2).split(".");
  const miles = ent.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${num < 0 ? "-" : ""}${miles}.${dec}`;
}
