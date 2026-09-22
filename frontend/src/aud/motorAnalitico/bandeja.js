// Lógica pura de la bandeja de trabajos de «Mayores y diarios» (SP2, Task 3).
export const SEVERIDADES = ["P0", "P1", "P2", "INFO"];
export const terminado = (estado) => estado === "listo" || estado === "error";
export const resumenSeveridad = (porSev = {}) => SEVERIDADES.map((s) => [s, porSev[s] || 0]);
export const paginas = (total, tam) => Math.max(1, Math.ceil(total / tam));
export const dinero = (texto) =>
  Number(texto || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
