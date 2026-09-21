import { useEffect, useRef, useState } from "react";

import * as api from "../../api";
import { CAMPOS_FICHA, herramientaDePrueba, nombreEstado } from "./cicloLogic";
import { ContextFields } from "./ContextoEncargo";

/*
 * E9 · Revisión y cierre de una prueba del encargo: puntos de revisión,
 * devolver a datos, aprobación inmutable con su papel final, nueva versión,
 * plantilla, ficha del encargo con alcance, encerar y eliminar.
 * Las reglas están en el servidor (puerto de route.ts y lifecycle.ts).
 */

const cargarExportador = () => import("./sitio/tools/exports.mjs");

function descargar(nombre, contenido, tipo) {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const REABRIBLES = ["PRUEBA_CONFIGURADA", "METODOLOGIA_APROBADA", "PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS", "EN_REVISION"];

function Puntos({ prueba, onAccion, ocupado }) {
  const notas = prueba.registro.notes || [];
  const [seccion, setSeccion] = useState("General");
  const [comentario, setComentario] = useState("");
  const [respuestas, setRespuestas] = useState({});
  const enRevision = prueba.estado === "EN_REVISION";
  return (
    <>
      <h6>Puntos de revisión ({notas.length})</h6>
      {notas.length === 0 && <p className="muted">Sin puntos.</p>}
      <ul className="nf-ciclo-notas">
        {notas.map((n) => (
          <li key={n.id}>
            <strong>{n.section}</strong> · {n.comment} <small className="muted">({n.createdBy})</small> ·{" "}
            <span className={n.status === "RESUELTO" ? "nf-ok" : "nf-error"}>{n.status}</span>
            {n.response && <p className="muted">Respuesta: {n.response}</p>}
            {enRevision && n.status === "ABIERTO" && (
              <div className="nf-rec-row">
                <input
                  placeholder="Respuesta sustentada"
                  value={respuestas[n.id] || ""}
                  onChange={(e) => setRespuestas({ ...respuestas, [n.id]: e.target.value })}
                />
                <button type="button" className="btn sm" disabled={ocupado} onClick={() => onAccion("respond_note", { noteId: n.id, response: respuestas[n.id] || "" })}>
                  Responder
                </button>
              </div>
            )}
            {enRevision && n.status === "RESPONDIDO" && (
              <button type="button" className="btn sm" disabled={ocupado} onClick={() => onAccion("resolve_note", { noteId: n.id })}>
                Resolver
              </button>
            )}
          </li>
        ))}
      </ul>
      {enRevision && (
        <div className="nf-rec-row">
          <input value={seccion} onChange={(e) => setSeccion(e.target.value)} aria-label="Sección del punto" />
          <input placeholder="Nuevo punto de revisión" value={comentario} onChange={(e) => setComentario(e.target.value)} style={{ flex: 1 }} />
          <button type="button" className="btn sm" disabled={ocupado} onClick={async () => { await onAccion("add_note", { section: seccion, comment: comentario }); setComentario(""); }}>
            Abrir punto
          </button>
        </div>
      )}
    </>
  );
}

function Aprobar({ prueba, onAccion, ocupado }) {
  const reg = prueba.registro;
  const [conclusion, setConclusion] = useState(reg.conclusion || "");
  const [evaluacion, setEvaluacion] = useState(reg.exceptionReview || "");
  const [revisada, setRevisada] = useState(false);
  const excepciones = reg.run?.exceptions?.length || 0;
  return (
    <>
      <h6>Aprobación</h6>
      <label className="nf-ctx-field">
        Conclusión final
        <textarea rows={3} value={conclusion} onChange={(e) => setConclusion(e.target.value)} />
      </label>
      {excepciones > 0 && (
        <label className="nf-ctx-field">
          Evaluación de las {excepciones} excepciones
          <textarea rows={2} value={evaluacion} onChange={(e) => setEvaluacion(e.target.value)} />
        </label>
      )}
      <label className="nf-ctx-check">
        <input type="checkbox" checked={revisada} onChange={(e) => setRevisada(e.target.checked)} /> Revisé la conclusión y la confirmo
      </label>
      <p className="muted">Al aprobar, la versión queda inmutable: cualquier cambio exige una nueva versión.</p>
      <div className="nf-estudio-botones">
        <button
          type="button"
          className="btn sm primary"
          disabled={ocupado}
          onClick={() => onAccion("approve", { conclusion, exceptionReview: evaluacion, conclusionReviewed: revisada })}
        >
          Aprobar
        </button>
      </div>
    </>
  );
}

function Reabrir({ onAccion, ocupado }) {
  const [motivo, setMotivo] = useState("");
  return (
    <details>
      <summary>Devolver a datos</summary>
      <p className="muted">Vuelve a «Documentación recibida»: se borran validación, ejecución y análisis, y los puntos se reabren.</p>
      <div className="nf-rec-row">
        <input placeholder="Motivo de la reapertura (mínimo 10 caracteres)" value={motivo} onChange={(e) => setMotivo(e.target.value)} style={{ flex: 1 }} />
        <button type="button" className="btn sm" disabled={ocupado} onClick={() => onAccion("return_to_data", { comment: motivo })}>
          Devolver a datos
        </button>
      </div>
    </details>
  );
}

function Papel({ prueba, onRecargar }) {
  const reg = prueba.registro;
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const intentado = useRef(false);

  async function generar() {
    setGuardando(true);
    setError("");
    try {
      const exp = await cargarExportador();
      const t = herramientaDePrueba(prueba);
      await api.cicloSubirPapel(prueba.id, prueba.revision, exp.buildWorkbook(t), exp.buildHtml(t));
      await onRecargar();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setGuardando(false);
    }
  }

  // Recién aprobada: el papel se arma y se guarda solo, una vez.
  useEffect(() => {
    if (!reg.artifacts && !intentado.current) {
      intentado.current = true;
      generar();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function bajar(a) {
    const bytes = await api.cicloBajarArchivo(prueba.id, a.id);
    descargar(a.nombre, bytes, a.nombre.endsWith(".xlsx") ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" : "text/html;charset=utf-8");
  }

  return (
    <>
      <p className="nf-ok">
        Aprobada por {reg.approvedBy} el {String(reg.approvedAt || "").slice(0, 16).replace("T", " ")}. Esta versión es inmutable.
      </p>
      {reg.artifacts ? (
        <ul>
          {Object.values(reg.artifacts).map((a) => (
            <li key={a.id}>
              <button type="button" className="link" onClick={() => bajar(a)}>{a.nombre}</button>{" "}
              <small className="muted">SHA-256 {a.hash.slice(0, 16)}…</small>
            </li>
          ))}
        </ul>
      ) : (
        <button type="button" className="btn sm" disabled={guardando} onClick={generar}>
          {guardando ? "Guardando papel…" : "Generar y guardar el papel aprobado"}
        </button>
      )}
      {error && <p role="alert" className="nf-error">{error}</p>}
    </>
  );
}

function Plantilla({ prueba, onAccion, ocupado }) {
  const reg = prueba.registro;
  const [basis, setBasis] = useState(reg.templateApproved?.parameters?.basis || reg.parameters?.basis || "");
  const bajar = async () => {
    const exp = await cargarExportador();
    const t = { ...herramientaDePrueba(prueba), parameters: reg.templateApproved.parameters };
    descargar(`${(prueba.definicion.name || "prueba").replace(/[^\w-]+/g, "_").slice(0, 60)}_PLANTILLA.xlsx`,
      exp.buildWorkbook(t, true), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
  };
  return (
    <details>
      <summary>Guardar como plantilla</summary>
      <p className="muted">La plantilla es un Excel reutilizable con el programa y la metodología aprobados, sin datos del cliente.</p>
      {prueba.estado !== "APROBADO" && (
        <div className="nf-rec-row">
          <input placeholder="Sustento de la metodología de la plantilla" value={basis} onChange={(e) => setBasis(e.target.value)} style={{ flex: 1 }} />
          <button type="button" className="btn sm" disabled={ocupado} onClick={() => onAccion("approve_template", { basis, buckets: reg.parameters?.buckets || [] })}>
            Aprobar plantilla
          </button>
        </div>
      )}
      {reg.templateApproved && (
        <p>
          Aprobada por {reg.templateApproved.by}.{" "}
          <button type="button" className="link" onClick={bajar}>Descargar plantilla Excel</button>
        </p>
      )}
    </details>
  );
}

function FichaConAlcance({ prueba, onAccion, ocupado }) {
  const reg = prueba.registro;
  const [valor, setValor] = useState({ ...reg.engagement, country: reg.country });
  const [alcance, setAlcance] = useState("one");
  const [otras, setOtras] = useState([]);
  const [elegidas, setElegidas] = useState([]);
  useEffect(() => {
    if (alcance === "selected" && !otras.length)
      api.cicloListarPruebas(prueba.project_id).then((l) => setOtras(l.filter((x) => x.id !== prueba.id && x.estado !== "APROBADO")));
  }, [alcance]); // eslint-disable-line react-hooks/exhaustive-deps
  const alternar = (id) => setElegidas(elegidas.includes(id) ? elegidas.filter((x) => x !== id) : [...elegidas, id]);
  return (
    <details>
      <summary>Cambiar la ficha del encargo</summary>
      <p className="muted">Las pruebas afectadas vuelven a empezar: la ficha cambia fuentes, requerimientos y datos.</p>
      <ContextFields value={valor} onChange={setValor} keys={CAMPOS_FICHA} />
      <div className="nf-rec-row">
        {[["one", "Solo esta prueba"], ["selected", "Esta y otras elegidas"], ["all", "Todas las pruebas abiertas del encargo"]].map(([v, l]) => (
          <label key={v} className="nf-ctx-check">
            <input type="radio" name={`alcance-${prueba.id}`} checked={alcance === v} onChange={() => setAlcance(v)} /> {l}
          </label>
        ))}
      </div>
      {alcance === "selected" && (
        <div className="nf-estudio-marcas">
          {otras.length === 0 && <small className="muted">No hay otras pruebas abiertas.</small>}
          {otras.map((x) => (
            <label key={x.id} className="nf-ctx-check">
              <input type="checkbox" checked={elegidas.includes(x.id)} onChange={() => alternar(x.id)} /> {x.nombre} · v{x.version} · {nombreEstado(x.estado)}
            </label>
          ))}
        </div>
      )}
      <button
        type="button"
        className="btn sm"
        disabled={ocupado}
        onClick={() => onAccion("edit_context", { context: valor, scope: alcance, toolIds: alcance === "selected" ? [prueba.id, ...elegidas] : undefined })}
      >
        Aplicar el cambio
      </button>
    </details>
  );
}

function EncerarEliminar({ prueba, onAccion, ocupado }) {
  const [cliente, setCliente] = useState("");
  const [conserva, setConserva] = useState(false);
  const [definitivo, setDefinitivo] = useState(false);
  const [aprobada, setAprobada] = useState(false);
  return (
    <details id={`encerar-${prueba.id}`}>
      <summary>Encerar o eliminar</summary>
      <p className="muted">
        Escriba el nombre del cliente tal como está en la ficha («{prueba.registro.engagement.client}»). Encerar borra
        evidencia, resultados e historial y deja la prueba para empezar de nuevo; eliminar la quita del todo.
      </p>
      <input placeholder="Nombre del cliente" value={cliente} onChange={(e) => setCliente(e.target.value)} />
      <div className="nf-rec-row">
        <label className="nf-ctx-check">
          <input type="checkbox" checked={conserva} onChange={(e) => setConserva(e.target.checked)} /> Conservo el papel o acepto quedarme sin resultados
        </label>
        <button type="button" className="btn sm" disabled={ocupado} onClick={() => onAccion("erase", { confirmClient: cliente, downloadConfirmed: conserva })}>
          Encerar
        </button>
      </div>
      <div className="nf-rec-row">
        <label className="nf-ctx-check">
          <input type="checkbox" checked={definitivo} onChange={(e) => setDefinitivo(e.target.checked)} /> La eliminación es definitiva
        </label>
        {prueba.estado === "APROBADO" && (
          <label className="nf-ctx-check">
            <input type="checkbox" checked={aprobada} onChange={(e) => setAprobada(e.target.checked)} /> Es una versión aprobada y aun así la elimino
          </label>
        )}
        <button type="button" className="btn sm" disabled={ocupado} onClick={() => onAccion("delete", { confirmClient: cliente, deleteConfirmed: definitivo, approvedConfirmed: aprobada })}>
          Eliminar
        </button>
      </div>
    </details>
  );
}

export function Revision({ prueba, onAccion, onRecargar, ocupado }) {
  const reg = prueba.registro;
  const temprana = ["PRUEBA_SELECCIONADA", "PROGRAMA_PROPUESTO"].includes(prueba.estado);
  return (
    <>
      {(prueba.estado === "EN_REVISION" || prueba.estado === "APROBADO" || (reg.notes || []).length > 0) && (
        <>
          <h5>Revisión y aprobación</h5>
          <Puntos prueba={prueba} onAccion={onAccion} ocupado={ocupado} />
        </>
      )}
      {prueba.estado === "EN_REVISION" && <Aprobar prueba={prueba} onAccion={onAccion} ocupado={ocupado} />}
      {prueba.estado === "APROBADO" && (
        <>
          <h5>Papel aprobado</h5>
          <Papel prueba={prueba} onRecargar={onRecargar} />
          {prueba.sucesora ? (
            <p className="muted">Esta versión ya tiene una versión sucesora (prueba {prueba.sucesora}).</p>
          ) : (
            <div className="nf-estudio-botones">
              <button type="button" className="btn sm" disabled={ocupado} onClick={() => onAccion("new_version")}>
                Crear nueva versión
              </button>
            </div>
          )}
        </>
      )}
      {REABRIBLES.includes(prueba.estado) && <Reabrir onAccion={onAccion} ocupado={ocupado} />}
      {!temprana && reg.sourcesVerified && <Plantilla prueba={prueba} onAccion={onAccion} ocupado={ocupado} />}
      {prueba.estado !== "APROBADO" && <FichaConAlcance prueba={prueba} onAccion={onAccion} ocupado={ocupado} />}
      <EncerarEliminar prueba={prueba} onAccion={onAccion} ocupado={ocupado} />
    </>
  );
}
