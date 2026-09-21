import { useRef, useState } from "react";

import { MAX_FILE, brief, extractFile } from "./sitio/console/extract.mjs";

/*
 * Consola de archivos — la capa de inspección de
 * auditbrain-site/app/consola/studio.tsx.
 *
 * La lectura la hace `extract.mjs` del sitio, sin tocar: hojas, fórmulas con
 * su valor guardado, texto de Word y PDF, contenido de ZIP, advertencias.
 *
 * Diferencia deliberada con el sitio: aquí el archivo NO se sube a ningún
 * servidor. Se lee en el navegador del auditor y desaparece al cerrar la
 * pestaña. Para una herramienta que inspecciona papeles de clientes, es lo
 * más prudente.
 *
 * Lo que NO se replica, y por qué:
 * - el chat con IA sobre los archivos: el sitio usa los modelos de ChatGPT;
 *   el portal ya tiene su pestaña «Chat» con sus propios proveedores;
 * - el puente en vivo con ChatGPT: solo tiene sentido dentro de ChatGPT.
 */

const statusName = {
  extracted: "Contenido extraído",
  partial: "Revisión parcial",
  vision_pending: "Lectura visual pendiente",
  unsupported: "No procesado",
  error: "No se pudo procesar",
};

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function guardar(nombre, contenido, tipo) {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

async function sha256(bytes) {
  const h = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(h)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

// Informe de la revisión: misma presentación que el del sitio, sin la
// conversación (aquí no hay chat).
function exportarInforme(titulo, archivos) {
  const filas = archivos
    .map((f) => {
      const b = f.resultado ? brief(f.resultado) : null;
      return `<tr><td>${esc(f.nombre)}</td><td>${esc(f.error ? "No se pudo procesar: " + f.error : statusName[b.status])}</td><td>${esc(b?.formulaCount ?? "")}</td><td>${esc(f.sha256)}</td></tr>`;
    })
    .join("");
  guardar(
    "AuditBrain-inspeccion-archivos.html",
    `<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(titulo)}</title><style>body{font:16px/1.6 system-ui;margin:0;background:#eef2f6;color:#17283b}header{padding:36px;background:#102d50;color:white}main{max-width:1050px;margin:30px auto;padding:24px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;border:1px solid #ced8df;text-align:left;overflow-wrap:anywhere}@media print{body{background:white}}</style><header><small>AUDIT CONSULTING GROUP · AUDITBRAIN</small><h1>${esc(titulo)}</h1><p>Inspección de archivos · ${esc(new Date().toISOString().slice(0, 10))}</p></header><main><p>Registro de los archivos leídos y su huella. La lectura muestra fórmulas y valores guardados; no constituye aprobación ni validación de fórmulas, y nada se recalcula.</p><table><thead><tr><th>Archivo</th><th>Lectura</th><th>Fórmulas</th><th>SHA-256 del original</th></tr></thead><tbody>${filas}</tbody></table></main></html>`,
    "text/html;charset=utf-8"
  );
}

// Visor de una extracción: puerto de `Extraction` del sitio.
function Extraccion({ data }) {
  const [sheet, setSheet] = useState(0);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const sheets = data.sheets || [];
  const current = sheets[sheet] || sheets[0];
  const all = current?.formulas || [];
  const filtered = all.filter((f) => (f.cell + " " + f.formula).toLowerCase().includes(query.toLowerCase()));
  return (
    <div className="nf-extraccion">
      {(data.warnings || []).length > 0 && (
        <div className="nf-nota">{data.warnings.map((w) => <p key={w}>{w}</p>)}</div>
      )}
      {sheets.length > 0 && (
        <>
          <label className="nf-ctx-field">
            Hoja
            <select value={sheet} onChange={(e) => { setSheet(Number(e.target.value)); setPage(0); }}>
              {sheets.map((s, i) => <option key={i} value={i}>{s.name}</option>)}
            </select>
          </label>
          {current?.formulas && (
            <>
              <h5>Fórmulas originales · {all.length}</h5>
              <input
                placeholder="Buscar celda o fórmula"
                aria-label="Buscar fórmula"
                value={query}
                onChange={(e) => { setQuery(e.target.value); setPage(0); }}
              />
              <div className="nf-estudio-scroll nf-estudio-tabla">
                <table>
                  <thead><tr><th>Celda</th><th>Fórmula</th><th>Valor guardado</th></tr></thead>
                  <tbody>
                    {filtered.slice(page * 50, page * 50 + 50).map((f) => (
                      <tr key={f.cell}>
                        <td>{f.cell}</td>
                        <td>
                          <code>{f.formula ? "=" + f.formula : "Fórmula compartida; consultar la celda base"}</code>
                          {f.type !== "normal" && <small> · {f.type} {f.sharedIndex ?? ""} {f.range ?? ""}</small>}
                        </td>
                        <td>{f.cached ?? "Sin valor"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="nf-estudio-botones">
                <button type="button" className="btn sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Anterior</button>
                <span>
                  {filtered.length ? `${page * 50 + 1}–${Math.min(page * 50 + 50, filtered.length)} de ${filtered.length}` : "Sin fórmulas"}
                </span>
                <button type="button" className="btn sm" disabled={(page + 1) * 50 >= filtered.length} onClick={() => setPage((p) => p + 1)}>Siguiente</button>
              </div>
            </>
          )}
          <h5>Muestra de datos</h5>
          <pre className="nf-pre">
            {current?.cells
              ? current.cells.slice(0, 100).map((c) => `${c.cell}: ${c.value}`).join("\n")
              : current?.rows?.slice(0, 30).map((r) => r.join(" | ")).join("\n")}
          </pre>
          <p className="muted">Vista limitada a 100 celdas o 30 filas. Descargue la extracción para revisar todo el contenido leído.</p>
        </>
      )}
      {data.text && (
        <pre className="nf-pre">
          {data.text.slice(0, 40000)}
          {data.text.length > 40000 ? "\n[Vista limitada: descargue la extracción completa]" : ""}
        </pre>
      )}
      {data.children?.map((c) => (
        <details key={c.name}>
          <summary>{c.name} · {statusName[c.status]}</summary>
          <Extraccion data={c} />
        </details>
      ))}
      {data.kind === "image" && (
        <p className="muted">La lectura visual de imágenes no está disponible aquí: use el Chat del portal con la imagen.</p>
      )}
    </div>
  );
}

export default function ConsolaArchivos() {
  const [titulo, setTitulo] = useState("Revisión de archivos del cliente");
  const [archivos, setArchivos] = useState([]);
  const [activo, setActivo] = useState(null);
  const [ocupado, setOcupado] = useState("");
  const picker = useRef(null);

  async function leer(lista) {
    for (const f of Array.from(lista || [])) {
      const id = `${f.name}-${f.size}-${f.lastModified}`;
      setOcupado("Leyendo " + f.name + "…");
      let entrada;
      try {
        if (f.size > MAX_FILE) throw Error(`El archivo supera ${MAX_FILE / 1024 / 1024} MB.`);
        const bytes = new Uint8Array(await f.arrayBuffer());
        const [huella, resultado] = await Promise.all([sha256(bytes), extractFile(bytes, f.name)]);
        entrada = { id, nombre: f.name, tamano: f.size, sha256: huella, resultado };
      } catch (e) {
        entrada = { id, nombre: f.name, tamano: f.size, sha256: "", error: e.message || String(e) };
      }
      setArchivos((old) => [...old.filter((x) => x.id !== id), entrada]);
      setActivo(id);
    }
    setOcupado("");
    if (picker.current) picker.current.value = "";
  }

  const actual = archivos.find((a) => a.id === activo);

  return (
    <div className="nf-consola">
      <p className="nf-eyebrow">CONSOLA DE ARCHIVOS</p>
      <h3>Inspección de archivos del cliente</h3>
      <p className="nf-nota">
        Los archivos se leen <strong>en su navegador</strong>: no se suben al servidor y desaparecen al
        cerrar la pestaña. La lectura muestra fórmulas y valores guardados; no recalcula ni valida.
      </p>

      <div className="nf-rec-panel">
        <div className="nf-rec-row">
          <label className="nf-ctx-field" style={{ flex: 1 }}>
            Título de la revisión
            <input value={titulo} maxLength={120} onChange={(e) => setTitulo(e.target.value)} />
          </label>
          <div className="nf-estudio-botones">
            <input
              ref={picker}
              type="file"
              multiple
              hidden
              accept=".xlsx,.csv,.docx,.pdf,.zip,.txt,.md,.xml,.png,.jpg,.jpeg,.webp"
              onChange={(e) => leer(e.target.files)}
            />
            <button type="button" className="btn sm primary" disabled={!!ocupado} onClick={() => picker.current?.click()}>
              Agregar archivos
            </button>
            <button type="button" className="btn sm" disabled={!archivos.length} onClick={() => exportarInforme(titulo, archivos)}>
              Descargar informe HTML
            </button>
            <button type="button" className="btn sm" disabled={!archivos.length} onClick={() => { setArchivos([]); setActivo(null); }}>
              Limpiar
            </button>
          </div>
        </div>
        {ocupado && <p className="muted">{ocupado}</p>}
        <p className="muted">
          Excel, CSV, Word, PDF (hasta 50 páginas), ZIP, texto e imágenes · máximo {MAX_FILE / 1024 / 1024} MB por archivo.
        </p>
      </div>

      {archivos.length > 0 && (
        <div className="nf-consola-cuerpo">
          <ul className="nf-consola-lista">
            {archivos.map((a) => {
              const b = a.resultado ? brief(a.resultado) : null;
              return (
                <li key={a.id}>
                  <button type="button" className={a.id === activo ? "selected" : ""} onClick={() => setActivo(a.id)}>
                    <strong>{a.nombre}</strong>
                    <small>
                      {a.error ? "No se pudo procesar" : statusName[b.status]}
                      {b?.formulaCount ? ` · ${b.formulaCount} fórmulas` : ""}
                    </small>
                  </button>
                </li>
              );
            })}
          </ul>
          {actual && (
            <div className="nf-rec-panel nf-consola-detalle">
              <h4>{actual.nombre}</h4>
              <p className="muted">
                {(actual.tamano / 1024).toFixed(1)} KB · SHA-256 <code>{actual.sha256 || "—"}</code>
              </p>
              {actual.error ? (
                <p className="nf-error">{actual.error}</p>
              ) : (
                <>
                  <div className="nf-estudio-botones">
                    <button
                      type="button"
                      className="btn sm"
                      onClick={() =>
                        guardar(
                          actual.nombre.replace(/\.[^.]+$/, "") + "_extraccion.json",
                          JSON.stringify({ archivo: actual.nombre, sha256: actual.sha256, ...actual.resultado }, null, 2),
                          "application/json"
                        )
                      }
                    >
                      Descargar extracción completa
                    </button>
                  </div>
                  <Extraccion key={actual.id} data={actual.resultado} />
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
