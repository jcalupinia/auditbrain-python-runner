import { useEffect, useState } from "react";

import * as api from "../../api";
import { componentesDeTexto, detalleRequerimiento, erroresLegibles, esTabular, mapeoSugerido } from "./cicloLogic";

/*
 * E7 — requerimiento al cliente y documentación de una prueba.
 *
 * Toda regla la aplica el servidor (backend/app/aud/niif/ciclo): la cobertura
 * que se pinta aquí es la que él calcula. Lo único que hace el navegador por
 * su cuenta es leer las hojas de un archivo ya subido para ofrecer el mapeo de
 * columnas, con el mismo lector del sitio (sitio/tools/files.mjs); el mapeo
 * que vale es el que el servidor vuelve a hacer sobre el original.
 */

const cargarLector = () => import("./sitio/tools/files.mjs");

export function EditorRequerimiento({ prueba, onAccion, ocupado }) {
  const reg = prueba.registro;
  const [reqs, setReqs] = useState(reg.requests || []);
  useEffect(() => setReqs(reg.requests || []), [prueba.revision]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (i, cambios) => setReqs(reqs.map((r, j) => (j === i ? { ...r, ...cambios } : r)));
  const codigos = (reg.program || []).map((p) => p.code);

  return (
    <>
      <p className="muted">
        Un renglón por documento. Declare los componentes cuando el cliente lo entrega por partes (por ejemplo, un
        mayor por mes o un inventario por bodega): un solo archivo no cubrirá los demás.
      </p>
      <div className="nf-estudio-scroll nf-estudio-tabla">
        <table>
          <thead>
            <tr><th>Id</th><th>Documento</th><th>Formatos</th><th>Propósito</th><th>Procedimiento</th><th>Componentes</th><th>Grupo alternativo</th><th>Obligatorio</th></tr>
          </thead>
          <tbody>
            {reqs.map((r, i) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>
                  <textarea rows={2} value={r.document || ""} onChange={(e) => set(i, { document: e.target.value })} />
                  {detalleRequerimiento(r).length > 0 && <small className="muted">{detalleRequerimiento(r).join(" · ")}</small>}
                </td>
                {/* Editar el texto manda sobre la lista de formatos que trajo la ficha. */}
                <td><input value={r.format || ""} onChange={(e) => set(i, { format: e.target.value, formats: undefined })} /></td>
                <td><textarea rows={2} value={r.purpose || ""} onChange={(e) => set(i, { purpose: e.target.value })} /></td>
                <td>
                  <select value={r.procedure} onChange={(e) => set(i, { procedure: e.target.value })}>
                    {codigos.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </td>
                <td>
                  <input
                    placeholder="Ej.: Quito, Guayaquil"
                    defaultValue={(r.components || []).join(", ")}
                    onBlur={(e) => set(i, { components: componentesDeTexto(e.target.value) })}
                  />
                </td>
                <td><input value={r.group || ""} onChange={(e) => set(i, { group: e.target.value })} /></td>
                <td>
                  <input type="checkbox" checked={r.required !== false} onChange={(e) => set(i, { required: e.target.checked })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="nf-estudio-botones">
        <button type="button" className="btn sm" disabled={ocupado} onClick={() => onAccion("save_request", { requests: reqs })}>
          Guardar requerimiento
        </button>
        <button type="button" className="btn sm primary" disabled={ocupado} onClick={() => onAccion("approve_request", { requests: reqs })}>
          Aprobar requerimiento
        </button>
      </div>
    </>
  );
}

function Subida({ prueba, req, onSubido }) {
  const [componente, setComponente] = useState(req.components?.[0] || "");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function subir(e) {
    const archivo = e.target.files?.[0];
    e.target.value = "";
    if (!archivo) return;
    setOcupado(true);
    setError("");
    try {
      await api.cicloSubirArchivo(prueba.id, prueba.revision, req.id, componente, archivo);
      await onSubido();
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="nf-rec-pieza">
      {req.components?.length > 0 && (
        <select value={componente} onChange={(e) => setComponente(e.target.value)} aria-label={`Componente de ${req.id}`}>
          {req.components.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      )}
      <label className="btn sm">
        {ocupado ? "Subiendo…" : "Subir archivo"}
        <input type="file" hidden disabled={ocupado} onChange={subir} data-requerimiento={req.id} />
      </label>
      {error && <small className="nf-error">{error}</small>}
    </div>
  );
}

function Mapeo({ prueba, onAccion, ocupado }) {
  const tabulares = prueba.archivos.filter((a) => esTabular(a.nombre) && a.estado !== "rechazado");
  const campos = prueba.definicion.fields;
  const previo = prueba.registro.mapping;
  const [elegidoPorUsuario, setFileId] = useState(previo?.fileId || "");
  // El componente puede montarse antes de que exista ningún archivo: el
  // elegido se calcula siempre sobre lo que hay subido ahora.
  const fileId = tabulares.some((a) => a.id === Number(elegidoPorUsuario)) ? elegidoPorUsuario : tabulares[0]?.id || "";
  const [hojas, setHojas] = useState([]);
  const [hoja, setHoja] = useState(previo?.sheet || "");
  const [encabezado, setEncabezado] = useState(previo?.header || 1);
  const [mapa, setMapa] = useState(previo?.fields || {});
  const [error, setError] = useState("");

  // Lee las hojas del original en el navegador, con el lector del sitio.
  useEffect(() => {
    let vivo = true;
    (async () => {
      setError("");
      setHojas([]);
      if (!fileId) return;
      try {
        const archivo = prueba.archivos.find((a) => a.id === Number(fileId));
        const [bytes, lector] = await Promise.all([api.cicloBajarArchivo(prueba.id, fileId), cargarLector()]);
        const leido = lector.readSpreadsheet(bytes, archivo.nombre);
        if (!vivo) return;
        setHojas(leido.sheets);
        setHoja((h) => (leido.sheets.some((s) => s.name === h) ? h : leido.sheets[0]?.name || ""));
      } catch (e) {
        if (vivo) setError(e.message || String(e));
      }
    })();
    return () => { vivo = false; };
  }, [fileId]); // eslint-disable-line react-hooks/exhaustive-deps

  const actual = hojas.find((s) => s.name === hoja);
  const encabezados = actual?.rows?.[Number(encabezado) - 1] || [];

  useEffect(() => {
    if (encabezados.length && !Object.keys(mapa).length) setMapa(mapeoSugerido(encabezados, campos));
  }, [hoja, encabezado, hojas.length]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!tabulares.length) return <p className="muted">Suba un XLSX o CSV con la población para mapear sus columnas.</p>;

  return (
    <div>
      <div className="nf-rec-row">
        <label className="nf-ctx-field">
          Archivo con la población
          <select value={fileId} onChange={(e) => { setFileId(e.target.value); setMapa({}); }}>
            {tabulares.map((a) => <option key={a.id} value={a.id}>{a.requerimiento}{a.componente ? ` · ${a.componente}` : ""} · {a.nombre}</option>)}
          </select>
        </label>
        <label className="nf-ctx-field">
          Hoja
          <select value={hoja} onChange={(e) => { setHoja(e.target.value); setMapa({}); }}>
            {hojas.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
        </label>
        <label className="nf-ctx-field">
          Fila de encabezados
          <input type="number" min={1} max={100} value={encabezado} onChange={(e) => { setEncabezado(Number(e.target.value)); setMapa({}); }} />
        </label>
      </div>
      {error && <p className="nf-error">{error}</p>}
      {encabezados.length > 0 && (
        <div className="nf-ciclo-mapeo">
          {campos.map((f) => (
            <label key={f.key} className="nf-ctx-field">
              {f.label}
              <select
                value={mapa[f.key] ?? ""}
                onChange={(e) => setMapa({ ...mapa, [f.key]: e.target.value === "" ? undefined : Number(e.target.value) })}
              >
                <option value="">Sin mapear…</option>
                {encabezados.map((h, i) => <option key={i} value={i}>{String(h ?? "") || `(columna ${i + 1})`}</option>)}
              </select>
            </label>
          ))}
        </div>
      )}
      <button
        type="button"
        className="btn sm primary"
        disabled={ocupado || !hoja}
        onClick={() => onAccion("map_validate", { fileId: Number(fileId), sheet: hoja, header: Number(encabezado), mapping: mapa })}
      >
        Mapear y validar datos
      </button>
    </div>
  );
}

function Validacion({ prueba, onAccion, ocupado }) {
  const reg = prueba.registro;
  const [revisado, setRevisado] = useState(false);
  const [texto, setTexto] = useState("");
  const [saldo, setSaldo] = useState("");
  const [tolerancia, setTolerancia] = useState("0");
  const [aceptacion, setAceptacion] = useState("");
  return (
    <div>
      <p>
        Total de control de la población: <strong>{reg.controlTotal}</strong>. Compárelo con el saldo contable al corte.
      </p>
      <div className="nf-rec-row">
        <label className="nf-ctx-field">Saldo contable<input value={saldo} onChange={(e) => setSaldo(e.target.value)} placeholder="470.00" /></label>
        <label className="nf-ctx-field">Tolerancia<input value={tolerancia} onChange={(e) => setTolerancia(e.target.value)} /></label>
      </div>
      <label className="nf-ctx-field">
        Aceptación documentada de la diferencia (solo si no concilia; mínimo 15 caracteres)
        <textarea rows={2} value={aceptacion} onChange={(e) => setAceptacion(e.target.value)} />
      </label>
      <label className="nf-ctx-field">
        Revisión de evidencia: cómo cotejó los originales con la extracción y los datos
        <textarea rows={3} value={texto} onChange={(e) => setTexto(e.target.value)} />
      </label>
      <label className="nf-ctx-check">
        <input type="checkbox" checked={revisado} onChange={(e) => setRevisado(e.target.checked)} /> Revisé los originales, las
        extracciones y su relación con los datos.
      </label>
      <button
        type="button"
        className="btn sm primary"
        disabled={ocupado}
        onClick={() => onAccion("validate", { evidenceReviewed: revisado, evidenceReview: texto, ledger: saldo, tolerance: tolerancia, acceptance: aceptacion })}
      >
        Validar documentación
      </button>
    </div>
  );
}

export function Documentacion({ prueba, onAccion, onRecargar, ocupado }) {
  const reg = prueba.registro;
  const abierta = ["REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA"].includes(prueba.estado);
  const coberturaDe = (id) => prueba.cobertura.find((c) => c.id === id);

  async function bajar(a) {
    const bytes = await api.cicloBajarArchivo(prueba.id, a.id);
    const url = URL.createObjectURL(new Blob([bytes]));
    const enlace = Object.assign(document.createElement("a"), { href: url, download: a.nombre });
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  return (
    <>
      <h5>Requerimiento y evidencia</h5>
      <div className="nf-rec-fuentes">
        {reg.requests.map((r) => {
          const c = coberturaDe(r.id);
          const suyos = prueba.archivos.filter((a) => a.requerimiento === r.id);
          return (
            <div key={r.id} className="nf-rec-item">
              <strong>{r.id}</strong> · {r.document}
              <p className="muted">
                {r.format} · {r.required !== false ? "obligatorio" : "opcional"}
                {r.group ? ` · alternativa de «${r.group}»` : ""}
                {r.components?.length ? ` · componentes: ${r.components.join(", ")}` : ""}
              </p>
              {detalleRequerimiento(r).length > 0 && <p className="muted">{detalleRequerimiento(r).join(" · ")}</p>}
              {suyos.map((a) => (
                <div key={a.id} className="nf-rec-pieza">
                  <button type="button" className="link" onClick={() => bajar(a)}>{a.nombre}</button>
                  {a.componente && <small>{a.componente}</small>}
                  <small className={a.estado === "rechazado" ? "nf-error" : "nf-ok"}>{a.estado}</small>
                  {abierta && (
                    <button type="button" className="link" disabled={ocupado} onClick={() => onAccion("reject_file", { fileId: a.id })}>
                      {a.estado === "rechazado" ? "Restituir" : "Rechazar"}
                    </button>
                  )}
                </div>
              ))}
              {abierta && <Subida prueba={prueba} req={r} onSubido={onRecargar} />}
              <small className={c?.complete ? "nf-ok" : "nf-rec-falta"}>
                {c?.complete ? "Cubierto" : `Falta: ${(c?.pending || []).join(", ") || "entrega"}`}
              </small>
            </div>
          );
        })}
      </div>
      {prueba.huecos.length > 0 ? (
        <div className="nf-huecos">
          <strong>Impide validar ({prueba.huecos.length}):</strong>
          <ul>{prueba.huecos.map((h) => <li key={h}>{h}</li>)}</ul>
        </div>
      ) : (
        <p className="nf-ok">Requerimiento cubierto.</p>
      )}

      {abierta && (
        <>
          <h5>Población</h5>
          <Mapeo prueba={prueba} onAccion={onAccion} ocupado={ocupado} />
          {reg.validation && (
            <div className={reg.validation.ok ? "nf-nota" : "nf-huecos"}>
              <strong>
                {reg.validation.records} registros · {reg.validation.errors.length} errores · {reg.validation.warnings.length} advertencias
                {reg.mapping ? ` · ${reg.mapping.file}, hoja ${reg.mapping.sheet}` : ""}
              </strong>
              <ul>{erroresLegibles(reg.validation).map((e, i) => <li key={i}>{e}</li>)}</ul>
            </div>
          )}
          {reg.validation?.ok && (
            <>
              <h5>Validación</h5>
              <Validacion prueba={prueba} onAccion={onAccion} ocupado={ocupado} />
            </>
          )}
        </>
      )}

      {prueba.estado === "DOCUMENTACION_VALIDADA" && (
        <p className="nf-nota">
          Documentación validada por {reg.evidenceReview?.by}: {reg.validation?.records} registros, total de control{" "}
          {reg.controlTotal}, diferencia con el mayor {reg.reconciliation?.difference}. La ejecución de la prueba llega con E8.
        </p>
      )}
    </>
  );
}
