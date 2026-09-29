import { useEffect, useRef, useState } from "react";

import * as api from "../../api";
import { ChipDocumento, VistaTrabajo } from "./CicloVista";
import { prepararBaseTecnica, producir } from "./cicloOrquestacion";
import {
  EJECUCIONES,
  avanceCarga,
  estaProcesada,
  estadoPrueba,
  estadoRequerimiento,
  puedeEncerar,
  puedeSubir,
  separarRequerimientos,
} from "./efectivoLogic";

/*
 * E7 · Vista de 3 pasos de «Efectivo y Equivalentes de Efectivo» (tema oscuro
 * navy). SOLO se monta cuando `prueba.definicion.processor === "efectivo_equivalentes"`
 * (el branch está en PruebasEncargo.jsx). No reimplementa cédulas ni cálculos:
 *   1) Requerimientos de información  — 4 tarjetas primarias + soporte colapsable (ChipDocumento).
 *   2) Procesamiento de información   — Procesar (producir) y Encerar (onAccion "erase").
 *   3) Ejecución de auditoría         — tarjetas que abren la vista de trabajo detallada existente.
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

// Ícono azul de documento (mockup): SVG inline, sin dependencias externas.
function IconoDoc() {
  return (
    <svg className="nf-ef-doc-ico" viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
      <path d="M6 2h8l4 4v16H6V2z" fill="#1E4E8C" />
      <path d="M14 2v4h4" fill="#2E6FC0" />
      <path d="M8.5 12h7M8.5 15h7M8.5 18h4.5" stroke="#CFE0F5" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}

// Matriz del reproceso de la conciliación del último mes (endpoint /reproceso).
function MatrizReproceso({ datos }) {
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
      <p className="nf-ef-eyebrow">REPROCESO DE CONCILIACIÓN — ÚLTIMO MES</p>
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

export default function VistaEfectivo({ prueba, onAccion, onRecargar, ocupado }) {
  const reg = prueba.registro || {};
  const d = prueba.definicion || {};
  const estado = prueba.estado;
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
  const { principales, soporte } = separarRequerimientos(requests);
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
        <span className="nf-ef-eyebrow">EFECTIVO Y EQUIVALENTES DE EFECTIVO</span>
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
                <IconoDoc />
                {(() => {
                  const er = estadoRequerimiento(p.id, coberturaMap, estado);
                  const cls = er === "Error" ? "err" : er === "Pendiente" ? "pend" : "ok";
                  return <span className={`nf-ef-badge ${cls}`}>{er}</span>;
                })()}
              </div>
              <h4>{p.titulo}</h4>
              <p className="nf-ef-card-doc">{p.req.document}</p>
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
          {EJECUCIONES.map((e) => (
            <button
              key={e.clave}
              type="button"
              className={`nf-ef-ejec-card ${procesada ? "on" : "off"}`}
              disabled={!procesada}
              onClick={() => abrirEjecucion(e)}
            >
              <span className="nf-ef-ejec-t">{e.titulo}</span>
              <span className="nf-ef-ejec-flecha" aria-hidden="true">→</span>
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
          {reproceso && <MatrizReproceso datos={reproceso} />}
          <VistaTrabajo prueba={prueba} onAccion={onAccion} onRecargar={onRecargar} ocupado={ocupado} />
        </section>
      )}
    </div>
  );
}
