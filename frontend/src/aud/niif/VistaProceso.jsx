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

// Familias de color de las fichas de ícono (fondo degradado + glow del mismo color).
// El glifo va en blanco encima. Cada tarjeta puede fijar su `color` en procesoConfig.js;
// si no, se deriva del ícono con COLOR_POR_ICONO.
const COLORES = {
  blue: ["#3D7FE0", "#2456B8"],
  green: ["#35C15E", "#1F9E45"],
  gold: ["#D9B441", "#AE861C"],
  purple: ["#8E7BEA", "#6A52CC"],
  red: ["#EF5A5E", "#C62F34"],
  teal: ["#33BFB4", "#1F8C84"],
};
const COLOR_POR_ICONO = {
  doc: "blue", book: "blue", people: "gold", shield: "red", bank: "purple", building: "purple",
  list: "blue", table: "green", search: "teal", refresh: "blue", calendar: "purple", clock: "purple",
  box: "blue", sliders: "blue", calc: "blue", warning: "red", gears: "blue", chart: "gold",
  pdf: "red", pie: "gold", line: "green", dashboard: "blue",
};

// Íconos en blanco (line-art) para ir dentro de una ficha de color. Cada tarjeta declara
// su ícono por clave en procesoConfig.js.
const W = "#fff";
const ICONOS = {
  doc: <><path d="M7 3h6l4 4v14H7z" fill="none" stroke={W} strokeWidth="1.7" strokeLinejoin="round" /><path d="M13 3v4h4" fill="none" stroke={W} strokeWidth="1.7" strokeLinejoin="round" /><path d="M9.5 12.5h5M9.5 15.5h5M9.5 18.5h3" stroke={W} strokeWidth="1.5" strokeLinecap="round" /></>,
  book: <><path d="M12 6.2C10.4 5 8 4.6 5.4 5.1v12.8c2.6-.5 5-.1 6.6 1.1 1.6-1.2 4-1.6 6.6-1.1V5.1C16.6 4.6 14 5 12 6.2z" fill="none" stroke={W} strokeWidth="1.6" strokeLinejoin="round" /><path d="M12 6.2v12.8" stroke={W} strokeWidth="1.4" /></>,
  people: <><circle cx="9.2" cy="8.4" r="2.7" fill={W} /><path d="M3.8 19c0-3 2.4-5.2 5.4-5.2s5.4 2.2 5.4 5.2z" fill={W} /><circle cx="16.6" cy="9" r="2.1" fill="#ffffffcc" /><path d="M15 13.9c2.7.1 4.9 2.3 4.9 5.1" fill="none" stroke="#ffffffcc" strokeWidth="1.7" strokeLinecap="round" /></>,
  shield: <><path d="M12 3l7 2.8v5.4c0 4.6-3 7.6-7 9.4-4-1.8-7-4.8-7-9.4V5.8L12 3z" fill="none" stroke={W} strokeWidth="1.7" strokeLinejoin="round" /><path d="M9 12l2.2 2.2 4-4.5" fill="none" stroke={W} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></>,
  bank: <><path d="M12 3.2l8.5 4.3H3.5L12 3.2z" fill={W} /><path d="M6 9.6v6.8M10 9.6v6.8M14 9.6v6.8M18 9.6v6.8" stroke={W} strokeWidth="1.8" strokeLinecap="round" /><path d="M4 18.8h16" stroke={W} strokeWidth="2" strokeLinecap="round" /></>,
  list: <><circle cx="5.5" cy="7" r="1.5" fill={W} /><circle cx="5.5" cy="12" r="1.5" fill={W} /><circle cx="5.5" cy="17" r="1.5" fill={W} /><path d="M9.5 7h9M9.5 12h9M9.5 17h9" stroke={W} strokeWidth="1.7" strokeLinecap="round" /></>,
  table: <><rect x="4" y="5" width="16" height="14" rx="2" fill="none" stroke={W} strokeWidth="1.6" /><path d="M4 9.5h16M4 14h16M10 5v14" stroke={W} strokeWidth="1.4" /></>,
  search: <><circle cx="11" cy="11" r="5.4" fill="none" stroke={W} strokeWidth="1.9" /><path d="M15.1 15.1l4.4 4.4" stroke={W} strokeWidth="2.1" strokeLinecap="round" /></>,
  refresh: <path d="M6 9a7 7 0 0 1 12-2.5M18 6.5V3.5m0 3H15M18 15a7 7 0 0 1-12 2.5M6 17.5v3m0-3H9" fill="none" stroke={W} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />,
  calendar: <><rect x="4" y="5" width="16" height="15" rx="2.4" fill="none" stroke={W} strokeWidth="1.7" /><path d="M4 9.6h16M8 3v4M16 3v4" stroke={W} strokeWidth="1.7" strokeLinecap="round" /></>,
  clock: <><circle cx="12" cy="12" r="8" fill="none" stroke={W} strokeWidth="1.7" /><path d="M12 7.4V12l3.2 2.1" fill="none" stroke={W} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></>,
  box: <><path d="M12 3l8 4v10l-8 4-8-4V7l8-4z" fill="none" stroke={W} strokeWidth="1.6" strokeLinejoin="round" /><path d="M4 7l8 4 8-4M12 11v10" fill="none" stroke={W} strokeWidth="1.6" strokeLinejoin="round" /></>,
  sliders: <><path d="M4 8h9M17 8h3M4 16h3M11 16h9" stroke={W} strokeWidth="1.8" strokeLinecap="round" /><circle cx="15" cy="8" r="2.4" fill="none" stroke={W} strokeWidth="1.8" /><circle cx="9" cy="16" r="2.4" fill="none" stroke={W} strokeWidth="1.8" /></>,
  calc: <><rect x="5" y="3" width="14" height="18" rx="2.4" fill="none" stroke={W} strokeWidth="1.6" /><rect x="8" y="6" width="8" height="3" rx="0.8" fill={W} /><path d="M8.5 13h.01M12 13h.01M15.5 13h.01M8.5 17h.01M12 17h.01M15.5 17h.01" stroke={W} strokeWidth="2.2" strokeLinecap="round" /></>,
  warning: <><path d="M12 3.6l8.4 14.8a1 1 0 0 1-.87 1.5H4.47a1 1 0 0 1-.87-1.5L12 3.6z" fill="none" stroke={W} strokeWidth="1.7" strokeLinejoin="round" /><path d="M12 9.4v4.4M12 16.6v.2" stroke={W} strokeWidth="1.9" strokeLinecap="round" /></>,
  gears: <><circle cx="12" cy="12" r="3" fill="none" stroke={W} strokeWidth="1.7" /><path d="M12 4.2v2.3M12 17.5v2.3M4.2 12h2.3M17.5 12h2.3M6.5 6.5l1.6 1.6M15.9 15.9l1.6 1.6M17.5 6.5l-1.6 1.6M8.1 15.9l-1.6 1.6" stroke={W} strokeWidth="1.7" strokeLinecap="round" /></>,
  chart: <><rect x="4.5" y="12" width="3.4" height="7.5" rx="1.2" fill={W} /><rect x="10.3" y="7.5" width="3.4" height="12" rx="1.2" fill={W} /><rect x="16.1" y="4.5" width="3.4" height="15" rx="1.2" fill="#ffffffcc" /></>,
  pdf: <><path d="M7 3h6l4 4v14H7z" fill="none" stroke={W} strokeWidth="1.7" strokeLinejoin="round" /><path d="M13 3v4h4" fill="none" stroke={W} strokeWidth="1.7" strokeLinejoin="round" /><text x="12" y="18" fontSize="5.4" fill={W} textAnchor="middle" fontWeight="700">PDF</text></>,
  pie: <><circle cx="12" cy="12" r="8" fill="none" stroke={W} strokeWidth="1.7" /><path d="M12 12V4M12 12l7 3.6" stroke={W} strokeWidth="1.7" strokeLinecap="round" /></>,
  line: <><path d="M4 16l4-4 3 3 5-7 4 3" fill="none" stroke={W} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /><path d="M4 20h16" stroke="#ffffff88" strokeWidth="1.2" /></>,
  dashboard: <><rect x="4" y="4" width="7" height="7" rx="1.6" fill={W} /><rect x="13" y="4" width="7" height="4" rx="1.6" fill="#ffffffcc" /><rect x="13" y="10" width="7" height="10" rx="1.6" fill={W} /><rect x="4" y="13" width="7" height="7" rx="1.6" fill="#ffffffcc" /></>,
};
ICONOS.building = ICONOS.bank;

function Icono({ name, color }) {
  const fam = color || COLOR_POR_ICONO[name] || "blue";
  const [a, b] = COLORES[fam] || COLORES.blue;
  return (
    <svg
      className="nf-ef-ico"
      viewBox="0 0 24 24"
      width="24"
      height="24"
      aria-hidden="true"
      style={{
        background: `linear-gradient(150deg, ${a}, ${b})`,
        boxShadow: `inset 0 1px 0 rgba(255,255,255,0.24), 0 5px 13px ${b}59`,
      }}
    >
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
                <Icono name={p.icono} color={p.color} />
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
                <Icono name={e.icono} color={e.color} />
                <span className="nf-ef-ejec-tt">
                  <span className="nf-ef-ejec-t">{e.titulo}</span>
                  {e.subtitulo && <span className="nf-ef-ejec-s">{e.subtitulo}</span>}
                </span>
                <span className="nf-ef-ejec-flecha" aria-hidden="true">{procesada ? "›" : ""}</span>
              </span>
              <div className="nf-ef-ejec-pie">
                {procesada ? (
                  <>
                    <span className="nf-ef-ejec-badge">DISPONIBLE</span>
                    <Relacionados relacionados={e.relacionados} />
                  </>
                ) : (
                  <span className="nf-ef-ejec-lock">🔒 BLOQUEADO</span>
                )}
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
