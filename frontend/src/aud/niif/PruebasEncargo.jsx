import { useCallback, useEffect, useState } from "react";

import * as api from "../../api";
import {
  CAMPOS_FICHA,
  ETAPAS,
  alternarProcedimiento,
  etapaDe,
  fichaInicial,
  nombreEstado,
  procedimientosSinFuente,
} from "./cicloLogic";
import { Documentacion, EditorRequerimiento } from "./CicloDocumentacion";
import { Ejecucion } from "./CicloEjecucion";
import { Revision } from "./CicloRevision";
import { VistaTrabajo } from "./CicloVista";
import { ContextFields } from "./ContextoEncargo";
import "./fichaNiif.css";

/*
 * «Pruebas del encargo» — el ciclo real de una prueba sobre el proyecto AUD
 * activo (diseño 2026-09-21). E6 cubre: ficha del encargo, crear la prueba y
 * llevar su programa a aprobado. Todas las reglas las aplica el servidor; esta
 * pantalla solo pinta y envía.
 */

const CAMPOS_PROGRAMA = [
  ["code", "Código"],
  ["objective", "Objetivo"],
  ["risk", "Riesgo"],
  ["assertion", "Afirmación"],
  ["procedure", "Procedimiento"],
  ["evidence", "Evidencia"],
  ["criterion", "Criterio"],
];

function FichaEncargo({ proyecto, cliente, ficha, onGuardada }) {
  const [editando, setEditando] = useState(!ficha);
  const [valor, setValor] = useState(ficha || fichaInicial(cliente?.name));
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    setValor(ficha || fichaInicial(cliente?.name));
    setEditando(!ficha);
  }, [ficha, cliente?.name]);

  async function guardar(e) {
    e.preventDefault();
    setOcupado(true);
    setError("");
    try {
      const r = await api.cicloGuardarFicha(proyecto.id, valor);
      onGuardada(r.ficha);
      setEditando(false);
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <section className="nf-rec-panel">
      <div className="nf-rec-row">
        <div>
          <p className="nf-eyebrow">1 · FICHA DEL ENCARGO</p>
          {ficha ? (
            <>
              <h4>{ficha.client} · RUC {ficha.ruc}</h4>
              <p>{ficha.framework} · {ficha.edition} · Corte {ficha.cutoff} · {ficha.currency} · Visita {ficha.visit}</p>
              <p>Preparado por: {ficha.preparer} · Revisado por: {ficha.reviewer} · {ficha.firm}</p>
            </>
          ) : (
            <p className="muted">
              Complete la ficha del encargo: la usan todas las pruebas de este proyecto.
            </p>
          )}
        </div>
        {ficha && !editando && (
          <button type="button" className="btn sm" onClick={() => setEditando(true)}>Editar ficha</button>
        )}
      </div>
      {editando && (
        <form onSubmit={guardar}>
          <ContextFields value={valor} onChange={setValor} keys={CAMPOS_FICHA} />
          {error && <p className="nf-error">{error}</p>}
          <div className="nf-estudio-botones">
            <button type="submit" className="btn sm primary" disabled={ocupado}>Guardar ficha del encargo</button>
            {ficha && <button type="button" className="btn sm" onClick={() => setEditando(false)}>Cancelar</button>}
          </div>
        </form>
      )}
    </section>
  );
}

function Programa({ prueba, onAccion, ocupado }) {
  const reg = prueba.registro;
  const editable = prueba.estado === "PROGRAMA_PROPUESTO";
  const [programa, setPrograma] = useState(reg.program);
  const [fuentes, setFuentes] = useState(reg.sources);
  const [taxScope, setTaxScope] = useState(reg.taxScope || "");

  useEffect(() => {
    setPrograma(reg.program);
    setFuentes(reg.sources);
    setTaxScope(reg.taxScope || "");
  }, [prueba.revision]); // eslint-disable-line react-hooks/exhaustive-deps

  const setFuente = (i, cambios) => setFuentes(fuentes.map((s, j) => (j === i ? { ...s, ...cambios } : s)));
  const setProc = (i, k, v) => setPrograma(programa.map((p, j) => (j === i ? { ...p, [k]: v } : p)));
  const faltan = procedimientosSinFuente(programa, fuentes);
  const datos = { program: programa, sources: fuentes, taxScope };

  return (
    <>
      <h5>Fuentes</h5>
      <p className="muted">
        NIIF solo de ifrs.org; NIA de iaasb.org o ifac.org. Marque «Verificada» después de revisar documento,
        párrafo y vigencia, y vincule cada procedimiento a una fuente verificada.
      </p>
      <div className="nf-ciclo-fuentes">
        {fuentes.map((s, i) => (
          <div key={i} className="nf-rec-item">
            <strong>{s.category}</strong> · {s.organization}
            <label className="nf-ctx-field">
              Documento
              <input value={s.document || ""} disabled={!editable} onChange={(e) => setFuente(i, { document: e.target.value })} />
            </label>
            <label className="nf-ctx-field">
              Párrafo / artículo
              <input value={s.section || ""} disabled={!editable} onChange={(e) => setFuente(i, { section: e.target.value })} />
            </label>
            <label className="nf-ctx-field">
              Vigencia
              <input value={s.date || ""} disabled={!editable} onChange={(e) => setFuente(i, { date: e.target.value })} />
            </label>
            <label className="nf-ctx-field">
              Enlace (https)
              <input value={s.url || ""} disabled={!editable} onChange={(e) => setFuente(i, { url: e.target.value })} />
            </label>
            <div className="nf-estudio-marcas">
              {programa.map((p) => (
                <label key={p.code} className="nf-ctx-check">
                  <input
                    type="checkbox"
                    disabled={!editable}
                    checked={(s.procedures || []).includes(p.code)}
                    onChange={() => setFuentes(alternarProcedimiento(fuentes, i, p.code))}
                  />
                  {p.code}
                </label>
              ))}
            </div>
            <label className="nf-ctx-check">
              <input type="checkbox" disabled={!editable} checked={!!s.verified} onChange={(e) => setFuente(i, { verified: e.target.checked })} />
              Verificada
            </label>
          </div>
        ))}
      </div>
      {reg.taxApplicable && (
        <label className="nf-ctx-field">
          Tratamiento tributario revisado y su sustento
          <textarea rows={3} value={taxScope} disabled={!editable} onChange={(e) => setTaxScope(e.target.value)} />
        </label>
      )}

      <h5>Procedimientos</h5>
      <div className="nf-estudio-scroll nf-estudio-tabla">
        <table>
          <thead><tr>{CAMPOS_PROGRAMA.map(([, l]) => <th key={l}>{l}</th>)}<th>Fuente</th></tr></thead>
          <tbody>
            {programa.map((p, i) => (
              <tr key={p.code}>
                {CAMPOS_PROGRAMA.map(([k]) => (
                  <td key={k}>
                    {editable && k !== "code" ? (
                      <textarea rows={2} value={p[k] || ""} onChange={(e) => setProc(i, k, e.target.value)} />
                    ) : (
                      p[k]
                    )}
                  </td>
                ))}
                <td>
                  {p.state === "APROBADO" ? `${p.source?.category} · ${p.source?.document}` : faltan.includes(p.code) ? "Sin fuente verificada" : "✓"}
                  {p.reference && <small className="muted"> · Norma: {p.reference}</small>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editable && (
        <div className="nf-estudio-botones">
          <button type="button" className="btn sm" disabled={ocupado} onClick={() => onAccion("save_program", datos)}>
            Guardar programa
          </button>
          <button type="button" className="btn sm primary" disabled={ocupado} onClick={() => onAccion("approve_program", datos)}>
            Aprobar programa
          </button>
          <button type="button" className="link" disabled={ocupado} onClick={() => onAccion("research")}>
            Volver a consultar fuentes oficiales
          </button>
        </div>
      )}
    </>
  );
}

// Acciones del ciclo en lenguaje del auditor (la bitácora guarda el código).
const ACCION_BITACORA = {
  create: "Prueba creada", research: "Investigación de la norma", generate_program: "Programa generado", approve_program: "Programa aprobado",
  generate_request: "Requerimiento generado", approve_request: "Requerimiento aprobado", upload: "Documento subido", reject_file: "Documento rechazado o restituido",
  map_validate: "Datos mapeados y validados", validate: "Documentación validada y conciliada", configure: "Parámetros configurados",
  approve_methodology: "Metodología aprobada", execute: "Prueba ejecutada", save_analysis: "Análisis guardado", return_to_data: "Devuelta a datos",
  analyze: "Análisis generado", submit: "Enviada a revisión", approve: "Aprobada por el revisor", approve_template: "Plantilla aprobada",
  add_note: "Nota de revisión", respond_note: "Respuesta a nota de revisión",
};

export function Prueba({ id, onCambio, onAbrir }) {
  const [prueba, setPrueba] = useState(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setPrueba(await api.cicloLeerPrueba(id));
    } catch (e) {
      setError(e.message || String(e));
    }
  }, [id]);

  useEffect(() => { cargar(); }, [cargar]);

  async function accion(nombre, datos = {}) {
    setOcupado(true);
    setError("");
    try {
      const r = await api.cicloAccion(prueba.id, nombre, prueba.revision, datos);
      onCambio();
      // Una versión nueva es otra prueba; una eliminada ya no existe.
      if (nombre === "new_version") return onAbrir?.(r.id);
      if (nombre === "delete") return onAbrir?.(null);
      await cargar();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setOcupado(false);
    }
  }

  if (!prueba) return error ? <p className="nf-error">{error}</p> : <p className="muted">Cargando prueba…</p>;
  const etapa = etapaDe(prueba.estado);
  const reg = prueba.registro;

  return (
    <div className="nf-rec-panel nf-ciclo-prueba">
      <h4>{prueba.definicion.name} · v{prueba.version}</h4>
      <p className="muted">
        Estado: <strong>{nombreEstado(prueba.estado)}</strong> · revisión {prueba.revision} · metodología{" "}
        {reg.methodologyVersion}
      </p>
      <ol className="nf-ciclo-etapas">
        {ETAPAS.map((e, i) => (
          <li key={e} className={i < etapa ? "hecha" : i === etapa ? "actual" : ""}>{e}</li>
        ))}
      </ol>
      {error && <p role="alert" className="nf-error">{error}</p>}

      <VistaTrabajo prueba={prueba} onAccion={accion} onRecargar={async () => { await cargar(); onCambio(); }} ocupado={ocupado} />

      {["PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS"].includes(prueba.estado) && (
        <section>
          <h5>Análisis y cierre del papel de trabajo</h5>
          <Ejecucion prueba={prueba} onAccion={accion} ocupado={ocupado} soloAnalisis />
        </section>
      )}

      <section>
        <Revision prueba={prueba} onAccion={accion} onRecargar={async () => { await cargar(); onCambio(); }} ocupado={ocupado} />
      </section>

      <details className="nf-circuito">
        <summary>Circuito detallado (paso a paso, con mapeo manual)</summary>
      {prueba.estado === "PRUEBA_SELECCIONADA" && (
        <section>
          <h5>Programa de trabajo</h5>
          <p>
            Primero se consultan las fuentes oficiales del marco ({reg.engagement.framework}); después se genera el
            programa propuesto.
          </p>
          <div className="nf-estudio-botones">
            <button type="button" className="btn sm" disabled={ocupado} onClick={() => accion("research")}>
              {reg.researchedAt ? "Volver a consultar fuentes oficiales" : "Consultar fuentes oficiales"}
            </button>
            <button type="button" className="btn sm primary" disabled={ocupado || !reg.researchedAt} onClick={() => accion("generate_program")}>
              Generar programa
            </button>
          </div>
          {reg.researchedAt && <p className="nf-ok">Fuentes propuestas: {reg.sources.map((s) => s.category).join(", ")}.</p>}
        </section>
      )}

      {["PROGRAMA_PROPUESTO", "PROGRAMA_APROBADO"].includes(prueba.estado) && (
        <section>
          <h5>Programa de trabajo</h5>
          <Programa prueba={prueba} onAccion={accion} ocupado={ocupado} />
          {prueba.estado === "PROGRAMA_APROBADO" && (
            <div className="nf-estudio-botones">
              <button type="button" className="btn sm primary" disabled={ocupado} onClick={() => accion("generate_request")}>
                Generar requerimiento al cliente
              </button>
            </div>
          )}
        </section>
      )}

      {etapa > 2 && (
        <details>
          <summary>Programa de trabajo aprobado ({reg.program.length} procedimientos)</summary>
          <ul>{reg.program.map((p) => <li key={p.code}>{p.code} · {p.objective} · {p.source?.category} {p.source?.document}</li>)}</ul>
        </details>
      )}

      {prueba.estado === "REQUERIMIENTO_GENERADO" && (
        <section>
          <h5>Requerimiento al cliente</h5>
          <EditorRequerimiento prueba={prueba} onAccion={accion} ocupado={ocupado} />
        </section>
      )}

      {prueba.definicion.processor && etapa > 3 && (
        <p className="muted">
          Esta herramienta tiene un procesador propio que une varios anexos (cartera de tres años, provisión y mayor): su
          documentación, cálculo y cédulas se trabajan con «Procesar» en la vista de arriba.
        </p>
      )}

      {!prueba.definicion.processor && ["REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA", "DOCUMENTACION_VALIDADA"].includes(prueba.estado) && (
        <section>
          <Documentacion prueba={prueba} onAccion={accion} onRecargar={async () => { await cargar(); onCambio(); }} ocupado={ocupado} />
        </section>
      )}

      {!prueba.definicion.processor && ["DOCUMENTACION_VALIDADA", "PRUEBA_CONFIGURADA", "METODOLOGIA_APROBADA", "PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS", "EN_REVISION", "APROBADO"].includes(prueba.estado) && (
        <section>
          <Ejecucion prueba={prueba} onAccion={accion} ocupado={ocupado} />
        </section>
      )}

      </details>

      <details>
        <summary>Bitácora ({prueba.eventos.length})</summary>
        <ul>
          {prueba.eventos.map((e, i) => (
            <li key={i}>
              {e.fecha?.slice(0, 16).replace("T", " ")} · {e.actor} · {ACCION_BITACORA[e.accion] || e.accion}
              {e.estado_nuevo && e.estado_nuevo !== e.estado_anterior ? ` → ${nombreEstado(e.estado_nuevo)}` : ""}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function EncargoTrabajo({ proyecto, cliente, herramientaInicial = "" }) {
  const [ficha, setFicha] = useState(null);
  const [pruebas, setPruebas] = useState([]);
  const [herramientas, setHerramientas] = useState([]);
  const [origen, setOrigen] = useState(herramientaInicial);
  const [tributario, setTributario] = useState(false);
  const [abierta, setAbierta] = useState(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(true);

  const recargar = useCallback(async () => {
    if (!proyecto?.id) return;
    try {
      const [f, lista, herr] = await Promise.all([
        api.cicloLeerFicha(proyecto.id),
        api.cicloListarPruebas(proyecto.id),
        api.cicloHerramientas(),
      ]);
      setFicha(f.ficha);
      setPruebas(lista);
      setHerramientas(herr);
      setError("");
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setCargando(false);
    }
  }, [proyecto?.id]);

  useEffect(() => { setAbierta(null); setCargando(true); recargar(); }, [recargar]);

  async function crear() {
    setError("");
    try {
      const p = await api.cicloCrearPrueba(proyecto.id, origen, tributario);
      setOrigen("");
      setTributario(false);
      await recargar();
      setAbierta(p.id);
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  return (
    <div className="nf-ciclo">
      <p className="nf-eyebrow">PRUEBAS DEL ENCARGO · {proyecto.name}</p>
      {cargando && <p className="muted">Cargando…</p>}
      {error && <p role="alert" className="nf-error">{error}</p>}
      {!cargando && (
        <>
          <FichaEncargo proyecto={proyecto} cliente={cliente} ficha={ficha} onGuardada={setFicha} />

          <section className="nf-rec-panel">
            <p className="nf-eyebrow">2 · PRUEBAS</p>
            {ficha ? (
              <div className="nf-rec-row">
                <label className="nf-ctx-field" style={{ flex: 1 }}>
                  Nueva prueba
                  <select value={origen} onChange={(e) => setOrigen(e.target.value)}>
                    <option value="">Seleccione la herramienta…</option>
                    {herramientas.map((h) => (
                      <option key={h.origen} value={h.origen}>{h.nombre} · {h.tipo}</option>
                    ))}
                  </select>
                </label>
                <label className="nf-ctx-check">
                  <input type="checkbox" checked={tributario} onChange={(e) => setTributario(e.target.checked)} /> Incluye
                  tratamiento tributario
                </label>
                <button type="button" className="btn sm primary" disabled={!origen} onClick={crear}>Crear prueba</button>
              </div>
            ) : (
              <p className="muted">Guarde primero la ficha del encargo.</p>
            )}
            {pruebas.length === 0 ? (
              <p className="muted">Este encargo todavía no tiene pruebas.</p>
            ) : (
              <ul className="nf-consola-lista">
                {pruebas.map((p) => (
                  <li key={p.id}>
                    <button type="button" className={abierta === p.id ? "selected" : ""} onClick={() => setAbierta(abierta === p.id ? null : p.id)}>
                      <strong>{p.nombre} · v{p.version}</strong>
                      <small>{nombreEstado(p.estado)} · {ETAPAS[etapaDe(p.estado)]}</small>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {abierta && <Prueba key={abierta} id={abierta} onCambio={recargar} onAbrir={setAbierta} />}
        </>
      )}
    </div>
  );
}

// --- Encargos NIIF, independientes del Workspace -------------------------------
// El auditor elige o crea aquí el encargo (cliente + ejercicio + ficha); no
// tiene que ir a Workspaces ni cambiar el proyecto activo de arriba.

const RECORDAR = "nf_encargo_activo";
const recordado = () => { try { return Number(localStorage.getItem(RECORDAR)) || null; } catch { return null; } };
const recordar = (id) => { try { localStorage.setItem(RECORDAR, String(id)); } catch { /* sin almacenamiento */ } };

function NuevoEncargo({ onCreado, onCancelar }) {
  const [clientes, setClientes] = useState([]);
  const [clienteId, setClienteId] = useState("");
  const [nuevoCliente, setNuevoCliente] = useState("");
  const [nombre, setNombre] = useState("");
  const [ficha, setFicha] = useState(fichaInicial(""));
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  useEffect(() => { api.listClients().then(setClientes).catch(() => setClientes([])); }, []);

  function elegirCliente(id) {
    setClienteId(id);
    const c = clientes.find((x) => String(x.id) === String(id));
    if (c) setFicha((f) => ({ ...f, client: c.name, ruc: f.ruc || c.tax_id || "" }));
  }

  async function crear(e) {
    e.preventDefault();
    setOcupado(true);
    setError("");
    try {
      const datos = { nombre, ficha };
      if (clienteId) datos.client_id = Number(clienteId);
      else datos.cliente = nuevoCliente || ficha.client;
      onCreado(await api.cicloCrearEncargo(datos));
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <form className="nf-rec-panel" onSubmit={crear}>
      <p className="nf-eyebrow">NUEVO ENCARGO</p>
      <div className="nf-rec-row">
        <label className="nf-ctx-field">
          Cliente
          <select value={clienteId} onChange={(e) => elegirCliente(e.target.value)}>
            <option value="">— Cliente nuevo —</option>
            {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        {!clienteId && (
          <label className="nf-ctx-field">
            Nombre del cliente nuevo
            <input value={nuevoCliente} onChange={(e) => { setNuevoCliente(e.target.value); setFicha((f) => ({ ...f, client: e.target.value })); }} />
          </label>
        )}
        <label className="nf-ctx-field">
          Nombre del encargo
          <input value={nombre} placeholder={`Auditoría ${ficha.year || ""}`} onChange={(e) => setNombre(e.target.value)} />
        </label>
      </div>
      <p className="muted">Ficha del encargo: la usan todas sus pruebas (marco NIIF, corte, responsables).</p>
      <ContextFields value={ficha} onChange={setFicha} keys={CAMPOS_FICHA} />
      {error && <p role="alert" className="nf-error">{error}</p>}
      <div className="nf-estudio-botones">
        <button type="submit" className="btn sm primary" disabled={ocupado}>Crear encargo</button>
        {onCancelar && <button type="button" className="btn sm" onClick={onCancelar}>Cancelar</button>}
      </div>
    </form>
  );
}

export default function PruebasEncargo({ proyecto: workspace, herramienta = "" }) {
  const [encargos, setEncargos] = useState(null);
  const [sel, setSel] = useState(null);
  const [creando, setCreando] = useState(false);
  const [error, setError] = useState("");

  const cargar = useCallback(async () => {
    try {
      const lista = await api.cicloEncargos();
      setEncargos(lista);
      setSel((actual) => {
        const hay = (id) => lista.some((e) => e.id === id);
        if (hay(actual)) return actual;
        if (hay(recordado())) return recordado();
        if (hay(workspace?.id)) return workspace.id;
        return lista[0]?.id || null;
      });
      if (!lista.length) setCreando(true);
    } catch (e) {
      setError(e.message || String(e));
    }
  }, [workspace?.id]);
  useEffect(() => { cargar(); }, [cargar]);

  function elegir(id) {
    setSel(id);
    recordar(id);
    setCreando(false);
  }

  if (error) return <p role="alert" className="nf-error">{error}</p>;
  if (!encargos) return <p className="muted">Cargando encargos…</p>;
  const actual = encargos.find((e) => e.id === sel);

  return (
    <>
      <div className="nf-encargo-barra">
        <span className="nf-eyebrow">ENCARGO</span>
        <select value={sel || ""} onChange={(e) => elegir(Number(e.target.value))} aria-label="Encargo">
          {!encargos.length && <option value="">Todavía no hay encargos</option>}
          {encargos.map((e) => (
            <option key={e.id} value={e.id}>
              {e.cliente} · {e.nombre}{e.marco ? ` · ${e.marco}` : ""}{e.pruebas ? ` · ${e.pruebas} prueba(s)` : ""}
            </option>
          ))}
        </select>
        <button type="button" className="pc-chip accent" onClick={() => setCreando(true)}>+ Nuevo encargo</button>
      </div>
      {creando && (
        <NuevoEncargo
          onCreado={async (e) => { await cargar(); elegir(e.id); }}
          onCancelar={encargos.length ? () => setCreando(false) : null}
        />
      )}
      {!creando && actual && (
        <EncargoTrabajo key={actual.id} proyecto={{ id: actual.id, name: actual.nombre, module_code: "AUD" }} cliente={{ name: actual.cliente }} herramientaInicial={herramienta} />
      )}
    </>
  );
}
