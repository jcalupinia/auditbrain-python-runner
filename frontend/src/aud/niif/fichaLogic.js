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
// Las fichas se PERSISTEN EN EL BACKEND (`/api/v1/aud/niif/fichas`), no en el
// navegador: el circuito exige que quien marca una ficha como «probada» pueda
// ser alguien distinto de quien la diseñó, y con localStorage el revisor no
// vería nada. Aquí solo vive lo puro: validación, normalización, estados y la
// generación del encargo.
//
// Esta entrega sigue siendo SOLO la ficha de diseño y su circuito: no hay motor
// de cálculo, ni carga de archivos del cliente, ni generación de Excel.

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

// Normaliza la ficha para mandarla al backend: descarta filas vacías y recorta
// texto. `id`, `estado` y `actualizado` van por comodidad de la pantalla; el
// backend los ignora en el cuerpo, porque el estado lo gobierna él (ver
// backend/app/aud/niif/service.py).
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


// ---- Estados de la ficha ----
// Circuito cerrado, sin atajos (lo mismo que valida el backend en
// backend/app/aud/niif/service.py):
//   en diseño ──marcar probada──> probada ──generar código──> enviada
export const ESTADO_PROBADA = "probada";
export const ESTADO_ENVIADA = "enviada";

export const ETIQUETA_ESTADO = {
  [ESTADO_EN_DISENO]: "en diseño",
  [ESTADO_PROBADA]: "probada",
  [ESTADO_ENVIADA]: "enviada",
};

export function etiquetaEstado(estado) {
  return ETIQUETA_ESTADO[estado] || estado || "";
}

export function esEditable(ficha) {
  return (ficha?.estado || ESTADO_EN_DISENO) === ESTADO_EN_DISENO;
}

// El botón «Generar código para Claude» solo existe cuando alguien ya
// verificó que la prueba funciona.
export function puedeGenerarCodigo(ficha) {
  return ficha?.estado === ESTADO_PROBADA;
}

// ---- Lista en memoria ----
// La persistencia vive en el backend (`/api/v1/aud/niif/fichas`): las fichas
// son de la firma, no del navegador de quien las diseñó. Este helper solo
// mezcla la ficha recién guardada en la lista que ya tiene la pantalla, para
// no volver a pedir el listado completo tras cada guardado.
export function upsertFicha(lista, ficha) {
  const resto = (lista || []).filter((f) => f.id !== ficha.id);
  const clave = (f) => String(f.actualizado || f.updated_at || "");
  return [ficha, ...resto].sort((a, b) => clave(b).localeCompare(clave(a)));
}

// ---- Encargo para el asistente ----

// Convierte un texto libre en el fragmento de identificador que usa el
// catálogo AUD: mayúsculas, sin tildes, separado por guiones bajos (mismo
// molde que AUD.IMPUESTOS.OBLIGACIONES_FISCALES).
export function slugCatalogo(texto) {
  return String(texto || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

// Identificador de la herramienta dentro de frontend/src/aud/catalog.js.
export function idCatalogo(ficha) {
  return `AUD.${slugCatalogo(ficha?.rubro)}.${slugCatalogo(ficha?.nombre)}`;
}

// Nombre del paquete/carpeta de la herramienta (backend y frontend).
export function moduloCatalogo(ficha) {
  return slugCatalogo(ficha?.nombre).toLowerCase();
}

// "Valor neto de realización" -> "ValorNetoDeRealizacion" (componente React).
export function nombrePascal(texto) {
  return slugCatalogo(texto)
    .split("_")
    .filter(Boolean)
    .map((p) => p.charAt(0) + p.slice(1).toLowerCase())
    .join("");
}

// ídem en camelCase, para los nombres de archivo de lógica pura.
export function nombreCamel(texto) {
  const p = nombrePascal(texto);
  return p ? p.charAt(0).toLowerCase() + p.slice(1) : "";
}

export function fechaCorta(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : d.toISOString().slice(0, 10);
}

// Nombre sugerido para el .md descargable.
export function nombreArchivoEncargo(ficha) {
  const mod = moduloCatalogo(ficha).replace(/_/g, "-");
  return `encargo-${mod || "herramienta"}.md`;
}

function etiquetaFormato(opciones, id) {
  const f = opciones.find((o) => o.id === id);
  return f ? f.label : id;
}

function listaFormatos(opciones, ids) {
  return (ids || [])
    .map((x) => `${etiquetaFormato(opciones, x)} (\`${x}\`)`)
    .join(", ");
}

/**
 * Texto autosuficiente que el dueño copia y le pega a un asistente para que
 * implemente la herramienta. NO genera el código de la herramienta: genera el
 * encargo. Quien lo reciba no tiene esta conversación ni esta pantalla, así
 * que el texto lleva todo: dónde va, qué pide, qué produce, qué archivos
 * tocar y cuál es el contrato de la estructura.
 *
 * @param ficha  la ficha tal como la devuelve el backend
 * @param rubros el catálogo AUD (CATEGORIES) para resolver la etiqueta del ciclo
 */
export function textoEncargo(ficha, rubros) {
  const f = ficha || {};
  const id = idCatalogo(f);
  const mod = moduloCatalogo(f);
  const camel = nombreCamel(f.nombre);
  const pascal = nombrePascal(f.nombre);
  const prefijoHttp = mod.replace(/_/g, "-");
  const rubroCat = (rubros || []).find((c) => c.id === f.rubro);
  const rubroLabel = rubroCat ? rubroCat.label : f.rubro;
  const items = f.items || [];
  const salidas = f.salidas || [];
  const grupos = gruposAlternativos(items);
  const L = [];

  L.push(`# Encargo: implementar la herramienta «${f.nombre}»`);
  L.push("");
  L.push(
    "Eres el asistente que va a escribir esta herramienta de auditoría en el " +
      "repositorio `auditbrain-python-runner`. La ficha de abajo ya fue diseñada " +
      "y **probada** por el equipo de auditoría: tu trabajo es implementarla, no " +
      "rediseñarla. Si algo de la ficha te parece incompleto, pregúntalo antes de " +
      "inventarlo."
  );
  L.push("");

  L.push("## 1 · Dónde vive la herramienta");
  L.push("");
  L.push(`- **Ciclo / rubro del catálogo:** ${rubroLabel} (\`${f.rubro}\`)`);
  L.push(`- **Identificador de catálogo:** \`${id}\``);
  L.push(`- **Nombre de módulo derivado:** \`${mod}\``);
  L.push("");
  L.push(
    "Se registra en `frontend/src/aud/catalog.js`, dentro de la categoría " +
      `\`${f.rubro}\`. Si esa categoría todavía no tiene el arreglo \`tools\`, ` +
      "créalo. El identificador sigue el molde de los existentes " +
      "(`AUD.IMPUESTOS.OBLIGACIONES_FISCALES`, `AUD.MOTOR_BALANCES`):"
  );
  L.push("");
  L.push("```js");
  L.push("{");
  L.push(`  id: "${id}",`);
  L.push(`  label: "${f.nombre}",`);
  L.push("  description:");
  L.push(
    `    "Prueba de ${f.norma} ${f.parrafo}. Pide ${items.length} documento(s) al ` +
      `cliente y produce ${salidas.length} cédula(s).",`
  );
  L.push("}");
  L.push("```");
  L.push("");

  L.push("## 2 · Identificación de la prueba");
  L.push("");
  L.push(`- **Nombre:** ${f.nombre}`);
  L.push(`- **Rubro o ciclo:** ${rubroLabel}`);
  L.push(`- **Norma:** ${f.norma}`);
  L.push(`- **Párrafo:** ${f.parrafo}`);
  L.push("");

  L.push("## 3 · Requerimiento al cliente (bloque 2 de la estructura)");
  L.push("");
  L.push(
    "Cada ítem es un documento definido **por contenido, no por extensión**. " +
      "La herramienta debe aceptar cualquiera de los formatos declarados."
  );
  L.push("");
  items.forEach((it, i) => {
    L.push(`### Ítem ${i + 1} · ${it.que_se_pide}`);
    L.push("");
    L.push(`- **Formatos aceptados:** ${listaFormatos(FORMATOS_ENTRADA, it.formatos)}`);
    L.push(`- **Obligatorio:** ${it.obligatorio ? "sí" : "no (opcional)"}`);
    L.push(
      `- **Componentes esperados:** ${it.componentes}` +
        (Number(it.componentes) > 1
          ? " — puede llegar partido en varios archivos y hay que consolidarlos"
          : "")
    );
    L.push(
      `- **Grupo de fuentes alternativas:** ${
        it.grupo_alternativas ? `\`${it.grupo_alternativas}\`` : "ninguno"
      }`
    );
    L.push("");
  });

  if (Object.keys(grupos).length) {
    L.push("### Grupos de fuentes alternativas");
    L.push("");
    L.push(
      "Basta con recibir **una** de las fuentes de cada grupo para dar el " +
        "requerimiento por satisfecho; no se debe exigir todas:"
    );
    L.push("");
    Object.entries(grupos).forEach(([nombre, miembros]) => {
      L.push(`- **${nombre}**: ${miembros.map((m) => m.que_se_pide).join(" · o · ")}`);
    });
    L.push("");
  }

  L.push("## 4 · Salidas (bloque 4 de la estructura)");
  L.push("");
  L.push("Toda hoja entregada en el Excel tiene su cédula:");
  L.push("");
  salidas.forEach((s, i) => {
    L.push(`${i + 1}. **${s.nombre}** — formatos: ${listaFormatos(FORMATOS_SALIDA, s.formatos)}`);
  });
  L.push("");
  L.push(
    "Recordatorio del contrato: si se declara HTML, debe abrirse y funcionar " +
      "**sin conexión a internet**, sin depender de recursos remotos."
  );
  L.push("");

  L.push("## 5 · Archivos a crear o modificar");
  L.push("");
  L.push(
    "Sigue el patrón de los módulos AUD que ya existen: " +
      "`backend/app/aud/obligaciones_fiscales/` es el más completo y " +
      "`backend/app/aud/motor_balances/` es el mínimo."
  );
  L.push("");
  L.push("**Crear:**");
  L.push("");
  L.push(`- \`backend/app/aud/${mod}/__init__.py\` — docstring del módulo`);
  L.push(`- \`backend/app/aud/${mod}/models.py\` — modelo SQLAlchemy del encargo`);
  L.push(`- \`backend/app/aud/${mod}/schemas.py\` — schemas Pydantic de la API`);
  L.push(`- \`backend/app/aud/${mod}/service.py\` — motor de cálculo determinista`);
  L.push(
    `- \`backend/app/aud/${mod}/router.py\` — endpoints con prefijo ` +
      `\`/aud/${prefijoHttp}\`, protegidos con \`require_staff\``
  );
  L.push(
    `- \`backend/app/aud/${mod}/excel_assembler.py\` — armado de las ` +
      `${salidas.length} cédula(s) declaradas arriba`
  );
  L.push(`- \`frontend/src/aud/${mod}/${pascal}Tool.jsx\` — la pantalla de la herramienta`);
  L.push(
    `- \`frontend/src/aud/${mod}/${camel}Logic.js\` — lógica pura, separada del ` +
      "DOM para poder testearla con vitest (igual que `frontend/src/aud/of/ofLogic.js`)"
  );
  L.push(`- \`frontend/src/aud/${mod}/${camel}Logic.test.js\` — pruebas de esa lógica`);
  L.push(`- \`tests/test_aud_${mod}_router.py\` — pruebas de los endpoints`);
  L.push(`- \`tests/test_aud_${mod}_service.py\` — pruebas del motor de cálculo`);
  L.push("");
  L.push("**Modificar:**");
  L.push("");
  L.push(
    `- \`frontend/src/aud/catalog.js\` — añadir la entrada \`${id}\` en la ` +
      `categoría \`${f.rubro}\``
  );
  L.push(
    `- \`frontend/src/aud/ToolCatalog.jsx\` — enlazar \`${id}\` con ` +
      `\`${pascal}Tool.jsx\``
  );
  L.push("- `frontend/src/api.js` — funciones cliente de los endpoints nuevos");
  L.push(
    "- `backend/app/api/__init__.py` — importar el router y montarlo con " +
      "`include_router`, junto a los demás routers AUD"
  );
  L.push(
    "- `backend/app/db/session.py` — importar el módulo de modelos dentro de " +
      "`init_db()` para que `Base.metadata.create_all` cree la tabla"
  );
  L.push("");

  L.push("## 6 · Contrato de la estructura");
  L.push("");
  L.push(
    "La estructura común de toda herramienta de auditoría está en " +
      "**`docs/pruebas/ESTRUCTURA_HERRAMIENTA.md`**. Es el contrato: lo fijo es " +
      "esa estructura y lo único variable es lo que declara esta ficha (qué se " +
      "le pide al cliente y qué salidas produce). Léelo antes de escribir código, " +
      "en particular el bloque 2 (requerimiento y formatos aceptados), el bloque 3 " +
      "(acciones: editar, subir, procesar, descargar Excel y HTML, encerar) y el " +
      "bloque 4 (salidas)."
  );
  L.push("");
  L.push(
    "**Fuera de alcance:** cambiar esta ficha, tocar el catálogo de otro ciclo o " +
      "modificar herramientas existentes."
  );
  L.push("");

  L.push("---");
  L.push("");
  L.push(
    `Ficha \`#${f.id}\` · diseñada por ${f.autor_email || "—"}` +
      (f.probada_por_email
        ? ` · probada por ${f.probada_por_email} el ${fechaCorta(f.probada_en)}`
        : "")
  );

  return L.join("\n");
}
