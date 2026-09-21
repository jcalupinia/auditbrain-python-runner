import { useMemo, useState } from "react";

import { ContextFields } from "./ContextoEncargo";
import { METHODOLOGY_VERSION } from "./sitio/methodology.mjs";
import { checkUpload, coverage, gaps, parseItems } from "./sitio/requirement.mjs";
import { presentationExample } from "./sitio/tools/example.mjs";
import { calculationNotes } from "./sitio/tools/explanations.mjs";
import { buildHtml, buildWorkbook, sheetLabels, sheetNames, workbookSheets } from "./sitio/tools/exports.mjs";

/*
 * Recorrido metodológico de VNR — puerto de
 * auditbrain-site/app/herramientas/recorrido/studio.tsx.
 *
 * Todo lo que calcula o decide viene de las copias intactas del sitio
 * (carpeta sitio/): la cobertura con requirement.mjs, el caso con
 * example.mjs, las cédulas con exports.mjs. Aquí solo está la pantalla. Por
 * eso el recorrido del portal da exactamente lo que da el del sitio.
 *
 * Datos ficticios: no se guarda nada en el servidor.
 */

// El recorrido mide la cobertura con el MISMO motor que un encargo real, no
// con un contador de "4 de 4": componentes, fuentes alternativas del mismo
// grupo, formatos declarados y el rechazo que vuelve a abrir el hueco.
const ITEMS = parseItems([
  { text: "Inventario valorado al corte", instructions: "Cantidades, costo unitario, códigos y conciliación con el mayor.", formats: ["xlsx", "csv"], components: ["Bodega Quito", "Bodega Guayaquil"] },
  { text: "Lista de precios de venta", instructions: "Precio por ítem y condiciones de venta al corte.", formats: ["xlsx", "csv", "pdf"] },
  { text: "Costos de venta y terminación por ítem", instructions: "Costo necesario por ítem, con su sustento.", formats: ["xlsx", "csv"], group: "Costos necesarios de venta" },
  { text: "Estado de resultados con la base de asignación", instructions: "Alternativa a la anterior: sustente la población y la base de asignación del porcentaje.", formats: ["xlsx", "pdf"], group: "Costos necesarios de venta" },
  { text: "Políticas contables y deterioro registrado", instructions: "Método contable, saldos contabilizados y evidencia de estimaciones.", formats: ["pdf", "docx", "md"] },
]);

const CAMPOS = ["client", "country", "currency", "year", "visit", "cutoff", "preparer", "reviewer", "firm", "framework", "edition", "adoption", "reuseScope"];

const mostrar = (v) => (v && typeof v === "object" ? String(v.v ?? v.n ?? "") : String(v ?? ""));

function descargar(nombre, contenido, tipo) {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export default function RecorridoVNR() {
  const [ctx, setCtx] = useState(() => ({
    ...presentationExample().engagement,
    framework: "",
    edition: "",
    firm: "Audit Consulting",
  }));
  const [editing, setEditing] = useState(true);
  const [docs, setDocs] = useState([]);
  const [checked, setChecked] = useState(false);
  const [result, setResult] = useState(null);
  const [active, setActive] = useState(0);
  const [error, setError] = useState("");
  const [downloaded, setDownloaded] = useState(false);
  const [erase, setErase] = useState(false);
  const [kept, setKept] = useState(false);

  const estado = coverage(ITEMS, docs);
  const faltantes = gaps(ITEMS, docs);
  const cubiertos = estado.filter((c) => c.complete).length;
  const ready = !!ctx.framework && !!ctx.edition && faltantes.length === 0 && checked && !editing;

  const tocar = () => {
    setChecked(false);
    setResult(null);
    setDownloaded(false);
  };

  function cargar(item, comp) {
    setError("");
    try {
      checkUpload(ITEMS, item.id, comp || undefined, "ejemplo." + item.formats[0]);
      const id = item.id + ":" + (comp || "-");
      setDocs((old) => [...old.filter((d) => d.id !== id), { id, kind: "source", itemId: item.id, component: comp || undefined }]);
      tocar();
    } catch (e) {
      setError(e.message);
    }
  }

  function alternar(id) {
    setDocs((old) => old.map((d) => (d.id === id ? { ...d, state: d.state === "rechazado" ? undefined : "rechazado" } : d)));
    tocar();
  }

  function probarFormato(item) {
    setError("");
    try {
      checkUpload(ITEMS, item.id, item.components[0], "ejemplo.jpg");
      setError("El motor aceptó un formato que no debía: revise la declaración del ítem.");
    } catch (e) {
      setError("Así rechaza el motor un formato no declarado — " + e.message);
    }
  }

  const cambiarFicha = (v) => {
    setCtx(v);
    setDocs([]);
    setChecked(false);
    setResult(null);
    setDownloaded(false);
  };

  function procesar() {
    setError("");
    try {
      if (faltantes.length) throw Error("Cobertura incompleta. " + faltantes.join(" · "));
      if (!ready) throw Error("Complete la ficha, confirme la revisión y cierre la edición.");
      setResult({
        ...presentationExample(ctx),
        evidenceReview: {
          text: `Recorrido con ${cubiertos} de ${ITEMS.length} ítems cubiertos según el motor de cobertura, sobre datos sintéticos revisados por el usuario; no valida evidencia real.`,
        },
      });
      setActive(0);
      setDownloaded(false);
    } catch (e) {
      setError(e.message);
    }
  }

  function bajar(formato) {
    if (!result) return;
    try {
      if (formato === "xlsx")
        descargar("AuditBrain_VNR_EJEMPLO_v2.xlsx", buildWorkbook(result), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
      else descargar("AuditBrain_VNR_EJEMPLO_v2.html", buildHtml(result), "text/html;charset=utf-8");
      setDownloaded(true);
    } catch (e) {
      setError(e.message);
    }
  }

  const t = result || presentationExample({ ...ctx, framework: ctx.framework || "NIIF completas" });
  const cedulas = sheetLabels(t.definition);
  const nombres = sheetNames(t.definition);
  const hojas = useMemo(() => (result ? workbookSheets(result) : []), [result]);
  const sheet = hojas[active] || [];

  return (
    <div className="nf-recorrido">
      <header className="nf-rec-head">
        <div>
          <p className="nf-eyebrow">INVENTARIOS · RECORRIDO METODOLÓGICO</p>
          <h3>Valor neto de realización.</h3>
          <p className="muted">Ejemplo v2 · Manual y memoria {METHODOLOGY_VERSION}</p>
        </div>
      </header>

      <p className="nf-nota">
        <strong>Demostración interactiva con datos ficticios.</strong> Complete el recorrido sin guardar
        archivos en el servidor.
      </p>

      {/* ---------- Ficha común del encargo ---------- */}
      <section className="nf-rec-panel">
        <div className="nf-rec-row">
          <div>
            <p className="nf-eyebrow">FICHA COMÚN DEL ENCARGO</p>
            <h4>{ctx.client}</h4>
            <p>{ctx.visit} · Corte {ctx.cutoff} · {ctx.currency}</p>
            <p>Preparado por: {ctx.preparer} · Revisado por: {ctx.reviewer}</p>
            <p>{ctx.firm} · {ctx.framework || "Seleccione NIIF para las PYMES o NIIF completas"}</p>
          </div>
          <div className="nf-estudio-botones">
            <button type="button" className="btn sm" onClick={() => setEditing(!editing)}>Editar datos</button>
            <button type="button" className="btn sm primary" disabled={!ready} onClick={procesar}>Procesar</button>
            <button type="button" className="btn sm" disabled={!result} onClick={() => bajar("xlsx")}>Descargar Excel</button>
            <button type="button" className="btn sm" disabled={!result} onClick={() => bajar("html")}>Descargar HTML</button>
            <button type="button" className="btn sm" onClick={() => { setErase(true); setKept(false); }}>Encerar</button>
          </div>
        </div>
        {editing && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!ctx.framework || !ctx.edition || !ctx.visit || !ctx.reuseScope) {
                setError("Complete marco, edición, visita y alcance.");
                return;
              }
              setEditing(false);
              setError("");
            }}
          >
            <ContextFields value={ctx} onChange={cambiarFicha} keys={CAMPOS} />
            <p className="muted">
              En el ejemplo, el alcance queda documentado en la ficha. En un encargo real se vincula a una,
              varias o todas las pruebas. Cambiar la ficha exige volver a cargar y revisar las fuentes de esta
              demostración.
            </p>
            <button type="submit" className="btn sm primary">Confirmar ficha del ejemplo</button>
          </form>
        )}
      </section>

      {/* ---------- 1. Criterio ---------- */}
      <section className="nf-rec-panel">
        <h4>1. Criterio y requerimiento de información</h4>
        <p>{ctx.framework ? ctx.framework + " · " + (ctx.edition || "Edición pendiente") : "Seleccione primero el marco contable."}</p>
        <p>
          Investigar el tratamiento de inventarios del marco seleccionado, las NIA pertinentes y las políticas
          del cliente antes de aprobar el diseño. Estas referencias son puntos de consulta; no acreditan una
          revisión normativa.
        </p>
        <ul>
          {ctx.framework &&
            t.sources.map((s, i) => (
              <li key={i}>
                <a href={s.url} target="_blank" rel="noreferrer">{s.document}</a> · Pendiente de verificar
                norma, párrafo, vigencia y aplicación.
              </li>
            ))}
        </ul>
        <details>
          <summary>Ajustes, reversos e impuesto diferido</summary>
          <p>
            El cálculo muestra deterioro requerido menos deterioro registrado. Un ajuste negativo requiere
            evaluar la procedencia del reverso. El impuesto diferido requiere base fiscal, tasa aplicable,
            diferencia temporaria y criterios de reconocimiento. No se aplica una tasa universal ni se
            contabiliza automáticamente.
          </p>
          <p>
            Si esos tratamientos forman parte del encargo, deben añadirse sus fuentes, reglas, pruebas y
            cédulas antes de liberar la herramienta. Este recorrido ilustra el VNR básico.
          </p>
        </details>
      </section>

      {/* ---------- 2. Fuentes ---------- */}
      <section className="nf-rec-panel">
        <h4>2. Fuentes para procesar</h4>
        <p>
          Los botones corresponden a información requerida, no a extensiones. En este recorrido cargan datos
          sintéticos; no admiten archivos de clientes.
        </p>
        <p className="muted">
          Esta pantalla mide la cobertura con el mismo motor que un encargo real. Un ítem con componentes solo
          se cubre cuando llegan todos; dos ítems del mismo grupo son fuentes alternativas y basta una; un
          documento rechazado deja de cubrir y vuelve a abrir el hueco.
        </p>
        <div className="nf-rec-fuentes">
          {ITEMS.map((item) => {
            const c = estado.find((x) => x.id === item.id);
            const piezas = item.components.length ? item.components : [""];
            return (
              <div key={item.id} className="nf-rec-item">
                <h5>{item.text}</h5>
                <p className="muted">{item.instructions}</p>
                <ul className="nf-rec-decl">
                  <li><strong>Formatos aceptados:</strong> {item.formats.join(", ").toUpperCase()}</li>
                  <li>
                    <strong>Exigencia:</strong> {item.required ? "obligatorio" : "opcional"}
                    {item.group ? " · alternativa dentro de «" + item.group + "»" : ""}
                  </li>
                  <li><strong>Componentes:</strong> {item.components.length ? item.components.join(", ") : "entrega única"}</li>
                </ul>
                {piezas.map((comp) => {
                  const d = docs.find((x) => x.itemId === item.id && (x.component || "") === comp);
                  return (
                    <div key={item.id + comp} className="nf-rec-pieza">
                      <button type="button" className="btn sm" disabled={editing || !ctx.framework} onClick={() => cargar(item, comp)}>
                        {(d ? "Volver a cargar" : "Cargar ejemplo") + (comp ? " · " + comp : "")}
                      </button>
                      {d && (
                        <button type="button" className="btn sm" onClick={() => alternar(d.id)}>
                          {d.state === "rechazado" ? "Restituir" : "Rechazar"}
                        </button>
                      )}
                      <small>{d ? (d.state === "rechazado" ? "Rechazado · no cubre" : "Recibido") : "Pendiente"}</small>
                    </div>
                  );
                })}
                <small className={c?.complete ? "nf-ok" : "nf-rec-falta"}>
                  {c?.complete ? "Ítem cubierto" : "Falta: " + (c?.pending || []).join(", ")}
                </small>
                <div>
                  <button type="button" className="link" disabled={editing || !ctx.framework} onClick={() => probarFormato(item)}>
                    Probar un formato no admitido
                  </button>
                </div>
              </div>
            );
          })}
        </div>
        {faltantes.length > 0 && (
          <div className="nf-huecos">
            <strong>Lo que impide avanzar:</strong>
            <ul>{faltantes.map((g) => <li key={g}>{g}</li>)}</ul>
          </div>
        )}
        <p>
          {cubiertos} de {ITEMS.length} ítems cubiertos ·{" "}
          {faltantes.length ? "el motor bloquea el avance" : "requerimiento cubierto"}
        </p>
        <progress max={ITEMS.length} value={cubiertos} aria-label="Ítems cubiertos" style={{ width: "100%" }} />
        {faltantes.length === 0 && (
          <label className="nf-ctx-check">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => {
                setChecked(e.target.checked);
                setResult(null);
                setDownloaded(false);
              }}
            />{" "}
            He revisado los datos ficticios y entiendo que procesar esta demostración no valida una metodología
            para un cliente real.
          </label>
        )}
      </section>

      {error && <p role="alert" className="nf-error">{error}</p>}

      {/* ---------- 3. Cédulas ---------- */}
      <section className="nf-rec-panel">
        <h4>3. Cédulas y resultados</h4>
        <p>
          {result
            ? "Procesado · borrador de demostración. Las tarjetas corresponden a las hojas del Excel."
            : "Complete las fuentes y pulse Procesar. Las cédulas permanecerán pendientes hasta entonces."}
        </p>
        {result && (
          <div className="nf-rec-metricas">
            {[["Costo total", result.run.totals.cost], ["Deterioro requerido", result.run.totals.impairment], ["Ajuste propuesto", result.run.totals.adjustment]].map(([l, v]) => (
              <div key={l}><small>{l}</small><strong>{v}</strong></div>
            ))}
          </div>
        )}
        <div className="nf-rec-cedulas">
          {cedulas.map((label, i) => (
            <button
              key={label}
              type="button"
              disabled={!result}
              className={active === i && result ? "selected" : ""}
              onClick={() => setActive(i)}
            >
              <span>{String(i + 1).padStart(2, "0")}</span>
              <strong>{label}</strong>
              <small>{result ? "Ver cédula · borrador" : "Pendiente de procesar"}</small>
            </button>
          ))}
        </div>
        {result && (
          <article>
            <h5>{cedulas[active]} · {nombres[active]}</h5>
            <div className="nf-estudio-scroll nf-estudio-tabla">
              <table>
                <tbody>
                  {sheet.map((r, i) => (
                    <tr key={i}>
                      {r.map((v, j) => (
                        <td key={j}>
                          {mostrar(v)}
                          {v?.f && (
                            <details>
                              <summary>Fórmula auditable</summary>
                              <code>={v.f}</code>
                            </details>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="nf-nota">
              <strong>Cómo se prepara y calcula:</strong> {calculationNotes(result)[active]}
            </p>
          </article>
        )}
      </section>

      {/* ---------- 4. Descargar ---------- */}
      <section className="nf-rec-panel">
        <h4>4. Descargar, revisar y encerar</h4>
        <p>
          Excel y HTML usan la misma ficha, población y resultados procesados. El Excel contiene{" "}
          {cedulas.length} hojas enlazadas y fórmulas visibles. Conserve su descarga antes de limpiar. Esta
          demostración no guarda documentos en el servidor.
        </p>
        <div className="nf-estudio-botones">
          <button type="button" className="btn sm primary" disabled={!result} onClick={() => bajar("xlsx")}>Descargar Excel</button>
          <button type="button" className="btn sm" disabled={!result} onClick={() => bajar("html")}>Descargar HTML</button>
        </div>
        {downloaded && <p role="status">Descarga solicitada. Compruebe que el archivo abrió correctamente en su equipo.</p>}
      </section>

      {erase && (
        <div className="nf-rec-panel nf-rec-encerar" role="dialog" aria-label="Encerar el ejemplo de inventarios">
          <h4>Encerar el ejemplo de inventarios</h4>
          <p>
            Se quitarán las fuentes sintéticas y resultados de esta pantalla. Se conservará la ficha del encargo.
            Sus archivos descargados no se eliminan.
          </p>
          <label className="nf-ctx-check">
            <input type="checkbox" checked={kept} onChange={(e) => setKept(e.target.checked)} /> Conservo la
            descarga o acepto reiniciar el ejemplo sin resultados.
          </label>
          <div className="nf-estudio-botones">
            <button type="button" className="btn sm" onClick={() => setErase(false)}>Cancelar</button>
            <button
              type="button"
              className="btn sm peligro"
              disabled={!kept}
              onClick={() => {
                setDocs([]);
                setChecked(false);
                setResult(null);
                setDownloaded(false);
                setActive(0);
                setErase(false);
              }}
            >
              Confirmar encerado
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
