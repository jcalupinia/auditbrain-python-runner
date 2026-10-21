// Opciones del formulario del robot del SRI. Copiadas de la app de escritorio
// (aplicacion.py, pestaña "Descarga de Comprobantes"): son las etiquetas que el
// portal del SRI acepta en sus selects. "Todos" NO existe en el portal: el
// robot falla al no poder seleccionar el tipo en Recibidos.
export const TIPOS_POR_ORIGEN = {
  Recibidos: ["Facturas", "Retenciones", "Notas de crédito", "Notas de débito", "Liquidación de compra"],
  Emitidos: ["Facturas", "Liquidación de compra", "Retenciones", "Notas de crédito", "Notas de débito", "Guía de remisión"],
};

export const ESTADOS_EMITIDOS = ["Autorizados", "No autorizados"];

export function tiposDe(origen) {
  return TIPOS_POR_ORIGEN[origen] || TIPOS_POR_ORIGEN.Recibidos;
}

// Al cambiar de origen, conserva el tipo si sigue siendo válido; si no, el primero.
export function tipoValido(origen, tipo) {
  const lista = tiposDe(origen);
  return lista.includes(tipo) ? tipo : lista[0];
}
