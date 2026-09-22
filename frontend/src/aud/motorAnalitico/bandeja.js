// Lógica pura de la bandeja de trabajos de «Mayores y diarios» (SP2, Task 3).
//
// Contrato real del motor (motor-auditoria-analitica@sp2a-trabajos):
// - GET /trabajos/{id} → {id, estado, origen, creado, terminado, sha256, total, por_severidad, errores}
// - GET /trabajos/{id}/excepciones → {total, pagina, tam, excepciones: [...]}
//   cada excepción (motor/nucleo.py::Excepcion.a_dict()):
//   {regla_id, severidad, entidad_tipo, entidad_id, descripcion, evidencia,
//    monto_expuesto (texto), reglas_concurrentes, nia, hash}
import { ErrorMotor } from "./clienteMotor.js";

export const SEVERIDADES = ["P0", "P1", "P2", "INFO"];
export const terminado = (estado) => estado === "listo" || estado === "error";
export const resumenSeveridad = (porSev = {}) => SEVERIDADES.map((s) => [s, porSev[s] || 0]);
export const paginas = (total, tam) => Math.max(1, Math.ceil(total / tam));

// null si el valor está vacío o no es numérico: nunca se inventa «0,00».
export function dinero(texto) {
  if (texto === null || texto === undefined || String(texto).trim() === "") return null;
  const n = Number(texto);
  return Number.isFinite(n) ? n.toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : null;
}

// Envuelve dinero() con la bandera que la celda usa para pintar «sin datos».
export function montoVisible(texto) {
  const d = dinero(texto);
  return d === null ? { sinDatos: true, texto: "sin datos" } : { sinDatos: false, texto: d };
}

// De la respuesta cruda de /excepciones a filas listas para la tabla: lee
// `excepciones` (no `items`) y arma las columnas reales del contrato.
export function filasBandeja(respuesta) {
  return (respuesta?.excepciones || []).map((e) => ({
    hash: e.hash,
    severidad: e.severidad,
    reglaId: e.regla_id,
    nia: e.nia,
    entidad: `${e.entidad_tipo} ${e.entidad_id}`,
    descripcion: e.descripcion,
    monto: montoVisible(e.monto_expuesto),
    reglasConcurrentes: e.reglas_concurrentes,
    evidencia: e.evidencia,
  }));
}

// El 429 del motor trae dos motivos distintos en `detail` (servicio/app.py):
// «ya tienes 3 trabajos en curso» (cupo) vs «demasiadas solicitudes» (ritmo).
export function mensajeError(e) {
  if (e?.name === "AbortError") return "El motor no respondió a tiempo.";
  if (e instanceof ErrorMotor && e.estado === 429) {
    return /trabajos en curso/i.test(e.message || "")
      ? "Ya tienes 3 trabajos en curso: espera a que terminen."
      : "Demasiadas consultas seguidas: espera un minuto.";
  }
  return e?.message || "Error al comunicarse con el motor.";
}
