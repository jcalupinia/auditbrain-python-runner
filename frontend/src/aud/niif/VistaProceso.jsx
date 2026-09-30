import { useEffect, useRef, useState } from "react";

import * as api from "../../api";
import { ChipDocumento, VistaTrabajo } from "./CicloVista";
import { prepararBaseTecnica, producir } from "./cicloOrquestacion";
import {
  avanceCarga,
  estaProcesada,
  estadoPrueba,
  estadoRequerimiento,
  puedeEncerar,
  puedeSubir,
  separarRequerimientos,
} from "./efectivoLogic";

/*
 * Vista de 3 pasos config-driven (tema oscuro navy). La MISMA vista sirve para
 * varias herramientas: recibe una `config` por procesador (ver procesoConfig.js)
 * con el encabezado, las tarjetas de requerimientos primarios y las tarjetas de
 * ejecución (con los requerimientos que cada una usa). Hoy la usan
 * «Efectivo y Equivalentes de Efectivo» (efectivo_equivalentes) y
 * «Planificación de la auditoría» (planificacion_nia); el branch por processor
 * está en PruebasEncargo.jsx. No reimplementa cédulas ni cálculos:
 *   1) Requerimientos de información  — tarjetas primarias + soporte colapsable (ChipDocumento).
 *   2) Procesamiento de información   — Procesar (producir) y Encerar (onAccion "erase").
 *   3) Ejecución de auditoría         — tarjetas que abren la vista de trabajo detallada existente,
 *                                       cada una mostrando a qué requerimientos está relacionada.
 *
 * No muestra consolas (ConsolaChat / ConsolaPrueba) ni el panel de gobierno.
 */

const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
const num = (v) =>
  v === null || v === undefined || v === "" || Number.isNaN(Number(v))
    ? String(v ?? "")
    : Number(v).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function descargar(nombre, contenido, tipo) {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Íconos del mockup (SVG inline, sin dependencias externas). Cada tarjeta declara su
// ícono por clave en procesoConfig.js.
const ICONOS = {
  chart: <><rect x="4" y="12" width="3.4" height="8" rx="1" fill="#2E6FC0" /><rect x="10.3" y="7" width="3.4" height="13" rx="1" fill="#4C8BE0" /><rect x="16.6" y="4" width="3.4" height="16" rx="1" fill="#7FB0EE" /></>,
  doc: <><path d="M6 2h8l4 4v16H6V2z" fill="#1E4E8C" /><path d="M14 2v4h4" fill="#2E6FC0" /><path d="M8.5 12h7M8.5 15h7M8.5 18h4.5" stroke="#CFE0F5" strokeWidth="1.3" strokeLinecap="round" /></>,
  pdf: <><path d="M6 2h8l4 4v16H6V2z" fill="#B03030" /><path d="M14 2v4h4" fill="#E5484D" /><text x="12" y="17.5" fontSize="5.6" fill="#fff" textAnchor="middle" fontWeight="700">PDF</text></>,
  shield: <><path d="M12 2l7 3v6c0 5-3 8-7 10-4-2-7-5-7-10V5l7-3z" fill="#C7A83C" /><path d="M8.7 11.7l2.3 2.3 4.3-4.6" stroke="#071B2F" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" /></>,
  bank: <><path d="M12 3l9 5H3l9-5z" fill="#9B8BE0" /><rect x="5" y="9" width="2.4" height="8" fill="#9B8BE0" /><rect x="10.8" y="9" width="2.4" height="8" fill="#9B8BE0" /><rect x="16.6" y="9" width="2.4" height="8" fill="#9B8BE0" /><rect x="3.5" y="18" width="17" height="2.4" rx="0.5" fill="#9B8BE0" /></>,
  list: <><circle cx="6" cy="7" r="1.4" fill="#2E6FC0" /><circle cx="6" cy="12" r="1.4" fill="#2E6FC0" /><circle cx="6" cy="17" r="1.4" fill="#2E6FC0" /><path d="M10 7h9M10 12h9M10 17h9" stroke="#4C8BE0" strokeWidth="1.6" strokeLinecap="round" /></>,
  table: <><rect x="4" y="5" width="16" height="14" rx="1.5" fill="none" stroke="#3AA6A0" strokeWidth="1.5" /><path d="M4 9.5h16M4 14h16M10 5v14" stroke="#3AA6A0" strokeWidth="1.2" /></>,
  search: <><circle cx="11" cy="11" r="5.3" fill="none" stroke="#3AA6A0" strokeWidth="1.8" /><path d="M15 15l4.2 4.2" stroke="#3AA6A0" strokeWidth="1.8" strokeLinecap="round" /></>,
  refresh: <path d="M6 9a7 7 0 0 1 12-2.5M18 6.5V3.5m0 3H15M18 15a7 7 0 0 1-12 2.5M6 17.5v3m0-3H9" fill="none" stroke="#3AA6A0" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />,
  calendar: <><rect x="4" y="5" width="16" height="15" rx="2" fill="none" stroke="#4C8BE0" strokeWidth="1.6" /><path d="M4 9.5h16M8 3v4M16 3v4" stroke="#4C8BE0" strokeWidth="1.6" strokeLinecap="round" /></>,
  dashboard: <><rect x="4" y="4" width="7" height="7" rx="1.2" fill="#2E6FC0" /><rect x="13" y="4" width="7" height="4" rx="1.2" fill="#4C8BE0" /><rect x="13" y="10" width="7" height="10" rx="1.2" fill="#2E6FC0" /><rect x="4" y="13" width="7" height="7" rx="1.2" fill="#4C8BE0" /></>,
  line: <><path d="M4 16l4-4 3 3 5-7 4 3" fill="none" stroke="#34d36a" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /><path d="M4 20h16" stroke="#2f6f45" strokeWidth="1.1" /></>,
  pie: <><path d="M12 3a9 9 0 1 0 9 9h-9V3z" fill="#9B8BE0" /><path d="M12.8 3.1A9 9 0 0 1 20.9 11.2H12.8V3.1z" fill="#C3B6EE" /></>,
  calc: <><rect x="5" y="3" width="14" height="18" rx="2" fill="none" stroke="#4C8BE0" strokeWidth="1.5" /><rect x="7.4" y="5.4" width="9.2" height="3.4" rx="0.6" fill="#4C8BE0" /><path d="M8 13h.01M12 13h.01M16 13h.01M8 17h.01M12 17h.01M16 17h.01" stroke="#4C8BE0" strokeWidth="2.1" strokeLinecap="round" /></>,
  warning: <><path d="M12 3.2l9 15.8H3L12 3.2z" fill="#E5484D" /><path d="M12 9.2v4.6M12 16.4v.4" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" /></>,
  gears: <><circle cx="10" cy="10" r="3" fill="none" stroke="#9AA8BD" strokeWidth="1.6" /><path d="M10 3.2v2.2M10 14.6v2.2M3.2 10h2.2M14.6 10h2.2M5.2 5.2l1.6 1.6M13.2 13.2l1.6 1.6M14.8 5.2l-1.6 1.6M6.8 13.2l-1.6 1.6" stroke="#9AA8BD" strokeWidth="1.5" strokeLinecap="round" /><circle cx="16.6" cy="16.6" r="2.2" fill="#9AA8BD" /></>,
};

function Icono({ name }) {
  return (
    <svg className="nf-ef-ico" viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
      {ICONOS[name] || ICONOS.doc}
    </svg>
  );
}

// Chips compactos con los requerimientos que usa una tarjeta de ejecución. Acepta
// una lista de ids (["RQ-001", …]) o la cadena "todos" (resumen general).
function Relacionados({ relacionados }) {
  if (!relacionados) return null;
  const todos = relacionados === "todos";
  const ids = todos ? [] : relacionados.filter(Boolean);
  if (!todos && ids.length === 0) return null;
  return (
    <span className="nf-ef-rel">
      <span className="nf-ef-rel-lbl">Usa</span>
      {todos ? (
        <span className="nf-ef-rel-chip todos">Todos los requerimientos</span>
      ) : (
        ids.map((id) => (
          <span key={id} className="nf-ef-rel-chip">{id}</span>
        ))
      )}
    </span>
  );
}

// Matriz del reproceso de la conciliación del último mes (endpoint /reproceso).
function MatrizReproceso({ datos, onDescargar }) {
  if (!datos) return null;
  if (!datos.disponible) return <p className="nf-ef-aviso">{datos.motivo}</p>;
  const filas = datos.matriz || [];
  if (!filas.length) return <p className="nf-ef-aviso">El reproceso no encontró cuentas con estado de cuenta y libro mayor cruzables.</p>;
  const cols = [
    ["banco", "Banco", false],
    ["saldo_extracto", "Saldo extracto", true],
    ["saldo_libros", "Saldo libros", true],
    ["saldo_auditoria", "Saldo s/auditoría", true],
    ["diferencia", "Diferencia", true],
    ["estado", "Estado", false],
    ["coincidencias", "Coincidencias", true],
    ["n_partidas_reproceso", "Partidas", true],
  ];
  return (
    <div className="nf-ef-matriz">
      <div className="nf-ef-matriz-h">
        <p className="nf-ef-eyebrow">REPROCESO DE CONCILIACIÓN — ÚLTIMO MES</p>
        <button type="button" className="nf-ef-btn" onClick={onDescargar}>↓ REPROCESO_CONCILIACION.xlsx</button>
      </div>
      <div className="nf-ef-scroll">
        <table>
          <thead>
            <tr>{cols.map(([k, t]) => <th key={k}>{t}</th>)}</tr>
          </thead>
          <tbody>
            {filas.map((f, i) => (
              <tr key={i}>
                {cols.map(([k, , n]) => (
                  <td key={k} className={n ? "nf-ef-num" : ""}>
                    {k === "estado" ? (
                      <span className={`nf-ef-badge ${String(f[k]).startsWith("CONCILIADA") ? "ok" : "warn"}`}>{f[k]}</span>
                    ) : n ? (
                      num(f[k])
                    ) : (
                      String(f[k] ?? "")
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function VistaProceso({ config, prueba, onAccion, onRecargar, ocupado }) {
  const reg = prueba.registro || {};
  const d = prueba.definicion || {};
  const estado = prueba.estado;
  const principalesConfig = config.principales || [];
  const ejecuciones = config.ejecuciones || [];
  const [trabajando, setTrabajando] = useState(false);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [verDetalle, setVerDetalle] = useState(false);
  const [encerando, setEncerando] = useState(false);
  const [cliente, setCliente] = useState("");
  const [reproceso, setReproceso] = useState(null);
  const detalleRef = useRef(null);

  // Requerimientos: los del registro si ya se generaron; si no, los de la definición
  // (para pintar las tarjetas antes de preparar la base técnica).
  const conRequerimiento = Array.isArray(reg.requests) && reg.requests.length > 0;
  const requests = conRequerimiento ? reg.requests : d.requests || [];
  const { principales, soporte } = separarRequerimientos(requests, principalesConfig);
  const coberturaMap = Object.fromEntries((prueba.cobertura || []).map((c) => [c.id, c]));
  const avance = avanceCarga(requests, prueba.cobertura);
  const habilitadoSubir = conRequerimiento && puedeSubir(estado) && !trabajando && !ocupado;
  const procesada = estaProcesada(estado);
  const bloqueado = trabajando || ocupado;
  const tieneExcepciones = ((reg.run || {}).exceptions || []).length > 0;
  const estadoTexto = estadoPrueba(estado, tieneExcepciones);

  useEffect(() => {
    if (verDetalle && detalleRef.current) detalleRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [verDetalle]);

  async function correr(fn) {
    setTrabajando(true);
    setError("");
    setAviso("");
    try {
      await fn();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setTrabajando(false);
      await onRecargar();
    }
  }

  const prepararRequerimiento = () => correr(() => prepararBaseTecnica(prueba));

  const procesar = () =>
    correr(async () => {
      const param = { ...(d.parametros || {}), ...(reg.parameters || {}) };
      await producir(prueba, { param });
      setAviso("Información procesada: ya se pueden abrir las pruebas de ejecución.");
    });

  async function encerar() {
    setError("");
    try {
      await onAccion("erase", { confirmClient: cliente, downloadConfirmed: true });
      setEncerando(false);
      setCliente("");
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  async function bajarModelo(reqId) {
    try {
      descargar(`Modelo_${reqId}.xlsx`, await api.cicloBajarModelo(prueba.id, reqId), XLSX);
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  async function descargarReprocesoExcel() {
    try {
      descargar("REPROCESO_CONCILIACION.xlsx", await api.cicloReprocesoExcel(prueba.id), XLSX);
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  // Abre la vista de trabajo detallada, desplazándose a esa sección. La tarjeta de
  // reproceso además consulta el endpoint y muestra la matriz.
  async function abrirEjecucion(item) {
    if (!procesada) return;
    setVerDetalle(true);
    if (item.reproceso) {
      setReproceso(null);
      try {
        setReproceso(await api.cicloReproceso(prueba.id));
      } catch (e) {
        setReproceso({ disponible: false, motivo: e.message || String(e) });
      }
    }
  }

  return (
    <div className="nf-ef">
      <div className="nf-ef-estado">
        <span className="nf-ef-eyebrow">{config.eyebrow}</span>
        <span className={`nf-ef-estado-badge ${estadoTexto === "CON EXCEPCIONES" ? "warn" : estadoTexto === "REVISADA" ? "ok" : ""}`}>
          {estadoTexto}
        </span>
      </div>
      {error && <p role="alert" className="nf-ef-error">{error}</p>}
      {aviso && <p className="nf-ef-ok">{aviso}</p>}

      {/* ===== Paso 1 · Requerimientos de información ===== */}
      <section className="nf-ef-paso">
        <header className="nf-ef-paso-h">
          <span className="nf-ef-num">1</span>
          <h3>Requerimientos de información</h3>
        </header>
        {!conRequerimiento && (
          <div className="nf-ef-preparar">
            <p>Todavía no se ha generado el requerimiento de documentos para este encargo.</p>
            <button type="button" className="nf-ef-btn accent" disabled={bloqueado} onClick={prepararRequerimiento}>
              {trabajando ? "Preparando…" : "Preparar el requerimiento de documentos"}
            </button>
          </div>
        )}
        <div className="nf-ef-cards">
          {principales.map((p) => (
            <div key={p.id} className="nf-ef-card">
              <div className="nf-ef-card-top">
                <Icono name={p.icono} />
                {(() => {
                  const er = estadoRequerimiento(p.id, coberturaMap, estado);
                  const cls = er === "Error" ? "err" : er === "Pendiente" ? "pend" : "ok";
                  return <span className={`nf-ef-badge ${cls}`}>{er.toUpperCase()}</span>;
                })()}
              </div>
              <h4 title={p.req.document}>{p.titulo}</h4>
              {p.tipos && <p className="nf-ef-card-tipos">({p.tipos})</p>}
              <ChipDocumento
                prueba={prueba}
                req={p.req}
                cobertura={coberturaMap[p.id]}
                onSubido={onRecargar}
                habilitado={habilitadoSubir}
                processor={d.processor}
                onModelo={bajarModelo}
              />
            </div>
          ))}
        </div>
        {!principales.length && conRequerimiento && (
          <p className="nf-ef-aviso">El requerimiento generado no trae las tarjetas primarias esperadas.</p>
        )}
        {requests.length > 0 && (
          <div className="nf-ef-progreso">
            <div className="nf-ef-barra"><span style={{ width: `${avance.pct}%` }} /></div>
            <span className="nf-ef-progreso-t">{avance.completos} de {avance.total} documentos obligatorios completos</span>
          </div>
        )}
        {soporte.length > 0 && (
          <details className="nf-ef-soporte">
            <summary>Documentos de soporte ({soporte.length})</summary>
            <div className="nf-ef-soporte-lista">
              {soporte.map((r) => (
                <div key={r.id} className="nf-ef-soporte-item">
                  <span className="nf-ef-soporte-nom">{r.document}</span>
                  <ChipDocumento
                    prueba={prueba}
                    req={r}
                    cobertura={coberturaMap[r.id]}
                    onSubido={onRecargar}
                    habilitado={habilitadoSubir}
                    processor={d.processor}
                    onModelo={bajarModelo}
                  />
                </div>
              ))}
            </div>
          </details>
        )}
      </section>

      {/* ===== Paso 2 · Procesamiento de información ===== */}
      <section className="nf-ef-paso">
        <header className="nf-ef-paso-h">
          <span className="nf-ef-num">2</span>
          <h3>Procesamiento de información</h3>
        </header>
        <div className="nf-ef-proc">
          <button type="button" className="nf-ef-grande verde" disabled={bloqueado || !conRequerimiento} onClick={procesar}>
            <span className="nf-ef-grande-t">{trabajando ? "Procesando…" : "Procesar"}</span>
            <span className="nf-ef-grande-s">Valida, consolida y genera los análisis</span>
          </button>
          <button
            type="button"
            className="nf-ef-grande rojo"
            disabled={bloqueado || !puedeEncerar(estado)}
            onClick={() => setEncerando((v) => !v)}
            title={puedeEncerar(estado) ? undefined : "La versión aprobada es evidencia del encargo (NIA 230): no se encera."}
          >
            <span className="nf-ef-grande-t">Encerar</span>
            <span className="nf-ef-grande-s">Limpia la información y resultados</span>
          </button>
        </div>
        {!puedeEncerar(estado) && (
          <p className="nf-ef-aviso">Esta versión está aprobada (NIA 230): no se reinicia ni se elimina. Cree una nueva versión para corregirla.</p>
        )}
        {encerando && puedeEncerar(estado) && (
          <div className="nf-ef-encerar">
            <p>Escriba el nombre del cliente tal como está en la ficha («{reg.engagement?.client}») para confirmar. Encerar borra evidencia, resultados e historial.</p>
            <div className="nf-ef-encerar-row">
              <input value={cliente} onChange={(e) => setCliente(e.target.value)} placeholder="Nombre del cliente" />
              <button type="button" className="nf-ef-btn rojo" disabled={bloqueado || !cliente.trim()} onClick={encerar}>Confirmar encerado</button>
              <button type="button" className="nf-ef-btn" onClick={() => setEncerando(false)}>Cancelar</button>
            </div>
          </div>
        )}
      </section>

      {/* ===== Paso 3 · Ejecución de auditoría ===== */}
      <section className="nf-ef-paso">
        <header className="nf-ef-paso-h">
          <span className="nf-ef-num">3</span>
          <h3>Ejecución de auditoría</h3>
        </header>
        {!procesada && <p className="nf-ef-aviso">Procese la información para habilitar las pruebas.</p>}
        <div className="nf-ef-ejec">
          {ejecuciones.map((e) => (
            <button
              key={e.clave}
              type="button"
              className={`nf-ef-ejec-card ${procesada ? "on" : "off"}`}
              disabled={!procesada}
              onClick={() => abrirEjecucion(e)}
            >
              <span className="nf-ef-ejec-head">
                <Icono name={e.icono} />
                <span className="nf-ef-ejec-tt">
                  <span className="nf-ef-ejec-t">{e.titulo}</span>
                  {e.subtitulo && <span className="nf-ef-ejec-s">{e.subtitulo}</span>}
                </span>
                <span className="nf-ef-ejec-flecha" aria-hidden="true">{procesada ? "›" : ""}</span>
              </span>
              <div className="nf-ef-ejec-pie">
                {procesada
                  ? <Relacionados relacionados={e.relacionados} />
                  : <span className="nf-ef-ejec-lock">🔒 BLOQUEADO</span>}
              </div>
            </button>
          ))}
        </div>
      </section>

      {/* ===== Vista de trabajo detallada (paso 3) ===== */}
      {verDetalle && (
        <section className="nf-ef-detalle" ref={detalleRef}>
          <div className="nf-ef-detalle-h">
            <button type="button" className="nf-ef-btn" onClick={() => { setVerDetalle(false); setReproceso(null); }}>
              ← Volver a los pasos
            </button>
          </div>
          {reproceso && <MatrizReproceso datos={reproceso} onDescargar={descargarReprocesoExcel} />}
          <VistaTrabajo prueba={prueba} onAccion={onAccion} onRecargar={onRecargar} ocupado={ocupado} />
        </section>
      )}
    </div>
  );
}
