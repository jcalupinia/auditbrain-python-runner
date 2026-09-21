import { useRef, useState } from "react";

import { ContextFields } from "./ContextoEncargo";
import {
  ESTADOS,
  adjuntarExterno,
  confirmarDiseno,
  importarDiagnostico,
  nuevoCaso,
  paquete,
  papelReconstruido,
} from "./reconstruccion";
import { extractFile } from "./sitio/console/extract.mjs";
import { modelPreference } from "./sitio/reconstruction/protocol.ts";
import { catalog } from "./sitio/tools/domain.mjs";
import { buildHtml, buildWorkbook } from "./sitio/tools/exports.mjs";

/*
 * Reconstruir Excel — puerto de auditbrain-site/app/reconstruir/studio.tsx.
 *
 * Mismo circuito que el sitio: original → paquete para la IA → diagnóstico
 * (JSON) → el auditor confirma el diseño → Excel y HTML reconstruidos como
 * borrador, o un Excel hecho fuera que se adjunta.
 *
 * Diferencias deliberadas: el expediente vive en la pantalla (no se guarda en
 * servidor, como la consola) y la IA es la que el auditor elija — Claude,
 * ChatGPT u otra —: se le entrega el paquete y se importa lo que devuelve.
 */

const CAMPOS = ["framework", "edition", "country", "year", "cutoff", "currency", "visit"];

async function sha256(bytes) {
  const h = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(h)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

function guardar(nombre, contenido, tipo) {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

// Vista del diseño propuesto: puerto de `DesignPreview` del sitio.
function VistaDiseno({ design }) {
  const d = design.kind === "custom" ? design.definition : catalog[design.kind];
  return (
    <details>
      <summary>Revisar campos, fórmulas y datos propuestos</summary>
      <p>{design.parameters.basis}</p>
      <div className="nf-estudio-scroll nf-estudio-tabla">
        <table>
          <thead><tr><th>Campo</th><th>Descripción</th><th>Tipo</th></tr></thead>
          <tbody>{d.fields.map((f) => <tr key={f.key}><td>{f.key}</td><td>{f.label}</td><td>{f.type}</td></tr>)}</tbody>
        </table>
      </div>
      <div className="nf-estudio-scroll nf-estudio-tabla">
        <table>
          <thead><tr>{["Resultado", "Operación", "Entrada A", "Entrada B", "Decimales"].map((x) => <th key={x}>{x}</th>)}</tr></thead>
          <tbody>{d.rules.map((r) => <tr key={r.key}><td>{r.label}</td><td>{r.op}</td><td>{r.a}</td><td>{r.b}</td><td>{r.precision}</td></tr>)}</tbody>
        </table>
      </div>
      {design.parameters.buckets?.length > 0 && (
        <ul>{design.parameters.buckets.map((b, i) => <li key={i}>Mora {b.min} a {b.max ?? "sin límite"} días · tasa {b.rate}</li>)}</ul>
      )}
      {design.rows.length > 0 && (
        <>
          <p className="muted">Vista de las primeras 10 filas propuestas.</p>
          <div className="nf-estudio-scroll nf-estudio-tabla">
            <table>
              <thead><tr>{d.fields.map((f) => <th key={f.key}>{f.label}</th>)}</tr></thead>
              <tbody>
                {design.rows.slice(0, 10).map((r, i) => (
                  <tr key={i}>{d.fields.map((f) => <td key={f.key}>{String(r[f.key] ?? "Pendiente")}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </details>
  );
}

export default function ReconstruirExcel() {
  const [ctx, setCtx] = useState({ country: "Ecuador", currency: "USD", visit: "Final", framework: "", edition: "", year: "", cutoff: "" });
  const [tax, setTax] = useState(false);
  const [model, setModel] = useState("Otro modelo");
  const [caso, setCaso] = useState(null);
  const [extraction, setExtraction] = useState(null);
  const [respuesta, setRespuesta] = useState("");
  const [confirmado, setConfirmado] = useState(false);
  const [comentario, setComentario] = useState("");
  const [papel, setPapel] = useState(null);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState("");
  const pickerOriginal = useRef(null);
  const pickerExterno = useRef(null);
  const pickerRespuesta = useRef(null);

  async function paso(etiqueta, fn) {
    setOcupado(etiqueta);
    setError("");
    setAviso("");
    try {
      await fn();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setOcupado("");
    }
  }

  const leerArchivo = async (f) => {
    const bytes = new Uint8Array(await f.arrayBuffer());
    const [huella, ext] = await Promise.all([sha256(bytes), extractFile(bytes, f.name)]);
    return { huella, ext };
  };

  function abrirCaso(f) {
    paso("Leyendo el original…", async () => {
      for (const k of CAMPOS) if (!String(ctx[k] || "").trim()) throw Error("Complete marco, edición, país, ejercicio, corte, moneda y visita.");
      if (String(ctx.cutoff).slice(0, 4) !== String(ctx.year)) throw Error("La fecha de corte debe corresponder al ejercicio.");
      const { huella, ext } = await leerArchivo(f);
      setExtraction(ext);
      setCaso(nuevoCaso({ context: { ...ctx, year: String(ctx.year) }, tax, model, original: { name: f.name, sha256: huella }, extraction: ext, actor: "auditor" }));
      setPapel(null);
      setRespuesta("");
    });
  }

  function importar() {
    paso("Validando el diagnóstico…", async () => {
      setCaso(importarDiagnostico(caso, respuesta));
      setAviso("Diagnóstico importado. Revíselo antes de confirmar el diseño.");
    });
  }

  function confirmar() {
    paso("Confirmando…", async () => {
      setCaso(confirmarDiseno(caso, { confirmed: confirmado, comment: comentario, actor: "auditor" }));
    });
  }

  function reconstruir() {
    paso("Generando…", async () => {
      const p = papelReconstruido(caso);
      setPapel(p);
      setCaso({ ...caso, state: "RECONSTRUIDA", revision: caso.revision + 1, history: [...caso.history, { event: "Excel y HTML reconstruidos como borradores", at: new Date().toISOString(), actor: "auditor" }] });
    });
  }

  function adjuntar(f) {
    paso("Leyendo la versión externa…", async () => {
      const { huella, ext } = await leerArchivo(f);
      setCaso(adjuntarExterno(caso, { name: f.name, sha256: huella, extraction: ext }));
    });
  }

  const r = caso;
  const review = r?.review;

  return (
    <div className="nf-recon">
      <p className="nf-eyebrow">RECONSTRUIR EXCEL</p>
      <h3>Revisar y reconstruir una prueba Excel existente</h3>
      <p className="nf-nota">
        El original se lee en su navegador y se conserva sin cambios. La IA que usted elija diagnostica; usted
        confirma el diseño; AuditBrain reconstruye con su motor determinista. Todo sale como <strong>borrador</strong>.
      </p>

      {/* ---------- 1. Contexto y original ---------- */}
      <section className="nf-rec-panel">
        <h4>1. Contexto del encargo y Excel original</h4>
        <ContextFields value={ctx} onChange={setCtx} keys={CAMPOS} />
        <div className="nf-rec-row">
          <label className="nf-ctx-check">
            <input type="checkbox" checked={tax} onChange={(e) => setTax(e.target.checked)} /> La revisión incluye
            legislación tributaria (exigirá sustento TRIBUTARIO)
          </label>
          <label className="nf-ctx-field">
            Modelo preferido
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {modelPreference.options.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
        </div>
        <input ref={pickerOriginal} type="file" hidden accept=".xlsx" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) abrirCaso(f); }} />
        <button type="button" className="btn sm primary" disabled={!!ocupado} onClick={() => pickerOriginal.current?.click()}>
          {r ? "Empezar con otro original" : "Seleccionar el Excel original (.xlsx)"}
        </button>
        {r && (
          <p className="muted">
            {r.original.name} · {r.original.sheets.length} hojas · {r.original.formulaCount} fórmulas · SHA-256{" "}
            <code>{r.original.sha256}</code>
          </p>
        )}
      </section>

      {ocupado && <p className="muted">{ocupado}</p>}
      {error && <p role="alert" className="nf-error">{error}</p>}
      {aviso && <p role="status" className="nf-ok">{aviso}</p>}

      {r && (
        <>
          <p className="nf-estado">Estado: <strong>{ESTADOS[r.state]}</strong> · revisión {r.revision}</p>

          {/* ---------- 2. Paquete para la IA ---------- */}
          <section className="nf-rec-panel">
            <h4>2. Paquete para la IA</h4>
            <p>
              Entregue el paquete a la IA (Claude, ChatGPT u otra). Contiene las instrucciones de AuditBrain y la
              lectura del original, marcada como contenido no confiable. La IA debe devolver un archivo{" "}
              <code>revision-auditbrain.json</code>.
            </p>
            <div className="nf-estudio-botones">
              <button type="button" className="btn sm" onClick={() => guardar("paquete-revision-auditbrain.json", JSON.stringify(paquete(r, extraction), null, 2), "application/json")}>
                Descargar paquete
              </button>
              <button
                type="button"
                className="btn sm"
                onClick={() => navigator.clipboard.writeText(paquete(r, extraction).instructions).then(() => setAviso("Instrucciones copiadas."), () => setError("No se pudo copiar; use «Descargar paquete»."))}
              >
                Copiar instrucciones
              </button>
            </div>
          </section>

          {/* ---------- 3. Diagnóstico ---------- */}
          {["EN_REVISION", "DIAGNOSTICO"].includes(r.state) && (
            <section className="nf-rec-panel">
              <h4>3. Importar el diagnóstico</h4>
              <input ref={pickerRespuesta} type="file" hidden accept=".json,application/json" onChange={async (e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) setRespuesta(await f.text()); }} />
              <div className="nf-estudio-botones">
                <button type="button" className="btn sm" onClick={() => pickerRespuesta.current?.click()}>Cargar revision-auditbrain.json</button>
              </div>
              <label className="nf-ctx-field">
                o pegue aquí el contenido
                <textarea rows={6} value={respuesta} onChange={(e) => setRespuesta(e.target.value)} spellCheck={false} />
              </label>
              <button type="button" className="btn sm primary" disabled={!respuesta.trim() || !!ocupado} onClick={importar}>
                Importar diagnóstico
              </button>
            </section>
          )}

          {review && (
            <section className="nf-rec-panel">
              <h4>Diagnóstico recibido</h4>
              <p className="muted">{r.provenance}</p>
              <p>{review.summary}</p>
              <h5>Cobertura por hoja</h5>
              <ul>{review.coverage.map((c) => <li key={c.sheet}>{c.sheet} · {c.reviewed ? "revisada" : "no revisada"} · {c.notes}</li>)}</ul>
              <h5>Hallazgos</h5>
              <div className="nf-estudio-scroll nf-estudio-tabla">
                <table>
                  <thead><tr><th>Id</th><th>Categoría</th><th>Estado</th><th>Ubicación</th><th>Observación</th><th>Corrección</th><th>Fuentes</th></tr></thead>
                  <tbody>
                    {review.findings.map((f) => (
                      <tr key={f.id}><td>{f.id}</td><td>{f.category}</td><td>{f.status}</td><td>{f.location}</td><td>{f.observation}</td><td>{f.correction}</td><td>{f.sourceIds.join(", ")}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <h5>Fuentes</h5>
              <ul>
                {review.sources.map((s) => (
                  <li key={s.id}>
                    {s.id} · {s.category} · {s.organization} · {s.document} · {s.section} ·{" "}
                    <a href={s.url} target="_blank" rel="noreferrer">{s.url}</a>
                  </li>
                ))}
              </ul>
              <h5>Cambios propuestos</h5>
              <ul>{review.changes.map((c, i) => <li key={i}>{c.schedule}: {c.action} — {c.reason}</li>)}</ul>
              {review.limitations.length > 0 && (
                <>
                  <h5>Limitaciones</h5>
                  <ul>{review.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
                </>
              )}
              {review.design ? (
                <VistaDiseno design={review.design} />
              ) : (
                <p className="nf-nota">El diagnóstico no trae diseño determinista: tras confirmar, adjunte el Excel reconstruido fuera.</p>
              )}
            </section>
          )}

          {/* ---------- 4. Confirmar diseño ---------- */}
          {r.state === "DIAGNOSTICO" && (
            <section className="nf-rec-panel">
              <h4>4. Confirmar el diseño</h4>
              <label className="nf-ctx-check">
                <input type="checkbox" checked={confirmado} onChange={(e) => setConfirmado(e.target.checked)} /> Revisé el
                diagnóstico, sus fuentes y el diseño propuesto. Esto no es la aprobación final del papel.
              </label>
              <label className="nf-ctx-field">
                Fundamento de la confirmación (mínimo 15 caracteres)
                <textarea rows={3} value={comentario} maxLength={4000} onChange={(e) => setComentario(e.target.value)} />
              </label>
              <button type="button" className="btn sm primary" disabled={!!ocupado} onClick={confirmar}>Confirmar diseño</button>
            </section>
          )}

          {/* ---------- 5. Reconstruir ---------- */}
          {["DISENO_CONFIRMADO", "RECONSTRUIDA"].includes(r.state) && (
            <section className="nf-rec-panel">
              <h4>5. Reconstrucción</h4>
              {r.approval && <p className="muted">Diseño confirmado por {r.approval.by} · {r.approval.comment}</p>}
              {review?.design ? (
                <>
                  <button type="button" className="btn sm primary" disabled={!!ocupado} onClick={reconstruir}>
                    {papel ? "Volver a generar" : "Generar Excel y HTML reconstruidos"}
                  </button>
                  {papel && (
                    <>
                      <p>
                        {papel.plantilla ? "Plantilla con fórmulas, sin datos." : "Datos calculados con el motor determinista."}
                        {papel.run && ` Totales: ${Object.entries(papel.run.totals).map(([k, v]) => `${k} ${v}`).join(" · ")}.`}
                      </p>
                      <div className="nf-estudio-botones">
                        <button type="button" className="btn sm" onClick={() => guardar(`RECONSTRUIDA_${papel.kind}.xlsx`, buildWorkbook(papel.snapshot, papel.plantilla), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}>
                          Descargar Excel
                        </button>
                        <button type="button" className="btn sm" onClick={() => guardar(`RECONSTRUIDA_${papel.kind}.html`, buildHtml(papel.snapshot, papel.plantilla), "text/html;charset=utf-8")}>
                          Descargar HTML
                        </button>
                      </div>
                    </>
                  )}
                </>
              ) : r.state === "DISENO_CONFIRMADO" ? (
                <>
                  <input ref={pickerExterno} type="file" hidden accept=".xlsx" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) adjuntar(f); }} />
                  <button type="button" className="btn sm primary" disabled={!!ocupado} onClick={() => pickerExterno.current?.click()}>
                    Adjuntar el Excel reconstruido (.xlsx)
                  </button>
                </>
              ) : (
                <div>
                  <p>{r.result.mode} · {r.artifacts.xlsx.name} · {r.result.formulaCount} fórmulas · SHA-256 <code>{r.artifacts.xlsx.sha256}</code></p>
                  <ul>{r.result.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
                </div>
              )}
            </section>
          )}

          <details className="nf-rec-panel">
            <summary>Historial del expediente</summary>
            <ul>{r.history.map((h, i) => <li key={i}>{h.at} · {h.actor} · {h.event}</li>)}</ul>
          </details>
        </>
      )}
    </div>
  );
}
