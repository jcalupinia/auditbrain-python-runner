import { useEffect, useMemo, useRef, useState } from "react";

import * as api from "../../api";
import "../of/ofWorkspace.css";
import EjercicioModelo from "./EjercicioModelo";
import { ejemploDe, formatosTexto } from "./ejemplosRequerimientos";
import {
  archivosDe,
  detalleRequerimiento,
  erroresLegibles,
  estadoTributario,
  formulasLegibles,
  herramientaDePrueba,
  marcoAplicable,
  mejorEncabezado,
  niasDe,
  nombreEstado,
  pasoPreparar,
  problemasDe,
  textoTributarioInicial,
  tramosDeTexto,
} from "./cicloLogic";

/*
 * E10 · Vista de trabajo de una prueba, con la disposición del Workspace de
 * Obligaciones Fiscales: barra de acciones (Procesar · Descargar Excel ·
 * Encerar), base técnica, botones para subir cada documento, avance, tarjetas
 * de cédulas y resultado.
 *
 * «Confirmar base técnica» y «Procesar» no traen reglas nuevas: encadenan las
 * acciones del circuito que ya valida el servidor (cada una queda en la
 * bitácora). Miran el estado actual y hacen solo lo que falta.
 */

const cargarSitio = () =>
  Promise.all([import("./sitio/tools/domain.mjs"), import("./sitio/tools/exports.mjs"), import("./sitio/tools/files.mjs")]);

const FLOW_FIELDS = [
  { key: "id", label: "Contrato", type: "text" },
  { key: "fecha", label: "Fecha del pago", type: "date" },
  { key: "importe", label: "Importe", type: "number" },
];
const ANTES_DEL_REQUERIMIENTO = ["PRUEBA_SELECCIONADA", "PROGRAMA_PROPUESTO", "PROGRAMA_APROBADO", "REQUERIMIENTO_GENERADO"];
const CON_SUBIDA = ["REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA"];
const PROCESADA = ["PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS"];
// Qué documentos alimentan cada cédula: los de cálculo, salvo las de contexto.
const DE_CONTEXTO = { "01_Caratula": "Ficha del encargo", "02_Programa": "Programa de la ficha", "04_Fuentes": "Base técnica", "11_Conclusion": "Análisis del auditor", "12_Control_Revision": "Bitácora" };

const ETIQUETA_PARAM = {
  tasaDesc: "Tasa efectiva (%)", plazoBase: "Plazo de cobro (meses)", umbralGrave: "Mora grave (días)",
  umbralIndividual: "Saldo significativo", pctDeducible: "Límite anual (%)", pctLimite: "Límite acumulado (%)",
  tasaImp: "Tasa del impuesto (%)", provFiscalAnt: "Provisión fiscal anterior", dtaIniManual: "Diferido inicial",
};
// Formatos del papel de un procesador (el Excel va en «Descargar Excel»).
const FORMATOS_PAPEL = [
  ["docx", "Word", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
  ["pptx", "PowerPoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation"],
  ["html", "HTML sin conexión (y PDF)", "text/html;charset=utf-8"],
];
// Procesadores instalados por ficha (cartera con tramos de mora); los demás son herramientas del catálogo.
const PROC_FICHA = ["perdidas_incurridas_s11", "pce_simplificada_niif9"];
// Saldo escrito por el auditor («125.000,00» o «125000.00») al formato del servidor (punto decimal, sin miles).
export const saldoMayor = (t) => {
  const x = String(t || "").trim().replace(/\s/g, "");
  return x.includes(",") ? x.replace(/\./g, "").replace(",", ".") : x;
};
const esNumero = (v) => v !== null && v !== "" && !Number.isNaN(Number(v));
const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
// Qué alimenta cada cédula de un procesador, según su nombre.
const fuenteCedula = (nombre, anexos) =>
  /Resumen/.test(nombre) ? "Resume todas las cédulas"
    : /Parametros/.test(nombre) ? "Parámetros de la prueba"
    : /Problemas/.test(nombre) ? "Resultado del cálculo"
    : /Asientos|Ajuste/.test(nombre) ? "Cédulas de cálculo anteriores"
    : plural(anexos, "anexo del cliente", "anexos del cliente");
const TRAMOS_PI = [
  ["pv", "Corriente"], ["t30", "1 a 30 días"], ["t60", "31 a 60 días"], ["t90", "61 a 90 días"],
  ["t180", "91 a 180 días"], ["t360", "181 a 360 días"], ["t730", "361 a 730 días"], ["tmax", "Más de 730 días"],
].map(([k, tramo]) => ({ k, tramo }));

function descargar(nombre, contenido, tipo) {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
const mostrar = (v) => (v && typeof v === "object" ? String(v.v ?? v.n ?? "") : String(v ?? ""));

function ChipDocumento({ prueba, req, cobertura, onSubido, habilitado, processor, onModelo }) {
  const input = useRef(null);
  const [parte, setParte] = useState(req.components?.[0] || "");
  const [error, setError] = useState("");
  const [subiendo, setSubiendo] = useState(false);
  const completo = cobertura?.complete;
  const n = (prueba.archivos || []).filter((a) => a.requerimiento === req.id && a.estado !== "rechazado").length;
  // Flecha para bajar el FORMATO VÁLIDO: un ejemplo lleno del manifiesto, o el
  // modelo en blanco del propio requerimiento, o nada (solo los formatos).
  const ejemplo = ejemploDe(processor, req, undefined, import.meta.env.BASE_URL || "/");
  const formatos = formatosTexto(req);
  // El selector filtra a los formatos aceptados y permite elegir varios de una.
  const accept = (req.formats || []).map((f) => `.${String(f).toLowerCase()}`).join(",") || undefined;

  async function subir(e) {
    const archivos = Array.from(e.target.files || []);
    e.target.value = "";
    if (!archivos.length) return;
    setSubiendo(true);
    setError("");
    const fallos = [];
    // Se suben uno por uno (el backend recibe un archivo por request), pero el
    // auditor puede elegir varios de una en el selector.
    for (const archivo of archivos) {
      try {
        await api.cicloSubirArchivo(prueba.id, prueba.revision, req.id, parte, archivo);
      } catch (err) {
        fallos.push(`${archivo.name}: ${err.message || String(err)}`);
      }
    }
    try {
      await onSubido();
    } catch (err) {
      fallos.push(err.message || String(err));
    }
    setError(fallos.join(" · "));
    setSubiendo(false);
  }

  return (
    <span className="nf-vista-doc">
      {req.components?.length > 0 && (
        <select value={parte} onChange={(e) => setParte(e.target.value)} aria-label={`Parte de ${req.id}`} disabled={!habilitado}>
          {req.components.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      )}
      <button
        type="button"
        className={`pc-chip ${completo ? "on" : req.required !== false ? "warn" : ""}`}
        disabled={!habilitado || subiendo}
        title={[req.id, req.purpose, ...detalleRequerimiento(req), "Puede seleccionar varios archivos a la vez"].filter(Boolean).join(" · ")}
        onClick={() => input.current?.click()}
        data-requerimiento={req.id}
      >
        {subiendo ? "Subiendo…" : `${completo ? "✓" : "○"} ${req.document}${n ? ` (${n})` : ""}`}
      </button>
      <input ref={input} type="file" multiple accept={accept} hidden onChange={subir} data-requerimiento={req.id} />
      {(formatos || ejemplo) && (
        <small className="nf-doc-formatos">
          {formatos && (
            <span title="Formatos aceptados para este documento">
              {formatos}
              {req.required === false ? " · opcional" : ""}
            </span>
          )}
          {ejemplo?.tipo === "ejemplo" && (
            <a
              className="link nf-doc-ejemplo"
              href={ejemplo.url}
              download={ejemplo.archivo}
              title="Formato válido con datos de ejemplo (ficticios)"
              data-ejemplo={req.id}
            >
              ↓ Ejemplo
            </a>
          )}
          {ejemplo?.tipo === "modelo" && (
            <button
              type="button"
              className="link nf-doc-ejemplo"
              onClick={() => onModelo?.(req.id)}
              title="Formato válido (plantilla en blanco para llenar)"
              data-ejemplo={req.id}
            >
              ↓ Ejemplo
            </button>
          )}
        </small>
      )}
      {error && <small className="nf-error">{error}</small>}
    </span>
  );
}

function BaseTecnica({ prueba, taxScope, setTaxScope, taxConforme, setTaxConforme, gate }) {
  const d = prueba.definicion, reg = prueba.registro;
  const sugerido = d.tributario_sugerido;
  const marco = marcoAplicable(d, reg.engagement?.framework);
  const nias = niasDe(d);
  const formulas = d.processor
    ? (d.calculo || []).map((texto, i) => ({ key: i, texto, principal: PROC_FICHA.includes(d.processor) && i === d.calculo.length - 1 }))
    : formulasLegibles(d);
  const etiqueta = (k) => d.fields.find((f) => f.key === k)?.label || d.rules.find((r) => r.key === k)?.label || k;
  return (
    <details className="pc-panel nf-vista-base" open={ANTES_DEL_REQUERIMIENTO.includes(prueba.estado)}>
      <summary className="pc-panel-h">
        <span className="pc-panel-t">Base técnica y qué se calcula</span>
        <span className="pc-panel-m">{reg.engagement?.framework}</span>
      </summary>
      <div className="pc-panel-b">
        <div className="nf-vista-marco">
          <span>Esta herramienta aplica a: <strong>{marco.marcos.join(" y ")}</strong></span>
          <span>Marco de este encargo: <strong className={marco.sirve ? "nf-ok" : "nf-error"}>{marco.encargo}</strong></span>
        </div>
        {!marco.sirve && (
          <p role="alert" className="nf-error">
            Esta herramienta no es para {marco.encargo}: sus cálculos siguen {marco.marcos.join(" y ")}. Use una ficha diseñada para ese marco.
          </p>
        )}
        <p className="nf-eyebrow">NORMA CONTABLE</p>
        <ul className="nf-vista-lista">
          {marco.normas.map((n) => (
            <li key={n.marco} className={n.aplica ? "" : "muted"}>
              <strong>{n.marco}:</strong> {n.texto} · {n.aplica ? <span className="nf-ok">se aplica en este encargo</span> : "referencia"}
            </li>
          ))}
          {reg.taxApplicable && <li><strong>Tributario:</strong> {reg.sources.find((s) => s.category === "TRIBUTARIA")?.document}</li>}
        </ul>
        <p className="nf-eyebrow">QUÉ DICEN LAS NIA SOBRE ESTA PRUEBA</p>
        {nias.length ? (
          <div className="nf-estudio-scroll nf-estudio-tabla">
            <table>
              <thead><tr><th>Norma</th><th>Párrafos</th><th>Qué exige en esta prueba</th></tr></thead>
              <tbody>
                {nias.map((x) => <tr key={x.document}><td>{x.document}</td><td>{x.section}</td><td>{x.requirement}</td></tr>)}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="nf-error">La ficha no declara sus NIA: complétela antes de aplicar la prueba.</p>
        )}
        {(d.summary || d.description) && <p className="muted">{d.summary || d.description}</p>}
        <p className="nf-eyebrow">QUÉ SE CALCULA</p>
        <ol className="nf-vista-lista">
          {formulas.map((f) => <li key={f.key} className={f.principal ? "nf-ok" : ""}>{f.texto}{f.principal ? " · resultado principal" : ""}</li>)}
        </ol>
        {d.processor && !PROC_FICHA.includes(d.processor) && reg.run?.labels?.[d.primary] && (
          <p className="nf-ok">Resultado principal: {reg.run.labels[d.primary]}.</p>
        )}
        <p className="muted">Se concilia con el mayor: {etiqueta(d.control)}.</p>
        {(reg.program || []).length > 0 && (
          <details>
            <summary>Programa ({reg.program.length} procedimientos)</summary>
            <ul>{reg.program.map((p) => <li key={p.code}>{p.code} · {p.objective} · {p.procedure}{p.reference ? ` · ${p.reference}` : ""}</li>)}</ul>
          </details>
        )}
        {reg.taxApplicable && ANTES_DEL_REQUERIMIENTO.includes(prueba.estado) && (
          <div className="nf-tributario">
            <label className="nf-ctx-field">
              Tratamiento tributario revisado y su sustento
              {sugerido?.texto && (
                <small className="muted">
                  Viene pre-llenado con la base legal sugerida de esta herramienta. Revísela, edítela y confírmela contra la fuente oficial.
                  {sugerido.tiene_verificar && <> Hay citas marcadas <strong>«VERIFICAR»</strong>: resuélvalas antes de confirmar.</>}
                </small>
              )}
              <textarea rows={5} value={taxScope} onChange={(e) => setTaxScope(e.target.value)} />
            </label>
            <label className="nf-ctx-check">
              <input type="checkbox" checked={!!taxConforme} onChange={(e) => setTaxConforme(e.target.checked)} />{" "}
              Revisé la base legal sugerida y estoy conforme.
            </label>
            {gate && !gate.ok && <p className="nf-error" role="status">No se puede confirmar todavía: {gate.motivo}</p>}
          </div>
        )}
      </div>
    </details>
  );
}

const FORMATO = {
  n: (v) => Number(v).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  p: (v) => `${(Number(v) * 100).toLocaleString("es-EC", { maximumFractionDigits: 2 })} %`,
  i: (v) => Number(v).toLocaleString("es-EC"),
  a: (v) => String(Math.trunc(Number(v))),   // año: 2025, nunca «2.025»
};
// Una celda calculada llega como {f: fórmula, v: valor}: se muestra el valor y la fórmula al pasar el cursor.
const valorDe = (v) => (v && typeof v === "object" ? v.v : v);
export const celda = (v, f) => {
  const x = valorDe(v);
  if (x === null || x === undefined || x === "") return "";
  const formato = FORMATO[f] || (f === "x" ? FORMATO.n : null);
  // Texto dentro de una columna numérica («TOTAL», «No aplica»): se muestra tal cual, igual que en el Excel.
  return formato && esNumero(x) ? formato(x) : String(x);
};

function CedulaProcesador({ hoja }) {
  const filas = hoja.total ? [...hoja.rows, hoja.total] : hoja.rows;
  return (
    <div className="nf-estudio-scroll nf-estudio-tabla">
      <table>
        <thead><tr>{hoja.cols.map(([t]) => <th key={t}>{t}</th>)}</tr></thead>
        <tbody>
          {filas.map((r, i) => (
            <tr key={i} style={hoja.total && i === filas.length - 1 ? { fontWeight: 700 } : undefined}>
              {r.map((v, j) => (
                <td key={j} title={v && typeof v === "object" ? `=${v.f}` : undefined}
                  style={FORMATO[hoja.cols[j][1]] ? { textAlign: "right", whiteSpace: "nowrap" } : undefined}>
                  {celda(v, hoja.cols[j][1])}
                </td>
              ))}
            </tr>
          ))}
          {!filas.length && <tr><td colSpan={hoja.cols.length} className="muted">Sin partidas.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function PanelCedula({ prueba, indice, etiqueta, nombre, hojas, notas, calculo }) {
  const reg = prueba.registro;
  const hoja = hojas?.[indice];
  const derivada = prueba.definicion.processor && /Resumen|Parametros|Problemas|Asientos|Ajuste/.test(nombre || "");
  const fuente = DE_CONTEXTO[nombre] || (derivada ? fuenteCedula(nombre, calculo.length) : calculo.map((r) => r.document).join(" · "));
  return (
    <section className="pc-panel">
      <header className="pc-panel-h">
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <span className="pc-code">{String(indice + 1).padStart(2, "0")}</span>
          <span className="pc-panel-t">{etiqueta}</span>
        </div>
        <span className="pc-panel-m">{reg.run ? "GENERADA" : "PENDIENTE"}</span>
      </header>
      <div className="pc-panel-b">
        <p className="muted">Se alimenta de: {fuente}</p>
        {!reg.run || !hoja ? (
          <p className="muted">Se llena al pulsar «Procesar».</p>
        ) : hoja.cols ? (
          <CedulaProcesador hoja={hoja} />
        ) : (
          <>
            <div className="nf-estudio-scroll nf-estudio-tabla">
              <table>
                <tbody>
                  {hoja.map((r, i) => (
                    <tr key={i}>
                      {r.map((v, j) => (
                        <td key={j}>
                          {mostrar(v)}
                          {v?.f && (
                            <details>
                              <summary>Fórmula</summary>
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
            {notas?.[indice] && <p className="nf-nota"><strong>Cómo se prepara y calcula:</strong> {notas[indice]}</p>}
          </>
        )}
      </div>
    </section>
  );
}

export function VistaTrabajo({ prueba, onAccion, onRecargar, ocupado }) {
  const reg = prueba.registro;
  const d = prueba.definicion;
  const [sitio, setSitio] = useState(null);
  const [avance, setAvance] = useState("");
  const [error, setError] = useState("");
  const [trabajando, setTrabajando] = useState(false);
  const [mayor, setMayor] = useState("");
  const [taxScope, setTaxScope] = useState(() => textoTributarioInicial(reg, d));
  const [taxConforme, setTaxConforme] = useState(false);
  const [tramos, setTramos] = useState([{ min: "0", max: "30", rate: "" }, { min: "31", max: "", rate: "" }]);
  const [cedula, setCedula] = useState(0);
  const [modeloAbierto, setModeloAbierto] = useState(false);
  const [param, setParam] = useState(() => ({ ...(d.parametros || {}), ...Object.fromEntries(Object.entries(reg.parameters || {}).filter(([k]) => k in (d.parametros || {}))) }));
  const [tasas, setTasas] = useState(reg.parameters?.tasas || {});
  // Tramos de mora solo en las pruebas de cartera que los usan.
  const tramosVista = reg.run?.detalle?.tasas || d.tramos || (PROC_FICHA.includes(d.processor) ? TRAMOS_PI : null);

  useEffect(() => { cargarSitio().then(setSitio).catch((e) => setError(e.message || String(e))); }, []);

  const modelos = prueba.modelos || [];
  const calculo = (reg.requests || []).filter((r) => modelos.includes(r.id));
  const cobertura = Object.fromEntries((prueba.cobertura || []).map((c) => [c.id, c]));
  const obligatorios = (reg.requests || []).filter((r) => r.required !== false);
  const completos = obligatorios.filter((r) => cobertura[r.id]?.complete).length;
  const t = useMemo(() => herramientaDePrueba(prueba), [prueba]);
  const armado = useMemo(() => {
    if (d.processor)
      return { etiquetas: (d.cedulas || []).map(([, l]) => l), nombres: (d.cedulas || []).map(([n]) => n), hojas: reg.run?.hojas || null };
    if (!sitio) return null;
    const [, exp] = sitio;
    try {
      return { etiquetas: exp.sheetLabels(d), nombres: exp.sheetNames(d), hojas: reg.run ? exp.workbookSheets(t) : null };
    } catch (e) {
      return { error: e.message || String(e) };
    }
  }, [sitio, t, d, reg.run]);
  const [notas, setNotas] = useState(null);
  useEffect(() => {
    if (!reg.run || d.processor) return setNotas(null);
    import("./sitio/tools/explanations.mjs").then((m) => setNotas(m.calculationNotes(t))).catch(() => setNotas(null));
  }, [t, reg.run]);

  // Aplica una acción y devuelve la prueba fresca: los orquestadores avanzan sobre ella.
  async function paso(accion, datos = {}) {
    setAvance(`${nombreEstado(prueba.estado)} → ${accion}…`);
    await api.cicloAccion(prueba.id, accion, (await api.cicloLeerPrueba(prueba.id)).revision, datos);
    return api.cicloLeerPrueba(prueba.id);
  }

  async function correr(fn) {
    setTrabajando(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setAvance("");
      setTrabajando(false);
      await onRecargar();
    }
  }

  const confirmar = () => correr(async () => {
    let p = await api.cicloLeerPrueba(prueba.id);
    for (let i = 0; i < 8; i++) {
      const siguiente = pasoPreparar(p, taxScope, taxConforme);
      if (!siguiente) return;
      p = await paso(...siguiente);
    }
  });

  // Gate del tratamiento tributario: por qué NO se habilita «Confirmar base técnica».
  const gateTributario = estadoTributario(reg.taxApplicable, taxScope, taxConforme);

  // Mapea cada archivo de cálculo en el navegador (con el lector del sitio) y
  // manda al servidor la lista para unirla en una sola población.
  async function mapear(p) {
    const [, , files] = sitio || (await cargarSitio());
    const armar = async (req, campos) => {
      const partes = [];
      for (const a of archivosDe(p, req)) {
        const bytes = await api.cicloBajarArchivo(p.id, a.id);
        const elegido = mejorEncabezado(files.readSpreadsheet(bytes, a.nombre).sheets, campos);
        if (!elegido) throw new Error(`${a.nombre}: no se pudo leer ninguna hoja.`);
        if (elegido.faltan.length)
          throw new Error(`${a.nombre}: no se reconocen las columnas ${elegido.faltan.join(", ")}. Use el modelo de ${req} o el mapeo manual del circuito detallado.`);
        partes.push({ fileId: a.id, sheet: elegido.sheet, header: elegido.header, mapping: elegido.mapping });
      }
      return partes;
    };
    if (d.processor) {
      const datasets = {};
      for (const r of p.registro.requests.filter((x) => x.dataset)) {
        const tipo = d.tipos?.[r.dataset] || (["a1", "a2", "a3"].includes(r.dataset) ? "cartera" : r.dataset);
        const partes = await armar(r.id, d.campos[tipo]);
        if (partes.length) datasets[r.dataset] = partes;
      }
      if (!datasets.a3 && !datasets.actual) throw new Error("Suba el anexo de cartera del ejercicio corriente antes de procesar.");
      return paso("map_validate", { datasets });
    }
    const [poblacion, flujos] = (p.modelos || []);
    const files_ = await armar(poblacion, d.fields);
    if (!files_.length) throw new Error("Suba el reporte de cálculo antes de procesar.");
    const datos = { files: files_ };
    if (d.flows && flujos) {
      const f = (await armar(flujos, FLOW_FIELDS))[0];
      if (!f) throw new Error("Suba el calendario de pagos antes de procesar.");
      Object.assign(datos, { flowsFile: f.fileId, flowsSheet: f.sheet, flowsHeader: f.header, flowsMapping: f.mapping });
    }
    return paso("map_validate", datos);
  }

  const procesar = () => correr(async () => {
    let p = await api.cicloLeerPrueba(prueba.id);
    if (PROCESADA.includes(p.estado))
      p = await paso("return_to_data", { comment: "Reproceso solicitado desde la vista de trabajo con la evidencia vigente." });
    for (let i = 0; i < 10; i++) {
      if (CON_SUBIDA.includes(p.estado)) {
        if ((p.huecos || []).length) throw new Error(`Faltan documentos: ${p.huecos.join(" · ")}`);
        if (!p.registro.validation?.ok || p.estado === "REQUERIMIENTO_APROBADO" || !p.registro.rows?.length) {
          p = await mapear(p);
          if (!p.registro.validation?.ok)
            throw new Error(`La población tiene errores: ${erroresLegibles(p.registro.validation, 5).join(" · ")}`);
        }
        const nombres = (p.archivos || []).filter((a) => a.estado !== "rechazado").map((a) => a.nombre);
        p = await paso("validate", {
          evidenceReviewed: true,
          evidenceReview: `Procesado desde la vista de trabajo con ${nombres.length} archivo(s): ${nombres.join(", ")}.`,
          ledger: saldoMayor(mayor) || "0",
          tolerance: "0",
          acceptance: "Diferencia con el mayor pendiente de análisis al procesar.",
        });
      } else if (p.estado === "DOCUMENTACION_VALIDADA") {
        p = await paso("configure", {
          ...(d.processor ? { parametros: { ...param, tasas } } : {}),
          basis: `Parámetros y metodología de la ficha «${d.name}» (${d.source?.document || "base técnica confirmada"}), corte ${p.registro.engagement.cutoff}.`,
          buckets: d.id === "pce" ? tramosDeTexto(tramos) : [],
        });
      } else if (p.estado === "PRUEBA_CONFIGURADA") {
        p = await paso("approve_methodology");
      } else if (p.estado === "METODOLOGIA_APROBADA") {
        if (d.processor) {
          p = await paso("execute");
          continue;
        }
        const [dominio] = sitio || (await cargarSitio());
        const navegador = dominio.calculate(p.definicion, p.registro.rows, p.registro.parameters, p.registro.flows || []);
        p = await paso("execute", { navegador });
      } else return;
    }
  });

  async function bajarModelo(req) {
    try {
      descargar(`Modelo_${req}.xlsx`, await api.cicloBajarModelo(prueba.id, req), XLSX);
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  // «Editar datos» y «Encerar» abren su panel de abajo, que pide las
  // confirmaciones del sitio (alcance del cambio; nombre del cliente).
  function abrir(id) {
    const el = document.getElementById(id);
    if (el) {
      el.open = true;
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }
  function abrirEncerar() {
    const el = document.getElementById(`encerar-${prueba.id}`);
    if (el) {
      el.open = true;
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  const bloqueado = trabajando || ocupado;
  const puedeProcesar = [...CON_SUBIDA, "DOCUMENTACION_VALIDADA", "PRUEBA_CONFIGURADA", "METODOLOGIA_APROBADA", ...PROCESADA].includes(prueba.estado);
  const problemas = problemasDe(prueba);

  return (
    <div className="nf-vista">
      {/* ===== Barra de acciones ===== */}
      <div className="nf-vista-barra">
        <span className="nf-eyebrow">CONTRIBUYENTE</span>
        <span className="pc-chip on" style={{ cursor: "default", fontWeight: 700 }} title={reg.engagement?.client}>
          {reg.engagement?.ruc || reg.engagement?.client}
        </span>
        <span className="pc-chip" style={{ cursor: "default" }} title="Marco contable del encargo">{reg.engagement?.framework}</span>
        <button
          type="button"
          className="pc-chip"
          disabled={prueba.estado === "APROBADO"}
          title={prueba.estado === "APROBADO" ? "Versión aprobada: cree una nueva versión para cambiar los datos." : "Cambiar la ficha del encargo"}
          onClick={() => abrir(`ficha-${prueba.id}`)}
        >
          ✎ Editar datos
        </button>
        <span className="muted">{d.name} · {reg.engagement?.client} · corte {String(reg.engagement?.cutoff || "").split("-").reverse().join("-")}</span>
        <span style={{ flex: 1 }} />
        {ANTES_DEL_REQUERIMIENTO.includes(prueba.estado) ? (
          <button type="button" className="pc-chip accent" disabled={bloqueado || !gateTributario.ok} onClick={confirmar}
            title={gateTributario.ok ? "Confirmar la base técnica y preparar el requerimiento" : gateTributario.motivo}
            style={{ fontWeight: 700 }}>
            ✓ Confirmar base técnica
          </button>
        ) : (
          <button type="button" className="pc-chip accent" disabled={bloqueado || !puedeProcesar} onClick={procesar} style={{ fontWeight: 700 }}>
            {trabajando ? "Procesando…" : PROCESADA.includes(prueba.estado) ? "▶ Reprocesar" : "▶ Procesar"}
          </button>
        )}
        <button
          type="button"
          className="pc-chip accent"
          disabled={!reg.run || (!sitio && !d.processor)}
          onClick={async () => {
            const nombre = `${d.name.replace(/[^\w-]+/g, "_").slice(0, 60)}_v${prueba.version}.xlsx`;
            try {
              descargar(nombre, d.processor ? await api.cicloBajarLibro(prueba.id) : sitio[1].buildWorkbook(t), XLSX);
            } catch (e) {
              setError(e.message || String(e));
            }
          }}
        >
          Descargar Excel
        </button>
        {d.processor && FORMATOS_PAPEL.map(([ext, etiqueta, tipo]) => (
          <button key={ext} type="button" className="pc-chip" disabled={!reg.run} title={ext === "html" ? "Funciona sin internet y trae dentro Excel, Word, PowerPoint y PDF" : undefined}
            onClick={async () => {
              try {
                descargar(`${d.name.replace(/[^\w-]+/g, "_").slice(0, 60)}_v${prueba.version}.${ext}`, await api.cicloBajarLibro(prueba.id, ext), tipo);
              } catch (e) {
                setError(e.message || String(e));
              }
            }}>
            {etiqueta}
          </button>
        ))}
        <button
          type="button"
          className="pc-chip"
          disabled={!d.processor}
          title={d.processor ? "Recorrido de la prueba con datos de ejemplo (solo lectura)" : "Ejercicio modelo pendiente"}
          onClick={() => setModeloAbierto(true)}
        >
          Ejercicio modelo
        </button>
        <button type="button" className="pc-chip danger" onClick={abrirEncerar}>Encerar</button>
      </div>
      {modeloAbierto && <EjercicioModelo prueba={prueba} onCerrar={() => setModeloAbierto(false)} />}
      {avance && <p className="muted">{avance}</p>}
      {error && <p role="alert" className="nf-error">{error}</p>}

      <BaseTecnica prueba={prueba} taxScope={taxScope} setTaxScope={setTaxScope}
        taxConforme={taxConforme} setTaxConforme={setTaxConforme} gate={gateTributario} />

      {!ANTES_DEL_REQUERIMIENTO.includes(prueba.estado) && (
        <>
          {/* ===== Subir documentos ===== */}
          <div className="pc-scenarios nf-vista-subir">
            <span className="pc-scenarios-l" style={{ color: "var(--accent)" }}>SUBIR DOCUMENTOS</span>
            {(reg.requests || []).map((r) => (
              <ChipDocumento key={r.id} prueba={prueba} req={r} cobertura={cobertura[r.id]} onSubido={onRecargar} habilitado={CON_SUBIDA.includes(prueba.estado) && !bloqueado} processor={d.processor} onModelo={bajarModelo} />
            ))}
          </div>
          {calculo.length > 0 && (
            <p className="muted nf-vista-modelos">
              Modelo para el cliente:{" "}
              {calculo.map((r) => (
                <button key={r.id} type="button" className="link" onClick={() => bajarModelo(r.id)}>↓ {r.document}</button>
              ))}
              {" "}· si llega por partes (por ejemplo, meses o sucursales), un archivo por parte con el mismo modelo: «Procesar» los une.
            </p>
          )}
          <div className="nf-vista-progreso"><div style={{ width: `${obligatorios.length ? Math.round((completos / obligatorios.length) * 100) : 0}%` }} /></div>
          <p className="muted"><b style={{ color: "var(--accent)" }}>{completos}</b> de {obligatorios.length} documentos obligatorios completos{(prueba.huecos || []).length ? ` · falta: ${prueba.huecos.join(" · ")}` : ""}</p>
          {(prueba.archivos || []).length > 0 && (
            <details>
              <summary>Archivos subidos ({prueba.archivos.length})</summary>
              <ul>
                {prueba.archivos.map((a) => (
                  <li key={a.id}>
                    {a.requerimiento}{a.componente ? ` · ${a.componente}` : ""} · {a.nombre} ·{" "}
                    <span className={a.estado === "rechazado" ? "nf-error" : "nf-ok"}>{a.estado}</span>
                    {CON_SUBIDA.includes(prueba.estado) && (
                      <button type="button" className="link" disabled={bloqueado} onClick={() => onAccion("reject_file", { fileId: a.id })}>
                        {a.estado === "rechazado" ? " · Restituir" : " · Rechazar"}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}

          <div className="nf-rec-row">
            {puedeProcesar && (
              <label className="nf-ctx-field">
                Saldo según el mayor (opcional)
                <input value={mayor} onChange={(e) => setMayor(e.target.value)} placeholder="Ej.: 125.000,00" inputMode="decimal" />
              </label>
            )}
            {d.processor && puedeProcesar && (
              <details className="nf-ctx-field" open={!reg.run}>
                <summary>Parámetros de la prueba (editables; quedan en la cédula de parámetros)</summary>
                <div className="nf-rec-row">
                  {Object.keys(d.parametros || {}).filter((k) => typeof d.parametros[k] !== "object" || d.parametros[k] === null).map((k) => (
                    <label key={k} className="nf-ctx-field">
                      {d.etiquetas_parametros?.[k] || ETIQUETA_PARAM[k] || k}
                      <input value={param[k] ?? ""} onChange={(e) => setParam({ ...param, [k]: e.target.value })} style={{ width: 110 }} inputMode="decimal" />
                    </label>
                  ))}
                </div>
                {tramosVista && <p className="muted">Tasa fijada por el auditor por tramo (%): déjela en blanco para usar la observada. Úsela solo con evidencia de gestión de cobro.</p>}
                <div className="nf-rec-row">
                  {(tramosVista || []).map((x) => (
                    <label key={x.k} className="nf-ctx-field">
                      {x.tramo}{x.tasa === null && !(x.k in tasas) ? " · no medible" : ""}
                      <input value={tasas[x.k] ?? ""} placeholder={x.tasa === null || x.tasa === undefined ? "—" : `${(x.tasa * 100).toFixed(2).replace(".", ",")} observada`}
                        onChange={(e) => setTasas(Object.fromEntries(Object.entries({ ...tasas, [x.k]: e.target.value }).filter(([, v]) => String(v).trim() !== "")))} style={{ width: 130 }} />
                    </label>
                  ))}
                </div>
              </details>
            )}
            {d.id === "pce" && puedeProcesar && (
              <div className="nf-ctx-field">
                Tramos de mora (desde · hasta · tasa)
                {tramos.map((x, i) => (
                  <div key={i} className="nf-rec-row">
                    {["min", "max", "rate"].map((k) => (
                      <input key={k} value={x[k]} onChange={(e) => setTramos(tramos.map((y, j) => (j === i ? { ...y, [k]: e.target.value } : y)))} style={{ width: 80 }} />
                    ))}
                  </div>
                ))}
                <button type="button" className="link" onClick={() => setTramos([...tramos, { min: "", max: "", rate: "" }])}>Añadir tramo</button>
              </div>
            )}
          </div>

          {/* ===== Resultado ===== */}
          {reg.run && (
            <section className="pc-panel">
              <header className="pc-panel-h">
                <span className="pc-panel-t">Resultado</span>
                <span className="pc-panel-m">{plural(reg.run.rows.length, PROC_FICHA.includes(d.processor) ? "factura" : "partida", PROC_FICHA.includes(d.processor) ? "facturas" : "partidas")} · versión del cálculo {String(reg.run.engine || "").split(" ").pop()}</span>
              </header>
              <div className="pc-panel-b">
                <div className="pc-tiles">
                  {Object.entries(reg.run.totals).sort(([a], [b]) => (b === d.primary) - (a === d.primary)).map(([k, v]) => (
                    <div key={k} className={`pc-tile ${k === d.primary ? "on" : "done"}`} style={{ cursor: "default" }}>
                      <div className="pc-tile-txt">
                        <span className="pc-tile-t">{esNumero(v) ? FORMATO.n(v) : v}</span>
                        <span className="pc-tile-d">{reg.run.labels?.[k] || d.rules.find((r) => r.key === k)?.label || d.fields.find((f) => f.key === k)?.label || k}</span>
                      </div>
                    </div>
                  ))}
                </div>
                {problemas.length > 0 && (
                  <>
                    <p className="nf-eyebrow">PROBLEMAS ENCONTRADOS</p>
                    <ul>{problemas.map((x) => <li key={x}>{x}</li>)}</ul>
                  </>
                )}
                {reg.run.exceptions.length > 0 && (
                  <details open>
                    <summary>{d.processor ? "Problemas del cálculo" : "Excepciones por partida"} ({reg.run.exceptions.length})</summary>
                    <ul>{reg.run.exceptions.map((e, i) => <li key={i}>{e.row ? `Fila ${e.row} · ${e.id} · ` : ""}{e.message}{Number(e.amount) ? ` · Importe: ${FORMATO.n(e.amount)}` : ""}</li>)}</ul>
                  </details>
                )}
              </div>
            </section>
          )}

          {/* ===== Cédulas ===== */}
          {armado?.error && <p className="nf-error">{armado.error}</p>}
          {armado?.etiquetas && (
            <>
              <p className="muted">Pulse una cédula para ver su estado y qué documentos usa:</p>
              <div className="pc-tiles">
                {armado.etiquetas.map((label, i) => (
                  <button key={label} type="button" className={`pc-tile ${reg.run ? "done" : ""}${cedula === i ? " on" : ""}`} onClick={() => setCedula(i)}>
                    <span className={`pc-tile-n ${reg.run ? "done" : "dim"}`}>{i + 1}</span>
                    <div className="pc-tile-txt">
                      <span className="pc-tile-t">{label}</span>
                      <span className="pc-tile-d">{DE_CONTEXTO[armado.nombres[i]] || (d.processor ? fuenteCedula(armado.nombres[i], calculo.length) : calculo.map((r) => r.document).join(" · "))}</span>
                    </div>
                    <span className="pc-tile-st">{reg.run ? "GENERADA" : "PENDIENTE"}</span>
                  </button>
                ))}
              </div>
              <PanelCedula prueba={prueba} indice={cedula} etiqueta={armado.etiquetas[cedula]} nombre={armado.nombres[cedula]} hojas={armado.hojas} notas={notas} calculo={calculo} />
            </>
          )}
        </>
      )}
    </div>
  );
}
