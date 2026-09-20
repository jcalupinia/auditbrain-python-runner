// Lógica pura de la ficha de diseño de una herramienta NIIF.
//
// Aislada de React/DOM para poder testearla con vitest (vitest.config.js corre
// en environment: "node"), igual que `aud/of/ofLogic.js`.
//
// Fuente de verdad del contenido: docs/pruebas/ESTRUCTURA_HERRAMIENTA.md
//   · Bloque 2 → requerimiento al cliente (ítems, formatos, obligatoriedad,
//     componentes y grupos de fuentes alternativas)
//   · Bloque 4 → salidas (cédulas y sus formatos)
//
// Esta entrega es SOLO la ficha de diseño: no hay motor de cálculo, ni carga
// de archivos del cliente, ni generación de Excel.

export const ESTADO_EN_DISENO = "en_diseño";

// Formatos de entrada del Bloque 2.1 del documento.
export const FORMATOS_ENTRADA = [
  { id: "xlsx", label: "Excel (.xlsx / .xls)" },
  { id: "csv", label: "CSV" },
  { id: "xml", label: "XML" },
  { id: "docx", label: "Word (.docx)" },
  { id: "pdf", label: "PDF" },
  { id: "imagen", label: "Imagen (png / jpg)" },
  { id: "zip", label: "ZIP" },
  { id: "txt", label: "TXT" },
];

// Formatos de salida del Bloque 3 (Excel y HTML son requisito duro; el HTML
// debe abrirse sin conexión).
export const FORMATOS_SALIDA = [
  { id: "excel", label: "Excel" },
  { id: "html", label: "HTML autónomo" },
  { id: "pdf", label: "PDF" },
  { id: "word", label: "Word" },
];

let contador = 0;
function nuevaClave(prefijo) {
  contador += 1;
  return `${prefijo}-${contador}`;
}

export function itemVacio() {
  return {
    key: nuevaClave("item"),
    que_se_pide: "",
    formatos: [],
    obligatorio: true,
    componentes: 1,
    grupo_alternativas: "",
  };
}

export function salidaVacia() {
  return { key: nuevaClave("salida"), nombre: "", formatos: ["excel"] };
}

export function fichaVacia() {
  return {
    id: null,
    nombre: "",
    rubro: "",
    norma: "",
    parrafo: "",
    items: [itemVacio()],
    salidas: [salidaVacia()],
  };
}

// Agrupa los ítems por su grupo de fuentes alternativas. Los ítems sin grupo
// no entran. Devuelve { nombreGrupo: [item, ...] }.
export function gruposAlternativos(items) {
  const grupos = {};
  (items || []).forEach((it) => {
    const g = String(it.grupo_alternativas || "").trim();
    if (!g) return;
    if (!grupos[g]) grupos[g] = [];
    grupos[g].push(it);
  });
  return grupos;
}

// Devuelve la lista de errores que impiden guardar la ficha. Vacía = válida.
export function validarFicha(ficha) {
  const errores = [];
  const f = ficha || {};

  if (!String(f.nombre || "").trim()) errores.push("Falta el nombre de la prueba.");
  if (!String(f.rubro || "").trim()) errores.push("Falta el rubro o ciclo al que pertenece.");
  if (!String(f.norma || "").trim()) errores.push("Falta la norma NIIF/NIC de referencia.");
  if (!String(f.parrafo || "").trim()) errores.push("Falta el párrafo de la norma.");

  const items = (f.items || []).filter((it) => String(it.que_se_pide || "").trim());
  if (items.length === 0) {
    errores.push("El requerimiento al cliente necesita al menos un ítem.");
  }
  items.forEach((it, i) => {
    if (!(it.formatos || []).length) {
      errores.push(`El ítem ${i + 1} no declara ningún formato aceptado.`);
    }
    if (!(Number(it.componentes) >= 1)) {
      errores.push(`El ítem ${i + 1} debe venir en 1 componente o más.`);
    }
  });

  // Un grupo de fuentes alternativas con un solo miembro no es alternativa:
  // o se le agrega la otra fuente, o el ítem no lleva grupo.
  Object.entries(gruposAlternativos(items)).forEach(([nombre, miembros]) => {
    if (miembros.length < 2) {
      errores.push(
        `El grupo de fuentes alternativas "${nombre}" tiene un solo ítem; necesita dos o más.`
      );
    }
  });

  const salidas = (f.salidas || []).filter((s) => String(s.nombre || "").trim());
  if (salidas.length === 0) {
    errores.push("La ficha necesita al menos una cédula de salida.");
  }
  salidas.forEach((s, i) => {
    if (!(s.formatos || []).length) {
      errores.push(`La salida ${i + 1} no declara ningún formato.`);
    }
  });

  return errores;
}

// Normaliza la ficha para guardarla: descarta filas vacías, recorta texto,
// asigna id si no lo tiene y la deja en estado "en diseño" (todavía no hay
// motor de cálculo: eso viene después).
export function prepararParaGuardar(ficha, ahoraIso) {
  const f = ficha || {};
  const ahora = ahoraIso || new Date().toISOString();
  return {
    id: f.id || `niif-${Date.parse(ahora) || Date.now()}`,
    estado: ESTADO_EN_DISENO,
    actualizado: ahora,
    nombre: String(f.nombre || "").trim(),
    rubro: String(f.rubro || "").trim(),
    norma: String(f.norma || "").trim(),
    parrafo: String(f.parrafo || "").trim(),
    items: (f.items || [])
      .filter((it) => String(it.que_se_pide || "").trim())
      .map((it) => ({
        que_se_pide: String(it.que_se_pide).trim(),
        formatos: [...(it.formatos || [])],
        obligatorio: !!it.obligatorio,
        componentes: Number(it.componentes) || 1,
        grupo_alternativas: String(it.grupo_alternativas || "").trim(),
      })),
    salidas: (f.salidas || [])
      .filter((s) => String(s.nombre || "").trim())
      .map((s) => ({ nombre: String(s.nombre).trim(), formatos: [...(s.formatos || [])] })),
  };
}

// Vuelve del formato guardado al formato editable (cada fila necesita su key
// de React y la ficha siempre muestra al menos una fila de cada tipo).
export function fichaParaEditar(guardada) {
  const base = fichaVacia();
  if (!guardada) return base;
  const items = (guardada.items || []).map((it) => ({ ...itemVacio(), ...it }));
  const salidas = (guardada.salidas || []).map((s) => ({ ...salidaVacia(), ...s }));
  return {
    ...base,
    ...guardada,
    items: items.length ? items : base.items,
    salidas: salidas.length ? salidas : base.salidas,
  };
}

// ---- Persistencia local ----
// Mientras no exista endpoint de backend para las fichas, quedan en el
// navegador del auditor. Todo va envuelto en try/catch: si el navegador
// bloquea el almacenamiento, la página sigue funcionando (sin historial).
const CLAVE = "ab_niif_fichas";

function store() {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

export function listarFichas() {
  const s = store();
  if (!s) return [];
  try {
    const raw = JSON.parse(s.getItem(CLAVE) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

// Inserta o reemplaza por id y devuelve la lista resultante (más reciente
// primero).
export function upsertFicha(lista, ficha) {
  const resto = (lista || []).filter((f) => f.id !== ficha.id);
  return [ficha, ...resto].sort((a, b) =>
    String(b.actualizado || "").localeCompare(String(a.actualizado || ""))
  );
}

export function guardarFicha(ficha) {
  const lista = upsertFicha(listarFichas(), ficha);
  const s = store();
  if (s) {
    try {
      s.setItem(CLAVE, JSON.stringify(lista));
    } catch {
      /* almacenamiento no disponible: la ficha vive solo en memoria */
    }
  }
  return lista;
}

export function borrarFicha(id) {
  const lista = listarFichas().filter((f) => f.id !== id);
  const s = store();
  if (s) {
    try {
      s.setItem(CLAVE, JSON.stringify(lista));
    } catch {
      /* ídem */
    }
  }
  return lista;
}
