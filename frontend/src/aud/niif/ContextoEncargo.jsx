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
};

const choices = {
  firm: [["Audit Consulting", "Auditconsulting · Audit Consulting Group"], ["Partner", "Partner Auditing Cía. Ltda."]],
  framework: [["NIIF para las PYMES", "NIIF para las PYMES"], ["NIIF completas", "NIIF completas"]],
  visit: [["Preliminar", "Preliminar"], ["Final", "Final"]],
  reuseScope: [
    ["all", "Todas las pruebas que heredan la ficha"],
    ["selected", "Varias pruebas seleccionadas"],
    ["one", "Solo una prueba"],
  ],
};

export function ContextFields({ value, onChange, keys = Object.keys(contextLabels) }) {
  const cambiar = (key, v) => onChange({ ...value, [key]: v });
  return (
    <div className="nf-ctx-grid">
      {keys.map((key) => (
        <div className="nf-ctx-field" key={key}>
          <label htmlFor={"ctx-" + key}>{contextLabels[key]}</label>
          {key === "deferredTax" ? (
            <label className="nf-ctx-check">
              <input
                id={"ctx-" + key}
                type="checkbox"
                checked={value[key] === true}
                onChange={(e) => cambiar(key, e.target.checked)}
              />{" "}
              Habilita las cédulas de impuesto diferido en las pruebas de este encargo
            </label>
          ) : choices[key] ? (
            <select id={"ctx-" + key} value={value[key] || ""} onChange={(e) => cambiar(key, e.target.value)}>
              <option value="" disabled>
                Seleccione expresamente…
              </option>
              {choices[key].map(([v, l]) => (
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
      ))}
    </div>
  );
}
