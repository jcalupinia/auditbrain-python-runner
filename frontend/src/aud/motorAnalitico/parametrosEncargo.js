/* Parámetros del encargo (bloque U del formulario AUT-2026-001).
   El motor los exige sin valores por defecto: aquí solo se valida lo mismo
   antes de subir el archivo, para no hacerle perder el viaje al auditor.
   Espejo de `motor/parametros.py` (motor-auditoria-analitica@main):
   mismos límites, mismos textos de error que las pruebas de este archivo. */

export const CAMPOS = [
  { id: "ejercicio_inicio", etiqueta: "Inicio del ejercicio", tipo: "date", nia: "NIA 230" },
  { id: "ejercicio_fin", etiqueta: "Fin del ejercicio", tipo: "date", nia: "NIA 230" },
  { id: "materialidad", etiqueta: "Materialidad global", tipo: "importe", nia: "NIA 320 párr. 10" },
  { id: "materialidad_ejecucion", etiqueta: "Materialidad de ejecución", tipo: "importe", nia: "NIA 320 párr. 11" },
  { id: "umbral_insignificante", etiqueta: "Error claramente insignificante", tipo: "importe", nia: "NIA 450 párr. 5" },
  { id: "umbral_aprobacion", etiqueta: "Umbral de aprobación de gastos", tipo: "importe", nia: "NIA 240" },
  { id: "error_tolerable", etiqueta: "Error tolerable (muestreo)", tipo: "importe", nia: "NIA 530" },
  { id: "confianza", etiqueta: "Nivel de confianza", tipo: "opciones", opciones: [80, 90, 95, 99], nia: "NIA 330" },
  { id: "semilla", etiqueta: "Semilla del muestreo", tipo: "entero", nia: "NIA 530 / 230" },
  { id: "hora_inicio", etiqueta: "Hora de inicio de jornada", tipo: "entero", nia: "NIA 240" },
  { id: "hora_fin", etiqueta: "Hora de fin de jornada", tipo: "entero", nia: "NIA 240" },
  { id: "feriados", etiqueta: "Feriados (separados por coma)", tipo: "fechas", nia: "NIA 240", opcional: true },
  { id: "fecha_registro_es_contable", etiqueta: "Este mayor no distingue fecha de registro: usar la contable", tipo: "casilla", nia: "NIA 230", opcional: true },
];

export const INICIALES = Object.fromEntries(
  CAMPOS.map((c) => [c.id, c.tipo === "casilla" ? false : ""])
);

const IMPORTE = /^-?\d+([.,]\d+)?$/;
const FECHA = /^\d{4}-\d{2}-\d{2}$/;
const ENTERO = /^-?\d+$/;
const num = (v) => Number(String(v).replace(",", "."));
const fechas = (v) => String(v || "").split(",").map((f) => f.trim()).filter(Boolean);

// El motor usa datetime.date.fromisoformat, que rechaza un calendario
// inexistente ("2026-02-30" tiene formato válido pero no existe). El regex
// FECHA solo valida el formato; esta función valida que la fecha exista.
function fechaValida(v) {
  const t = String(v).trim();
  if (!FECHA.test(t)) return false;
  const [y, m, d] = t.split("-").map(Number);
  const fecha = new Date(Date.UTC(y, m - 1, d));
  return fecha.getUTCFullYear() === y && fecha.getUTCMonth() === m - 1 && fecha.getUTCDate() === d;
}

function importeInvalido(v) {
  const t = String(v).trim();
  if (!IMPORTE.test(t)) return true;
  const decimales = t.split(/[.,]/)[1];
  // "50.000" pasa el regex pero para dinero solo caben 2 decimales:
  // 3+ es casi siempre un separador de miles mal escrito (espejo del motor).
  return Boolean(decimales) && decimales.length > 2;
}

function vacio(v) {
  return v === "" || v === null || v === undefined;
}

export function validar(valores) {
  const errores = {};

  for (const campo of CAMPOS) {
    if (campo.opcional) continue;
    if (vacio(valores[campo.id])) errores[campo.id] = "obligatorio";
  }

  for (const campo of CAMPOS) {
    if (errores[campo.id]) continue;
    const v = valores[campo.id];
    if (campo.opcional && vacio(v)) continue;

    if (campo.tipo === "date") {
      if (!fechaValida(v)) errores[campo.id] = "fecha inválida";
    } else if (campo.tipo === "importe") {
      if (importeInvalido(v)) errores[campo.id] = "escríbelo sin separador de miles: 50000 o 50000,50";
    } else if (campo.tipo === "entero") {
      if (!ENTERO.test(String(v).trim())) errores[campo.id] = "debe ser un número entero";
    } else if (campo.tipo === "opciones") {
      if (!campo.opciones.includes(Number(v))) {
        const opts = campo.opciones;
        errores[campo.id] = `usa ${opts.slice(0, -1).join(", ")} o ${opts[opts.length - 1]}`;
      }
    } else if (campo.tipo === "fechas") {
      if (fechas(v).some((f) => !fechaValida(f))) errores[campo.id] = "fecha inválida";
    }
  }

  // Rango horario del motor (0-23) antes de la regla cruzada hora_inicio/hora_fin.
  if (!errores.hora_inicio && !(num(valores.hora_inicio) >= 0 && num(valores.hora_inicio) < 24)) {
    errores.hora_inicio = "debe estar entre 0 y 23";
  }
  if (!errores.hora_fin && !(num(valores.hora_fin) >= 0 && num(valores.hora_fin) <= 23)) {
    errores.hora_fin = "debe estar entre 0 y 23";
  }

  if (!errores.materialidad && num(valores.materialidad) <= 0) {
    errores.materialidad = "debe ser mayor que cero";
  }
  if (!errores.umbral_aprobacion && num(valores.umbral_aprobacion) <= 0) {
    errores.umbral_aprobacion = "debe ser mayor que cero";
  }

  const sinError = (...ids) => ids.every((id) => !errores[id]);

  if (sinError("ejercicio_inicio", "ejercicio_fin") &&
      valores.ejercicio_fin <= valores.ejercicio_inicio) {
    errores.ejercicio_fin = "debe ser posterior al inicio del ejercicio";
  }

  if (sinError("materialidad", "materialidad_ejecucion")) {
    const mat = num(valores.materialidad);
    const ejec = num(valores.materialidad_ejecucion);
    if (!(ejec > 0 && ejec <= mat)) errores.materialidad_ejecucion = "no puede superar la materialidad global";
  }

  if (sinError("materialidad_ejecucion", "umbral_insignificante")) {
    const ejec = num(valores.materialidad_ejecucion);
    const ins = num(valores.umbral_insignificante);
    if (!(ins > 0 && ins < ejec)) {
      errores.umbral_insignificante = "debe ser menor que la materialidad de ejecución";
    }
  }

  if (sinError("materialidad_ejecucion", "error_tolerable")) {
    const ejec = num(valores.materialidad_ejecucion);
    const tol = num(valores.error_tolerable);
    if (!(tol > 0 && tol <= ejec)) {
      errores.error_tolerable = "no puede superar la materialidad de ejecución";
    }
  }

  // El motor (motor/parametros.py) marca esta regla en hora_inicio, no en hora_fin.
  if (sinError("hora_inicio", "hora_fin") && num(valores.hora_inicio) >= num(valores.hora_fin)) {
    errores.hora_inicio = "debe ser anterior a la hora de fin";
  }

  if (sinError("ejercicio_inicio", "ejercicio_fin", "feriados")) {
    const lista = fechas(valores.feriados);
    if (lista.some((f) => f < valores.ejercicio_inicio || f > valores.ejercicio_fin)) {
      errores.feriados = "hay feriados fuera del ejercicio";
    }
  }

  return errores;
}

// Un trabajo que falla por parámetros debe decir por qué: arma la lista
// campo → motivo (el error del motor manda sobre la validación local del
// navegador) para mostrarla fuera del <details> plegado. `balance` no es
// un CAMPOS del bloque U pero también es un motivo de error del motor.
export function resumenErrores(erroresParametros = {}, erroresMotorPorCampo = {}, balanceError = "") {
  const resumen = [];
  for (const campo of CAMPOS) {
    const motivo = erroresMotorPorCampo[campo.id] || erroresParametros[campo.id];
    if (motivo) resumen.push({ campo: campo.id, etiqueta: campo.etiqueta, motivo });
  }
  if (balanceError) resumen.push({ campo: "balance", etiqueta: "Balance", motivo: balanceError });
  return resumen;
}

export function aEnvio(valores) {
  const salida = {};
  for (const campo of CAMPOS) {
    const v = valores[campo.id];
    switch (campo.tipo) {
      case "date":
      case "importe":
        salida[campo.id] = String(v).trim();
        break;
      case "entero":
      case "opciones":
        salida[campo.id] = Number(v);
        break;
      case "fechas":
        salida[campo.id] = fechas(v);
        break;
      case "casilla":
        salida[campo.id] = Boolean(v);
        break;
      default:
        break;
    }
  }
  return salida;
}
