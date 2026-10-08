// Ficha del encargo: los mismos campos, etiquetas y opciones que
// `ContextFields` de auditbrain-site/app/herramientas/context-controls.tsx.
// Ese archivo es TSX con componentes del sitio y no se puede copiar tal cual;
// se copian literalmente los textos y las opciones, y se pintan con controles
// nativos. Si el sitio cambia una opción, hay que cambiarla aquí.

export const contextLabels = {
  client: "Cliente / razón social",
  ruc: "Identificación fiscal / RUC",
  activity: "Actividad económica",
  year: "Ejercicio",
  cutoff: "Fecha de corte",
  visit: "Visita de auditoría",
  preparer: "Preparado por",
  reviewer: "Revisado por",
  firm: "Firma auditora",
  framework: "Marco contable",
  edition: "Edición / versión normativa aplicable",
  adoption: "Adopción local y vigencia por verificar",
  country: "País",
  currency: "Moneda (código de 3 letras)",
  reuseScope: "Reutilizar datos del encargo",
  deferredTax: "Aplica impuestos diferidos",
  logoCliente: "Logo de la compañía auditada",
};

// Tamaño máximo del logo del cliente (binario). El backend lo valida en
// ~1,2 MB de *data URI*; aquí se corta el archivo antes de leerlo.
const MAX_LOGO_BYTES = 1_200_000;

// Lee el logo elegido como *data URI* (PNG/JPG/SVG) y lo entrega por callback.
// El logo viaja dentro de la ficha (datos.logoCliente) y reemplaza al de ejemplo
// en el HTML del papel y en la portada del Excel/Word/PowerPoint.
function leerLogoCliente(file, cb) {
  if (!file) return;
  if (file.size > MAX_LOGO_BYTES) {
    alert("El logo debe ser una imagen PNG, JPG o SVG de menos de 1 MB.");
    return;
  }
  const r = new FileReader();
  r.onload = (e) => cb(String(e.target.result || ""));
  r.readAsDataURL(file);
}

const choices = {
  firm: [["Audit Consulting", "Auditconsulting · Audit Consulting Group"], ["Partner", "Partner Auditing Cía. Ltda."]],
  framework: [["NIIF para las PYMES", "NIIF para las PYMES"], ["NIIF completas", "NIIF completas"]],
  visit: [["Preliminar", "Preliminar"], ["Final", "Final"]],
  reuseScope: [
    ["all", "Todas las pruebas que heredan la ficha"],
    ["selected", "Varias pruebas seleccionadas"],
    ["one", "Solo una prueba"],
  ],
  adoption: [
    ["Adoptada y vigente para el ejercicio", "Adoptada y vigente para el ejercicio"],
    ["Adoptada; vigencia por verificar", "Adoptada; vigencia por verificar"],
    ["Emitida por el IASB; no adoptada localmente aún", "Emitida por el IASB; no adoptada localmente aún"],
    ["Por verificar en la SCVS", "Por verificar en la SCVS"],
    ["No aplica", "No aplica"],
  ],
};

// La edición aplicable depende del marco contable: NIIF para las PYMES tiene
// ediciones discretas (2ª/2015 y 3ª/2025); NIIF completas se libra por año.
const editionChoices = (fw) =>
  fw === "NIIF para las PYMES"
    ? [["2015", "2015 · 2ª edición"], ["2025", "2025 · 3ª edición"]]
    : [["2023", "2023"], ["2024", "2024"], ["2025", "2025"], ["2026", "2026"]];

// Conserva un valor ya guardado que no esté en la lista (p. ej. una edición escrita
// a mano antes) para no perderlo al mostrar el desplegable en fichas anteriores.
const withCurrent = (list, cur) =>
  cur && !list.some(([v]) => v === cur) ? [[String(cur), String(cur)], ...list] : list;

export function ContextFields({ value, onChange, keys = Object.keys(contextLabels) }) {
  const cambiar = (key, v) => onChange({ ...value, [key]: v });
  return (
    <div className="nf-ctx-grid">
      {keys.map((key) => {
        const base = key === "edition" ? editionChoices(value.framework) : choices[key];
        const opts = base && (key === "edition" || key === "adoption") ? withCurrent(base, value[key]) : base;
        return (
        <div className="nf-ctx-field" key={key}>
          <label htmlFor={"ctx-" + key}>{contextLabels[key]}</label>
          {key === "logoCliente" ? (
            <div className="nf-ctx-logo">
              {value[key] ? (
                <img src={value[key]} alt="Logo de la compañía auditada" className="nf-ctx-logo-preview" />
              ) : (
                <span className="nf-ctx-logo-vacio">
                  Sin logo — el papel usará el nombre de la compañía (en el HTML queda el logo de ejemplo solo en la demostración)
                </span>
              )}
              <div className="nf-ctx-logo-acciones">
                <input
                  id={"ctx-" + key}
                  type="file"
                  accept="image/png,image/jpeg,image/svg+xml"
                  onChange={(e) => leerLogoCliente(e.target.files && e.target.files[0], (uri) => cambiar(key, uri))}
                />
                {value[key] ? (
                  <button type="button" className="nf-ctx-logo-quitar" onClick={() => cambiar(key, "")}>
                    Quitar
                  </button>
                ) : null}
              </div>
            </div>
          ) : key === "deferredTax" ? (
            <label className="nf-ctx-check">
              <input
                id={"ctx-" + key}
                type="checkbox"
                checked={value[key] === true}
                onChange={(e) => cambiar(key, e.target.checked)}
              />{" "}
              Habilita las cédulas de impuesto diferido en las pruebas de este encargo
            </label>
          ) : opts ? (
            <select id={"ctx-" + key} value={value[key] || ""} onChange={(e) => cambiar(key, e.target.value)}>
              <option value="" disabled>
                Seleccione expresamente…
              </option>
              {opts.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          ) : (
            <input
              id={"ctx-" + key}
              required={key !== "adoption"}
              maxLength={key === "adoption" ? 1000 : key === "currency" ? 3 : 200}
              type={key === "cutoff" ? "date" : key === "year" ? "number" : "text"}
              value={value[key] ?? ""}
              onChange={(e) => cambiar(key, key === "currency" ? e.target.value.toUpperCase() : e.target.value)}
            />
          )}
        </div>
        );
      })}
    </div>
  );
}
