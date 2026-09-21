// Lógica pura del «Estudio de la prueba» (sin React, para poder probarla).
//
// Regla de diseño: aquí NO se decide qué ítems ni qué componentes tiene una
// ficha. Eso lo decide el backend (`estudio.items_de_ficha`) y llega en la
// respuesta de cobertura. Si el frontend lo recalculara, habría una tercera
// copia de la regla que puede divergir de las otras dos.

export const RECIBIDO = "recibido";
export const RECHAZADO = "rechazado";

// Clave de una marca: ítem y componente. Un ítem sin componentes usa "".
export const claveMarca = (itemId, componente = "") => `${itemId}|${componente}`;

// Las marcas del auditor → los documentos que entiende el backend. Lo que no
// está marcado no se envía: no recibido es la ausencia de documento.
export function documentosDesdeMarcas(marcas) {
  return Object.entries(marcas || {})
    .filter(([, estado]) => estado === RECIBIDO || estado === RECHAZADO)
    .map(([clave, estado]) => {
      const [itemId, componente] = clave.split("|");
      const doc = { kind: "source", itemId };
      if (componente) doc.component = componente;
      if (estado === RECHAZADO) doc.state = RECHAZADO;
      return doc;
    });
}

// Ciclo de una marca al pulsarla: nada → recibido → rechazado → nada.
export function siguienteMarca(actual) {
  if (!actual) return RECIBIDO;
  if (actual === RECIBIDO) return RECHAZADO;
  return undefined;
}

// JSON escrito a mano por el auditor → objeto, con un mensaje que diga en
// qué recuadro está el error.
export function parsearJson(texto, recuadro) {
  const limpio = String(texto || "").trim();
  if (!limpio) throw new Error(`El recuadro «${recuadro}» está vacío.`);
  try {
    return JSON.parse(limpio);
  } catch (e) {
    throw new Error(`El recuadro «${recuadro}» no es JSON válido: ${e.message}`);
  }
}

// Columnas de una tabla de resultados: la unión de claves de todas las filas,
// en el orden en que aparecen. El motor no garantiza que todas las filas
// traigan las mismas claves.
export function columnas(filas) {
  const vistas = [];
  for (const f of filas || []) {
    for (const k of Object.keys(f)) if (!vistas.includes(k)) vistas.push(k);
  }
  return vistas;
}

// Caso de ejemplo: arrendamiento NIIF 16, el mismo que
// tests/test_aud_niif_motor.py contrasta contra la fórmula cerrada. Sirve para
// que el auditor vea el motor funcionando antes de pegar su propia definición.
export const EJEMPLO_NIIF16 = {
  definicion: {
    id: "custom",
    name: "Arrendamientos NIIF 16",
    area: "Arrendamientos",
    fields: [
      { key: "id", label: "Contrato", type: "text" },
      { key: "pago", label: "Pago por período", type: "number" },
      { key: "tasa", label: "Tasa incremental", type: "number" },
      { key: "n", label: "Períodos", type: "number" },
      { key: "directos", label: "Costos directos iniciales", type: "number" },
    ],
    series: {
      count: "n",
      backward: [
        { key: "pendiente", label: "Saldo más pago", op: "add", a: "@apertura", b: "pago", precision: 6 },
        { key: "factor", label: "Uno más la tasa", op: "add", a: "tasa", b: "#1", precision: 6 },
        { key: "apertura", label: "Pasivo al inicio del período", op: "divide", a: "pendiente", b: "factor", precision: 6 },
      ],
      forward: [
        { key: "interes", label: "Interés del período", op: "multiply", a: "apertura", b: "tasa", precision: 2 },
        { key: "con_interes", label: "Pasivo más interés", op: "add", a: "apertura", b: "interes", precision: 6 },
        { key: "cierre", label: "Pasivo al cierre", op: "subtract", a: "con_interes", b: "pago", precision: 2 },
        { key: "activo_inicial", label: "Activo por derecho de uso inicial", op: "add", a: "^apertura", b: "directos", precision: 2 },
        { key: "depreciacion", label: "Depreciación del período", op: "divide", a: "^activo_inicial", b: "periodos", precision: 2 },
        { key: "acumulada", label: "Depreciación acumulada", op: "multiply", a: "depreciacion", b: "periodo", precision: 2 },
        { key: "activo", label: "Activo al cierre", op: "subtract", a: "^activo_inicial", b: "acumulada", precision: 2 },
      ],
    },
    rules: [
      { key: "pasivo_inicial", label: "Pasivo en el reconocimiento", op: "add", a: "apertura_inicial", b: "#0", precision: 2 },
      { key: "activo_reconocido", label: "Activo en el reconocimiento", op: "add", a: "pasivo_inicial", b: "directos", precision: 2 },
      { key: "interes_plazo", label: "Interés total del plazo", op: "add", a: "interes_total", b: "#0", precision: 2 },
    ],
    control: "pago",
    primary: "pasivo_inicial",
  },
  filas: [{ id: "L-001", pago: "10000", tasa: "0.06", n: "5", directos: "1200" }],
};
