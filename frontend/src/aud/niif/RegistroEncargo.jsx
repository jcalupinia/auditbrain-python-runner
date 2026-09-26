import { useCallback, useEffect, useState } from "react";

import * as api from "../../api";
import {
  CICLOS, DECISIONES, DOCUMENTOS, NOMBRE_ARCHIVO, NOMBRE_TIPO, PROCEDIMIENTOS, ROLES, TEMAS, decisionDe, miIndependencia,
  resumenRegistros,
} from "./registroLogic";

/*
 * «Registro del encargo» (decisión del dueño, 2026-09-26): lo que no sale de los documentos del cliente se confirma
 * con un clic (independencia, discusión del equipo, aceptación del socio, carta firmada, comunicación al gobierno) y
 * la plataforma genera la carta de encargo, el acta de la discusión y la carta de planificación. La planificación
 * lee estos registros al ejecutarse (hoja 00_Registros). Las reglas las aplica el servidor.
 */

const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function descargar(nombre, contenido) {
  const url = URL.createObjectURL(new Blob([contenido], { type: DOCX }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const hoy = () => new Date().toISOString().slice(0, 10);

export function RegistroEncargo({ proyecto }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [indep, setIndep] = useState({ nombre: "", rol: "", amenazas: "", salvaguardas: "", anio_desde: "" });
  const [discusion, setDiscusion] = useState(hoy());
  const [carta, setCarta] = useState({ fecha: hoy(), limitaciones: "" });
  const [comunic, setComunic] = useState({ fecha: hoy(), medio: "" });
  const [indag, setIndag] = useState({ tema: "", procedimiento: "Indagación", persona: "", resumen: "", fecha: hoy() });
  const [consulta, setConsulta] = useState({ tipo: "consulta", tema: "", detalle: "" });
  const [resoluciones, setResoluciones] = useState({});
  const [enfoques, setEnfoques] = useState({});

  const recargar = useCallback(async () => {
    try {
      setDatos(await api.cicloRegistros(proyecto.id));
    } catch (e) {
      setError(e.message || String(e));
    }
  }, [proyecto.id]);

  useEffect(() => {
    recargar();
  }, [recargar]);

  const mia = datos ? miIndependencia(datos.registros, datos.usuario) : null;
  useEffect(() => {
    if (mia) setIndep((v) => ({ ...v, nombre: v.nombre || mia.nombre, rol: v.rol || mia.rol }));
  }, [mia]);

  async function registrar(cuerpo) {
    setOcupado(true);
    setError("");
    try {
      await api.cicloRegistrar(proyecto.id, cuerpo);
      await recargar();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setOcupado(false);
    }
  }

  async function resolver(id) {
    setError("");
    try {
      await api.cicloResolverConsulta(proyecto.id, id, resoluciones[id] || "");
      await recargar();
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  async function anular(id) {
    setError("");
    try {
      await api.cicloAnularRegistro(proyecto.id, id);
      await recargar();
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  async function documento(tipo) {
    setError("");
    try {
      descargar(NOMBRE_ARCHIVO[tipo], await api.cicloDocumentoEncargo(proyecto.id, tipo));
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  if (!datos) return error ? <p className="nf-error">{error}</p> : <p className="muted">Cargando registros…</p>;
  const resumen = resumenRegistros(datos.encargo);

  return (
    <section className="nf-rec-panel nf-registro-encargo">
      <p className="nf-eyebrow">2 · REGISTRO DEL ENCARGO</p>
      <p className="muted">
        Lo que no está en los documentos del cliente se confirma aquí con un clic. La planificación toma estos registros
        al ejecutarse y los muestra en la hoja 00_Registros del papel.
      </p>
      {error && <p role="alert" className="nf-error">{error}</p>}
      <ul className="nf-consola-lista">
        {resumen.map((x) => (
          <li key={x.clave}>
            <strong>{x.hecho ? "✔" : "○"} {x.etiqueta}</strong> <small className="muted">· {x.detalle}</small>
          </li>
        ))}
      </ul>

      <div className="nf-rec-item">
        <h5>Mi independencia (Código IESBA; NIA 220)</h5>
        <div className="nf-rec-row">
          <label className="nf-ctx-field">
            Nombre en el papel
            <input value={indep.nombre} placeholder={datos.usuario} onChange={(e) => setIndep({ ...indep, nombre: e.target.value })} />
          </label>
          <label className="nf-ctx-field">
            Rol
            <select value={indep.rol} onChange={(e) => setIndep({ ...indep, rol: e.target.value })}>
              <option value="">Seleccione…</option>
              {ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </label>
          <label className="nf-ctx-field">
            Atiendo al cliente desde (año, opcional)
            <input inputMode="numeric" value={indep.anio_desde} onChange={(e) => setIndep({ ...indep, anio_desde: e.target.value })} />
          </label>
        </div>
        <label className="nf-ctx-field">
          Amenazas a la independencia (vacío si no hay)
          <textarea rows={2} value={indep.amenazas} onChange={(e) => setIndep({ ...indep, amenazas: e.target.value })} />
        </label>
        <label className="nf-ctx-field">
          Salvaguardas aplicadas
          <textarea rows={2} value={indep.salvaguardas} onChange={(e) => setIndep({ ...indep, salvaguardas: e.target.value })} />
        </label>
        <button type="button" className="btn sm primary" disabled={ocupado || !indep.rol}
          onClick={() => registrar({ tipo: "independencia", ...indep })}>
          Confirmo mi independencia
        </button>
      </div>

      <div className="nf-rec-item">
        <h5>Discusión del equipo y aceptación</h5>
        <div className="nf-rec-row">
          <label className="nf-ctx-field">
            Fecha de la discusión
            <input type="date" value={discusion} max={hoy()} onChange={(e) => setDiscusion(e.target.value)} />
          </label>
          <button type="button" className="btn sm" disabled={ocupado || !mia}
            title={mia ? "" : "Confirme primero su independencia"}
            onClick={() => registrar({ tipo: "asistencia", rol: mia?.rol, nombre: mia?.nombre, fecha: discusion })}>
            Asistí a la discusión
          </button>
          <button type="button" className="btn sm" disabled={ocupado || mia?.rol !== "Socio"}
            title={mia?.rol === "Socio" ? "" : "La aceptación la registra el socio"}
            onClick={() => registrar({ tipo: "aceptacion" })}>
            Acepto el encargo (socio)
          </button>
        </div>
      </div>

      <div className="nf-rec-item">
        <h5>Carta de encargo y comunicación al gobierno</h5>
        <div className="nf-rec-row">
          <label className="nf-ctx-field">
            Fecha de firma del cliente
            <input type="date" value={carta.fecha} max={hoy()} onChange={(e) => setCarta({ ...carta, fecha: e.target.value })} />
          </label>
          <label className="nf-ctx-field" style={{ flex: 1 }}>
            Limitaciones al alcance (vacío si no hay)
            <input value={carta.limitaciones} onChange={(e) => setCarta({ ...carta, limitaciones: e.target.value })} />
          </label>
          <button type="button" className="btn sm" disabled={ocupado} onClick={() => registrar({ tipo: "carta", ...carta })}>
            Carta firmada
          </button>
        </div>
        <div className="nf-rec-row">
          <label className="nf-ctx-field">
            Fecha de envío
            <input type="date" value={comunic.fecha} max={hoy()} onChange={(e) => setComunic({ ...comunic, fecha: e.target.value })} />
          </label>
          <label className="nf-ctx-field" style={{ flex: 1 }}>
            Medio (reunión, correo, carta)
            <input value={comunic.medio} onChange={(e) => setComunic({ ...comunic, medio: e.target.value })} />
          </label>
          <button type="button" className="btn sm" disabled={ocupado || !comunic.medio.trim()}
            onClick={() => registrar({ tipo: "comunicacion", ...comunic })}>
            Comunicación enviada
          </button>
        </div>
      </div>

      <div className="nf-rec-item">
        <h5>Enfoque por ciclo: confianza o no en los controles (NIA 330)</h5>
        <small className="muted">
          La planificación propone el enfoque de cada ciclo (hoja 45); el socio lo confirma o lo cambia aquí. Confiar en los
          controles obliga a probar su eficacia y baja un nivel la confianza del muestreo del ciclo.
        </small>
        {CICLOS.map((ciclo) => {
          const actual = decisionDe(datos.encargo, ciclo);
          const v = enfoques[ciclo] || { decision: actual?.decision || "", motivo: "" };
          return (
            <div key={ciclo} className="nf-rec-row">
              <span style={{ flex: 1, minWidth: 220 }}>
                {ciclo}
                <small className="muted"> · {actual ? `${actual.decision} (${actual.actor}, ${actual.fecha})` : "Sin confirmar"}</small>
              </span>
              <select aria-label={`Enfoque · ${ciclo}`} value={v.decision}
                onChange={(e) => setEnfoques({ ...enfoques, [ciclo]: { ...v, decision: e.target.value } })}>
                <option value="">Seleccione…</option>
                {DECISIONES.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              <input aria-label={`Motivo · ${ciclo}`} placeholder="Motivo" value={v.motivo}
                onChange={(e) => setEnfoques({ ...enfoques, [ciclo]: { ...v, motivo: e.target.value } })} />
              <button type="button" className="btn sm" disabled={ocupado || mia?.rol !== "Socio" || !v.decision || v.motivo.trim().length < 10}
                title={mia?.rol === "Socio" ? "" : "Lo confirma el socio"}
                onClick={() => registrar({ tipo: "enfoque", ciclo, decision: v.decision, motivo: v.motivo })}>
                Confirmar
              </button>
            </div>
          );
        })}
      </div>

      <div className="nf-rec-item">
        <h5>Indagaciones y observaciones (NIA 315)</h5>
        <div className="nf-rec-row">
          <label className="nf-ctx-field">
            Tema
            <select value={indag.tema} onChange={(e) => setIndag({ ...indag, tema: e.target.value })}>
              <option value="">Seleccione…</option>
              {TEMAS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className="nf-ctx-field">
            Procedimiento
            <select value={indag.procedimiento} onChange={(e) => setIndag({ ...indag, procedimiento: e.target.value })}>
              {PROCEDIMIENTOS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className="nf-ctx-field">
            Persona entrevistada o lugar
            <input value={indag.persona} onChange={(e) => setIndag({ ...indag, persona: e.target.value })} />
          </label>
          <label className="nf-ctx-field">
            Fecha
            <input type="date" value={indag.fecha} max={hoy()} onChange={(e) => setIndag({ ...indag, fecha: e.target.value })} />
          </label>
        </div>
        <label className="nf-ctx-field">
          Qué se obtuvo
          <textarea rows={2} value={indag.resumen} onChange={(e) => setIndag({ ...indag, resumen: e.target.value })} />
        </label>
        <button type="button" className="btn sm" disabled={ocupado || !indag.tema || indag.resumen.trim().length < 10}
          onClick={async () => { await registrar({ tipo: "indagacion", ...indag }); setIndag({ ...indag, persona: "", resumen: "" }); }}>
          Registrar indagación
        </button>
      </div>

      <div className="nf-rec-item">
        <h5>Consultas y diferencias de opinión (NIA 220)</h5>
        <div className="nf-rec-row">
          <label className="nf-ctx-field">
            Tipo
            <select value={consulta.tipo} onChange={(e) => setConsulta({ ...consulta, tipo: e.target.value })}>
              <option value="consulta">Consulta técnica</option>
              <option value="diferencia">Diferencia de opinión</option>
            </select>
          </label>
          <label className="nf-ctx-field" style={{ flex: 1 }}>
            Tema
            <input value={consulta.tema} onChange={(e) => setConsulta({ ...consulta, tema: e.target.value })} />
          </label>
          <button type="button" className="btn sm" disabled={ocupado || consulta.tema.trim().length < 5}
            onClick={async () => { await registrar(consulta); setConsulta({ ...consulta, tema: "", detalle: "" }); }}>
            Abrir
          </button>
        </div>
        {datos.registros.filter((r) => ["consulta", "diferencia"].includes(r.tipo) && r.datos.estado === "Abierta").map((r) => (
          <div key={r.id} className="nf-rec-row">
            <span style={{ flex: 1 }}>{NOMBRE_TIPO[r.tipo]} · {r.datos.tema}</span>
            <input placeholder="Resolución" value={resoluciones[r.id] || ""}
              onChange={(e) => setResoluciones({ ...resoluciones, [r.id]: e.target.value })} />
            <button type="button" className="btn sm" disabled={(resoluciones[r.id] || "").trim().length < 10}
              onClick={() => resolver(r.id)}>
              Resolver
            </button>
          </div>
        ))}
      </div>

      <div className="nf-estudio-botones">
        {DOCUMENTOS.map(([tipo, etiqueta]) => (
          <button key={tipo} type="button" className="btn sm" onClick={() => documento(tipo)}>
            Descargar {etiqueta}
          </button>
        ))}
      </div>
      <small className="muted">
        Los documentos son modelos para revisar y firmar; el acta y la carta de planificación toman la última
        planificación ejecutada de este encargo.
      </small>

      {datos.registros.length > 0 && (
        <details>
          <summary>Registros vigentes ({datos.registros.length})</summary>
          <ul className="nf-consola-lista">
            {datos.registros.map((r) => (
              <li key={r.id}>
                {NOMBRE_TIPO[r.tipo]} · {r.nombre}{r.rol ? ` (${r.rol})` : ""} · {r.fecha}
                {r.actor === datos.usuario && (
                  <button type="button" className="link" onClick={() => anular(r.id)}>Anular</button>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
