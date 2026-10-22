import { useEffect, useRef, useState } from "react";
import { PAGINAS } from "../paginas.js";
import {
  sriPermiso,
  sriDescargar,
  sriEstado,
  sriEnviarCaptcha,
  sriCancelar,
  sriDescargarZip,
  sriConsolidar,
  sriReporteFechas,
  sriHistorial,
  sriReconstruir,
  sriCruceRetenciones,
  sriFacturaRetencion,
  sriValorNeto,
  sriDeclaracionesDescargar,
  sriDescargarArchivo,
  sriVivoUrl,
} from "../../../api.js";
import { ESTADOS_EMITIDOS, tipoValido, tiposDe } from "./sriOpciones.js";
import { SONDEO_MS, debeRenovar, formatosValidos, sesionDesdePermiso } from "./sriSesion.js";
import { avisoXmlEmitidos, validarEstablecimiento, validarPuntoEmision } from "./sriValidacion.js";
import { COLUMNAS_HISTORIAL, filtrarHistorial, normalizarFila, opcionesDe } from "./sriHistorial.js";
import "./CumplimientoSRI.css";

const META = PAGINAS.find((p) => p.id === "sri");

// Devuelve un token vigente para el trabajo en curso, renovando el permiso si
// está por vencer (el permiso dura 5 min; una descarga puede durar más).
async function tokenVigente(ctx) {
  if (debeRenovar(ctx.current.vence)) {
    const p = await sriPermiso(ctx.current.encargo);
    Object.assign(ctx.current, sesionDesdePermiso(p));
  }
  return ctx.current.token;
}

// Pide detener el trabajo en curso; el estado "cancelado" llega por el sondeo.
async function detenerTrabajo(ctx, setError) {
  try { await sriCancelar(ctx.current.url, await tokenVigente(ctx), ctx.current.id); }
  catch (e) { setError(e?.message || "No se pudo detener el trabajo."); }
}

function BotonDetener({ ctx, trabajando, cancelando, setError }) {
  if (!trabajando) return null;
  return (
    <button type="button" className="ma-boton" onClick={() => detenerTrabajo(ctx, setError)} disabled={cancelando}>
      {cancelando ? "Deteniendo…" : "⏹ Detener"}
    </button>
  );
}

// Subpáginas = las pestañas del robot del SRI (aplicacion.py de copia-robot-audit).
const SUBS = [
  { id: "descarga", titulo: "Descarga de comprobantes" },
  { id: "reportefechas", titulo: "Reporte por fechas" },
  { id: "reportes", titulo: "Historial" },
  { id: "consolidacion", titulo: "Consolidación de documentos" },
  { id: "reconstruccion", titulo: "Reconstruir XML" },
  { id: "cruce", titulo: "Retención ↔ Factura" },
  { id: "facturaret", titulo: "Factura ↔ Retención" },
  { id: "valorneto", titulo: "Valor neto (NC)" },
  { id: "declaraciones", titulo: "Declaraciones" },
  { id: "ayuda", titulo: "Ayuda" },
];

// Obligaciones cuya navegación del portal está mapeada (consulta de declaraciones).
const OBLIGACIONES_DECL = [
  { id: "iva_104", nombre: "IVA (F-104)", mensual: true },
  { id: "retenciones_103", nombre: "Retenciones en la fuente (F-103)", mensual: true },
  { id: "renta_sociedades_101", nombre: "Renta Sociedades (F-101)", mensual: false },
];
const DOCS_DECL = ["Declaración completa", "Declaración perfilada", "Comprobante de declaración"];

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const ANIO_ACTUAL = new Date().getFullYear();
const ANIOS = Array.from({ length: 10 }, (_, i) => ANIO_ACTUAL - i);
// Tipos por origen y estados de Emitidos: ver sriOpciones.js (paridad con la
// app de escritorio; el portal no tiene una opción para todos los tipos).
const MODOS_FECHA = ["Mes", "Rango de meses", "Año completo"];
// Vista en vivo del robot (solo lectura). Va por el motor de la firma como
// MJPEG (endpoint /motor/sri/vivo), publicado por Tailscale Funnel: se ve por
// el mismo canal que el resto del motor, SIN exigir que el auditor esté en la
// red Tailscale. El permiso firmado viaja en el query string porque un <img>
// no puede mandar cabecera Authorization. Reconecta con token fresco al fallar.
function VistaEnVivo({ encargo = "SRI vista en vivo" }) {
  const [src, setSrc] = useState("");
  const [error, setError] = useState("");
  const ultimo = useRef(0);
  const vivo = useRef(true);

  async function conectar() {
    try {
      const p = await sriPermiso(encargo);
      if (!vivo.current) return;
      ultimo.current = Date.now();
      // El sufijo &t= fuerza al navegador a reabrir el stream con el token nuevo.
      setSrc(`${sriVivoUrl(p.url, p.token)}&t=${ultimo.current}`);
      setError("");
    } catch {
      if (vivo.current) setError("No se pudo autorizar la vista en vivo. Reintenta en unos segundos.");
    }
  }

  useEffect(() => {
    vivo.current = true;
    conectar();
    return () => { vivo.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [encargo]);

  // Un stream MJPEG queda autorizado al conectarse; solo hay que reconectar si
  // la conexión se cae o el token venció. Se limita a un reintento cada 4 s.
  function alFallar() {
    if (Date.now() - ultimo.current < 4000) return;
    conectar();
  }

  return (
    <div className="ma-sri-vivo">
      <div className="ma-sri-vivo-cab">
        <span>🔴 Robot en vivo — solo lectura</span>
        <span className="ma-sri-vivo-nota">Se transmite por el motor de la firma. Verás el navegador del robot cuando esté descargando del SRI.</span>
      </div>
      {error ? (
        <div className="ma-sri-vivo-aviso">{error}</div>
      ) : src ? (
        <img title="Robot SRI en vivo" alt="Robot SRI en vivo" src={src} className="ma-sri-vivo-frame" onError={alFallar} />
      ) : (
        <div className="ma-sri-vivo-aviso">Conectando con la vista en vivo…</div>
      )}
    </div>
  );
}

// Resumen legible del resultado del robot (en vez del JSON crudo).
function ResumenResultado({ r, titulo }) {
  if (!r || typeof r !== "object") {
    return <div className="ma-sri-resumen"><div className="ma-sri-resumen-titulo">{titulo}</div></div>;
  }
  const n = (k) => (typeof r[k] === "number" ? r[k] : null);
  const total = n("n_registros") ?? n("registros_esperados") ?? n("total");
  const pdfOk = n("descargados_pdf_verificados") ?? n("n_pdf");
  const pdfEsp = n("esperados_pdf");
  const xmlOk = n("descargados_xml_verificados") ?? n("n_xml");
  const xmlEsp = n("esperados_xml");
  const ctx = [r.tipo_visible, r.estado_autorizacion, r.fecha_filtro].filter(Boolean).join(" · ");
  const conteos = [];
  if (pdfEsp != null) conteos.push(`PDF ${pdfOk ?? 0}/${pdfEsp}`);
  if (xmlEsp != null) conteos.push(`XML ${xmlOk ?? 0}/${xmlEsp}`);
  return (
    <div className="ma-sri-resumen">
      <div className="ma-sri-resumen-titulo">{titulo}</div>
      {ctx && <div>{ctx}</div>}
      {total != null && <div><strong>{total}</strong> comprobantes</div>}
      {conteos.length > 0 && <div className="ma-sri-resumen-conteos">{conteos.join("  ·  ")}</div>}
      {r.mensaje && <div className="ma-sri-resumen-msg">{r.mensaje}</div>}
      <details className="ma-sri-detalle"><summary>Ver detalle técnico</summary><pre>{JSON.stringify(r, null, 2)}</pre></details>
    </div>
  );
}

// Resumen de un reporte offline (reconstrucción / cruces): conteos + por mes.
const _ETIQUETAS_OFFLINE = {
  generados: "XML generados", total_filas: "Filas leídas", repetidos: "Repetidas",
  fallidos: "Sin generar", invalidos: "No validan XSD",
  total_retenciones: "Retenciones", total_documentos: "Documentos sustento",
  con_factura: "Con factura", sin_factura: "Sin factura",
  total_facturas: "Facturas", con_retencion: "Con retención", sin_retencion: "Sin retención",
  total_nc: "Notas de crédito", encontradas_local: "Facturas halladas", no_encontradas: "No encontradas",
};
function ResumenOffline({ r, titulo, onDescargar, bajando, textoDescarga }) {
  if (!r || typeof r !== "object") return null;
  const chips = Object.entries(_ETIQUETAS_OFFLINE)
    .filter(([k]) => typeof r[k] === "number")
    .map(([k, et]) => ({ et, v: r[k] }));
  const porMes = r.por_mes && typeof r.por_mes === "object" ? Object.entries(r.por_mes).sort() : [];
  return (
    <div className="ma-sri-resumen">
      <div className="ma-sri-resumen-titulo">{titulo}</div>
      {r.message && <div className="ma-sri-resumen-msg">{r.message}</div>}
      {chips.length > 0 && (
        <div className="ma-sri-resumen-conteos">
          {chips.map((c) => <span key={c.et}>{c.et}: <strong>{c.v}</strong></span>)}
        </div>
      )}
      {porMes.length > 0 && (
        <div className="ma-sri-resumen-conteos">
          {porMes.map(([m, n]) => <span key={m}>{m}: <strong>{n}</strong></span>)}
        </div>
      )}
      {onDescargar && (
        <div className="ma-sri-descarga-acciones">
          <button type="button" className="ma-boton" onClick={onDescargar} disabled={bajando}>
            {bajando ? "Preparando…" : (textoDescarga || "Descargar reporte")}
          </button>
        </div>
      )}
      <details className="ma-sri-detalle"><summary>Ver detalle técnico</summary><pre>{JSON.stringify(r, null, 2)}</pre></details>
    </div>
  );
}

// ---------- Subpágina 1: Descarga (login + filtros + captcha relay) ----------
function SubDescarga() {
  const [form, setForm] = useState({
    ruc: "", clave: "", origen: "Recibidos", tipo: tiposDe("Recibidos")[0],
    modo_fecha: "Mes", anio: ANIO_ACTUAL, mes: 1, mes_fin: 12, dia: 0,
    estado_emitidos: ESTADOS_EMITIDOS[0], establecimiento: "Todos", punto_emision: "",
    formatoXML: true, formatoPDF: true, modo_rapido: false,
  });
  const [aviso, setAviso] = useState("");
  const [fase, setFase] = useState("idle"); // idle|procesando|captcha|listo|error
  const [progreso, setProgreso] = useState([]);
  const [captchaImg, setCaptchaImg] = useState(null);
  const [captchaCodigo, setCaptchaCodigo] = useState("");
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState("");
  const [bajando, setBajando] = useState(false);
  const [segundos, setSegundos] = useState(0);
  const [verVivo, setVerVivo] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const ctx = useRef({ url: "", token: "", id: "", vivo: false });
  useEffect(() => () => { ctx.current.vivo = false; }, []);
  useEffect(() => {
    if (!(fase === "procesando" || fase === "captcha")) return undefined;
    const t = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [fase]);

  const set = (k) => (e) => {
    const v = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    // Las listas de tipo cambian con el origen: si el tipo actual no existe en
    // el nuevo origen, se toma el primero (igual que la app de escritorio).
    setForm((f) => (k === "origen" ? { ...f, origen: v, tipo: tipoValido(v, f.tipo) } : { ...f, [k]: v }));
  };
  const trabajando = fase === "procesando" || fase === "captcha";

  async function poll() {
    if (!ctx.current.vivo) return;
    try {
      const est = await sriEstado(ctx.current.url, await tokenVigente(ctx), ctx.current.id);
      setProgreso(est.progreso || []);
      if (est.estado === "captcha") { setFase("captcha"); setCaptchaImg(est.captcha_img_b64 || null); }
      else if (est.estado === "listo") { ctx.current.vivo = false; setResultado(est.resultado || {}); setFase("listo"); return; }
      else if (est.estado === "error" || est.estado === "cancelado") { ctx.current.vivo = false; setError(est.error || "La descarga falló."); setFase("error"); return; }
      else { setFase("procesando"); setCaptchaImg(null); }
      setCancelando(Boolean(est.cancelando));
    } catch { /* red transitoria: seguimos */ }
    setTimeout(poll, SONDEO_MS);
  }

  async function lanzar() {
    setError(""); setResultado(null); setProgreso([]); setCaptchaImg(null); setSegundos(0); setCancelando(false);
    if (!/^\d{13}$/.test(form.ruc.trim())) { setError("El RUC debe tener 13 dígitos."); return; }
    if (!form.clave) { setError("Falta la clave del SRI del cliente."); return; }
    setAviso("");
    let formatos = form.modo_rapido ? [] : [form.formatoXML && "XML", form.formatoPDF && "PDF"].filter(Boolean);
    if (!formatosValidos(formatos, form.modo_rapido)) { setError("Selecciona al menos un formato (XML o PDF) o activa el modo rápido."); return; }
    const esEmitidos = form.origen === "Emitidos";
    let establecimiento = null;
    let puntoEmision = null;
    if (esEmitidos) {
      const est = validarEstablecimiento(form.establecimiento);
      if (!est.ok) { setError(est.error); return; }
      const pto = validarPuntoEmision(form.punto_emision, est.valor);
      if (!pto.ok) { setError(pto.error); return; }
      establecimiento = est.valor; puntoEmision = pto.valor || null;
      // Como en la app de escritorio: el SRI no entrega el XML de Emitidos
      // pasados ~30 días; con PDF marcado se sigue solo con PDF, si no se detiene.
      const avisoXml = avisoXmlEmitidos({
        origen: form.origen, estado_emitidos: form.estado_emitidos, formatos, modo_rapido: form.modo_rapido,
        periodo: { modo_fecha: form.modo_fecha, anio: form.anio, mes: form.mes, mes_fin: form.mes_fin, dia: form.dia },
      });
      if (avisoXml) {
        setAviso(avisoXml.mensaje);
        if (!avisoXml.continuar) return;
        formatos = avisoXml.formatos;
      }
    }
    const encargo = `SRI ${form.ruc.trim()}`;
    setFase("procesando");
    try {
      const permiso = await sriPermiso(encargo);
      const { id } = await sriDescargar(permiso.url, permiso.token, {
        ruc: form.ruc.trim(), clave: form.clave, origen: form.origen, tipo: form.tipo,
        modo_fecha: form.modo_fecha, anio: Number(form.anio), mes: Number(form.mes),
        mes_fin: Number(form.mes_fin), dia: Number(form.dia),
        estado_emitidos: esEmitidos ? form.estado_emitidos : null,
        establecimiento, punto_emision: puntoEmision,
        formatos, modo_rapido: form.modo_rapido,
      });
      ctx.current = { ...sesionDesdePermiso(permiso), encargo, id, vivo: true };
      setForm((f) => ({ ...f, clave: "" }));
      poll();
    } catch (e) { setError(e?.message || "No se pudo iniciar la descarga."); setFase("error"); }
  }

  async function enviarCaptcha() {
    if (!captchaCodigo.trim()) return;
    try {
      await sriEnviarCaptcha(ctx.current.url, await tokenVigente(ctx), ctx.current.id, captchaCodigo.trim());
      setCaptchaCodigo(""); setCaptchaImg(null); setFase("procesando");
    } catch (e) { setError(e?.message || "No se pudo enviar el captcha."); }
  }

  async function bajarZip() {
    setBajando(true); setError("");
    try { await sriDescargarZip(ctx.current.url, await tokenVigente(ctx), ctx.current.id); }
    catch (e) { setError(e?.message || "No se pudo descargar el ZIP."); }
    finally { setBajando(false); }
  }

  return (
    <section className="ma-tarjeta ma-sri-descarga">
      <div className="ma-sri-descarga-cab">
        <h3>Descarga de comprobantes</h3>
        <span>El robot inicia sesión en el portal del SRI y descarga los comprobantes del período.</span>
      </div>
      <div className="ma-sri-form">
        <label>RUC del cliente
          <input value={form.ruc} onChange={set("ruc")} inputMode="numeric" maxLength={13} placeholder="1791859596001" disabled={trabajando} />
        </label>
        <label>Clave del SRI
          <input type="password" value={form.clave} onChange={set("clave")} placeholder="•••••••" autoComplete="off" disabled={trabajando} />
        </label>
        <label>Origen
          <select value={form.origen} onChange={set("origen")} disabled={trabajando}><option>Recibidos</option><option>Emitidos</option></select>
        </label>
        <label>Tipo de comprobante
          <select value={form.tipo} onChange={set("tipo")} disabled={trabajando}>{tiposDe(form.origen).map((t) => <option key={t}>{t}</option>)}</select>
        </label>
        <label>Modo de fecha
          <select value={form.modo_fecha} onChange={set("modo_fecha")} disabled={trabajando}>{MODOS_FECHA.map((m) => <option key={m}>{m}</option>)}</select>
        </label>
        <label>Año
          <select value={form.anio} onChange={set("anio")} disabled={trabajando}>{ANIOS.map((a) => <option key={a} value={a}>{a}</option>)}</select>
        </label>
        {form.modo_fecha !== "Año completo" && (
          <label>{form.modo_fecha === "Rango de meses" ? "Mes inicio" : "Mes"}
            <select value={form.mes} onChange={set("mes")} disabled={trabajando}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select>
          </label>
        )}
        {form.modo_fecha === "Rango de meses" && (
          <label>Mes fin
            <select value={form.mes_fin} onChange={set("mes_fin")} disabled={trabajando}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select>
          </label>
        )}
        {form.modo_fecha === "Mes" && (
          <label>Día (0 = todo el mes)
            <input type="number" min={0} max={31} value={form.dia} onChange={set("dia")} disabled={trabajando} />
          </label>
        )}
        {form.origen === "Emitidos" && (
          <label>Estado de autorización
            <select value={form.estado_emitidos} onChange={set("estado_emitidos")} disabled={trabajando}>{ESTADOS_EMITIDOS.map((e) => <option key={e}>{e}</option>)}</select>
          </label>
        )}
        {form.origen === "Emitidos" && (
          <label>Establecimiento
            <input value={form.establecimiento} onChange={set("establecimiento")} maxLength={5} placeholder="Todos o 001" title="Escribe 'Todos' o un número de 3 dígitos (ej. 001)." disabled={trabajando} />
          </label>
        )}
        {form.origen === "Emitidos" && (
          <label>Punto de emisión (opcional)
            <input value={form.punto_emision} onChange={(e) => setForm((f) => ({ ...f, punto_emision: e.target.value.replace(/\D/g, "").slice(0, 3) }))} inputMode="numeric" maxLength={3} placeholder="001" title="Hasta 3 dígitos numéricos (ej. 001). Obligatorio si indicas un establecimiento." disabled={trabajando} />
          </label>
        )}
        <label className="ma-sri-check">Formatos
          <span className="ma-sri-check-fila">
            <label><input type="checkbox" checked={form.formatoXML} onChange={set("formatoXML")} disabled={trabajando || form.modo_rapido} /> XML</label>
            <label><input type="checkbox" checked={form.formatoPDF} onChange={set("formatoPDF")} disabled={trabajando || form.modo_rapido} /> PDF</label>
          </span>
        </label>
        <label className="ma-sri-check">Modo rápido
          <span className="ma-sri-check-fila"><label><input type="checkbox" checked={form.modo_rapido} onChange={set("modo_rapido")} disabled={trabajando} /> Solo reporte, sin archivos</label></span>
        </label>
      </div>
      <div className="ma-sri-descarga-acciones">
        <button type="button" className="ma-sri-boton-ejecutar" onClick={lanzar} disabled={trabajando}>
          {trabajando ? "Descargando…" : "Descargar"}
        </button>
        <BotonDetener ctx={ctx} trabajando={trabajando} cancelando={cancelando} setError={setError} />
        {fase === "listo" && (
          <button type="button" className="ma-boton" onClick={bajarZip} disabled={bajando}>
            {bajando ? "Preparando ZIP…" : "Descargar archivos (ZIP)"}
          </button>
        )}
        <button type="button" className="ma-boton" onClick={() => setVerVivo((v) => !v)}>
          {verVivo ? "Ocultar vista en vivo" : "🔴 Ver el robot en vivo"}
        </button>
        <span className="ma-sri-descarga-clave-nota">La clave va directo al motor de la firma; no se guarda ni pasa por el servidor web.</span>
      </div>

      {verVivo && <VistaEnVivo encargo="SRI vista en vivo (descarga)" />}

      {captchaImg && (
        <div className="ma-sri-captcha" role="dialog" aria-label="Resolver captcha">
          <p><strong>El SRI pide un captcha.</strong> Escribe lo que ves:</p>
          <img alt="captcha del SRI" src={`data:image/png;base64,${captchaImg}`} className="ma-sri-captcha-img" />
          <div className="ma-sri-captcha-fila">
            <input value={captchaCodigo} onChange={(e) => setCaptchaCodigo(e.target.value)} placeholder="Código" autoFocus onKeyDown={(e) => e.key === "Enter" && enviarCaptcha()} />
            <button type="button" className="ma-sri-boton-ejecutar" onClick={enviarCaptcha}>Enviar</button>
          </div>
        </div>
      )}
      {(fase === "procesando" || fase === "captcha") && (
        <div className="ma-sri-trabajando">
          <span className="ma-sri-spinner" aria-hidden="true" />
          <span>
            El robot está trabajando en el servidor… <strong>{segundos}s</strong>
            {fase === "captcha" ? " · esperando que resuelvas el captcha" : " · entrando al SRI y navegando (puede tardar 1-3 min)"}
          </span>
        </div>
      )}
      {aviso && <div className="ma-sri-resultado ma-sri-resultado-aviso">{aviso}</div>}
      {progreso.length > 0 && <ul className="ma-sri-progreso">{progreso.slice(-8).map((m, i) => <li key={i}>{m}</li>)}</ul>}
      {fase === "listo" && <div className="ma-sri-resultado ma-sri-resultado-ok"><ResumenResultado r={resultado} titulo="✅ Descarga completada" /></div>}
      {error && <div className="ma-sri-resultado ma-sri-resultado-error">{error}</div>}
    </section>
  );
}

// ---------- Subpágina: Reporte por fechas (offline, de lo ya descargado) ----------
const TIPOS_REPORTE = ["Facturas", "Retenciones", "Notas de crédito", "Notas de débito", "Liquidación de compra", "Guía de remisión"];
const MODOS_REPORTE = ["Día específico", "Mes completo", "Rango de fechas", "Rango de meses", "Año completo"];
const _iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const _hoyIso = () => _iso(new Date());

// Rango [inicio, fin] en ISO según el modo (misma lógica que la app de escritorio).
function rangoReporteFechas(f) {
  const a = Number(f.anio);
  const fin = (m) => new Date(a, m, 0).getDate();
  if (f.modo === "Día específico") return [f.fecha, f.fecha];
  if (f.modo === "Mes completo") { const m = Number(f.mes); return [`${a}-${String(m).padStart(2, "0")}-01`, `${a}-${String(m).padStart(2, "0")}-${fin(m)}`]; }
  if (f.modo === "Rango de fechas") return [f.fecha_inicio, f.fecha_fin];
  if (f.modo === "Rango de meses") { const mi = Number(f.mes_inicio); const mf = Number(f.mes_fin); return [`${a}-${String(mi).padStart(2, "0")}-01`, `${a}-${String(mf).padStart(2, "0")}-${fin(mf)}`]; }
  return [`${a}-01-01`, `${a}-12-31`];
}

function SubReporteFechas() {
  const hoy = new Date();
  const [form, setForm] = useState({
    ruc: "", origen: "Recibidos", tipo: "Facturas", estado_emitidos: ESTADOS_EMITIDOS[0], modo: "Mes completo",
    anio: ANIO_ACTUAL, mes: hoy.getMonth() + 1, mes_inicio: 1, mes_fin: hoy.getMonth() + 1,
    fecha: _hoyIso(), fecha_inicio: _iso(new Date(hoy.getFullYear(), hoy.getMonth(), 1)), fecha_fin: _hoyIso(),
  });
  const [estado, setEstado] = useState("idle");
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState("");
  const [bajando, setBajando] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function generar() {
    setError(""); setResultado(null);
    if (!/^\d{13}$/.test(form.ruc.trim())) { setError("El RUC debe tener 13 dígitos."); return; }
    const [ini, fin] = rangoReporteFechas(form);
    if (!ini || !fin) { setError("Debes definir un rango de fechas válido."); return; }
    if (ini > fin) { setError("La fecha inicio no puede ser mayor que la fecha fin."); return; }
    setEstado("procesando");
    try {
      const p = await sriPermiso(`SRI reporte fechas ${form.ruc.trim()}`);
      const r = await sriReporteFechas(p.url, p.token, {
        ruc: form.ruc.trim(), origen: form.origen, tipo: form.tipo,
        estado_emitidos: form.origen === "Emitidos" ? form.estado_emitidos : null,
        fecha_inicio: ini, fecha_fin: fin,
      });
      setResultado(r); setEstado(r.ok === false ? "error" : "listo");
      if (r.ok === false) setError(r.message || "No se pudo generar el reporte.");
    } catch (e) { setError(e?.message || "No se pudo generar el reporte."); setEstado("error"); }
  }

  async function bajar() {
    if (!resultado?.excel_path) return;
    setBajando(true); setError("");
    try { const p = await sriPermiso(`SRI reporte fechas ${form.ruc.trim()}`); await sriDescargarArchivo(p.url, p.token, resultado.excel_path); }
    catch (e) { setError(e?.message || "No se pudo descargar."); }
    finally { setBajando(false); }
  }

  return (
    <section className="ma-tarjeta ma-sri-descarga">
      <div className="ma-sri-descarga-cab">
        <h3>Reporte por fechas</h3>
        <span>Excel con los comprobantes ya descargados de un RUC entre dos fechas (Excel y PDF del mismo formato que el reporte de descarga). No entra al SRI.</span>
      </div>
      <div className="ma-sri-form">
        <label>RUC del contribuyente<input value={form.ruc} onChange={set("ruc")} inputMode="numeric" maxLength={13} placeholder="1791859596001" /></label>
        <label>Origen<select value={form.origen} onChange={set("origen")}><option>Recibidos</option><option>Emitidos</option></select></label>
        <label>Tipo de comprobante<select value={form.tipo} onChange={set("tipo")}>{TIPOS_REPORTE.map((t) => <option key={t}>{t}</option>)}</select></label>
        {form.origen === "Emitidos" && (
          <label>Estado de autorización<select value={form.estado_emitidos} onChange={set("estado_emitidos")}>{ESTADOS_EMITIDOS.map((e) => <option key={e}>{e}</option>)}</select></label>
        )}
        <label>Modo de fecha<select value={form.modo} onChange={set("modo")}>{MODOS_REPORTE.map((m) => <option key={m}>{m}</option>)}</select></label>
        {form.modo === "Día específico" && <label>Fecha<input type="date" value={form.fecha} onChange={set("fecha")} /></label>}
        {(form.modo === "Mes completo" || form.modo === "Rango de meses" || form.modo === "Año completo") && (
          <label>Año<select value={form.anio} onChange={set("anio")}>{ANIOS.map((a) => <option key={a} value={a}>{a}</option>)}</select></label>
        )}
        {form.modo === "Mes completo" && <label>Mes<select value={form.mes} onChange={set("mes")}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>}
        {form.modo === "Rango de fechas" && <label>Fecha inicio<input type="date" value={form.fecha_inicio} onChange={set("fecha_inicio")} /></label>}
        {form.modo === "Rango de fechas" && <label>Fecha fin<input type="date" value={form.fecha_fin} onChange={set("fecha_fin")} /></label>}
        {form.modo === "Rango de meses" && <label>Mes inicio<select value={form.mes_inicio} onChange={set("mes_inicio")}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>}
        {form.modo === "Rango de meses" && <label>Mes fin<select value={form.mes_fin} onChange={set("mes_fin")}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>}
      </div>
      <div className="ma-sri-descarga-acciones">
        <button type="button" className="ma-sri-boton-ejecutar" onClick={generar} disabled={estado === "procesando"}>{estado === "procesando" ? "Generando…" : "Generar reporte por fechas"}</button>
      </div>
      {estado === "listo" && (
        <div className="ma-sri-resultado ma-sri-resultado-ok">
          <ResumenOffline r={{ ...resultado, total_filas: resultado?.rows }} titulo="✅ Reporte generado" onDescargar={resultado?.excel_path ? bajar : null} bajando={bajando} textoDescarga="Descargar reporte por fechas" />
          {Array.isArray(resultado?.errors) && resultado.errors.length > 0 && <p className="ma-sri-tabla-nota">PDF con advertencias omitidos: {resultado.errors.length}</p>}
        </div>
      )}
      {error && <div className="ma-sri-resultado ma-sri-resultado-error">{error}</div>}
    </section>
  );
}

// ---------- Subpágina 2: Reportes e historial ----------
function SubReportes() {
  const [historial, setHistorial] = useState(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [filtros, setFiltros] = useState({ busqueda: "", ruc: "Todos", origen: "Todos", tipo: "Todos", anio: "Todos" });
  const setF = (k) => (e) => setFiltros((f) => ({ ...f, [k]: e.target.value }));

  async function cargar() {
    setCargando(true); setError("");
    try {
      const permiso = await sriPermiso("SRI historial");
      const r = await sriHistorial(permiso.url, permiso.token);
      setHistorial((Array.isArray(r.historial) ? r.historial : []).map(normalizarFila));
    } catch (e) { setError(e?.message || "No se pudo cargar el historial."); }
    finally { setCargando(false); }
  }
  useEffect(() => { cargar(); }, []);

  const todas = Array.isArray(historial) ? historial : [];
  const filas = filtrarHistorial(todas, filtros);
  return (
    <section className="ma-tarjeta ma-sri-tabla-bloque">
      <div className="ma-sri-descarga-cab">
        <h3>Historial</h3>
        <span>Descargas registradas en el servidor, más recientes primero. Los archivos de cada descarga se bajan desde la pestaña «Descarga» (botón ZIP) al terminar.</span>
      </div>
      <div className="ma-sri-descarga-acciones">
        <button type="button" className="ma-boton" onClick={cargar} disabled={cargando}>{cargando ? "Cargando…" : "Actualizar historial"}</button>
      </div>
      {todas.length > 0 && (
        <div className="ma-sri-form">
          <label>Búsqueda<input value={filtros.busqueda} onChange={setF("busqueda")} placeholder="RUC, tipo, estado…" /></label>
          <label>RUC<select value={filtros.ruc} onChange={setF("ruc")}>{opcionesDe(todas, "ruc").map((o) => <option key={o}>{o}</option>)}</select></label>
          <label>Origen<select value={filtros.origen} onChange={setF("origen")}>{opcionesDe(todas, "origen").map((o) => <option key={o}>{o}</option>)}</select></label>
          <label>Tipo<select value={filtros.tipo} onChange={setF("tipo")}>{opcionesDe(todas, "tipo").map((o) => <option key={o}>{o}</option>)}</select></label>
          <label>Año<select value={filtros.anio} onChange={setF("anio")}>{opcionesDe(todas, "anio").map((o) => <option key={o}>{o}</option>)}</select></label>
        </div>
      )}
      {error && <div className="ma-sri-resultado ma-sri-resultado-error">{error}</div>}
      {todas.length === 0 && !cargando && !error && <p className="ma-sri-tabla-nota">Sin descargas registradas todavía.</p>}
      {todas.length > 0 && filas.length === 0 && <p className="ma-sri-tabla-nota">Ninguna descarga coincide con los filtros.</p>}
      {filas.length > 0 && (
        <div className="ma-tabla-wrap">
          <table className="ma-tabla ma-sri-tabla">
            <thead><tr>{COLUMNAS_HISTORIAL.map(([k, et]) => <th key={k}>{et}</th>)}</tr></thead>
            <tbody>
              {filas.map((h, i) => (
                <tr key={`${h.timestamp}-${i}`}>
                  {COLUMNAS_HISTORIAL.map(([k]) => <td key={k} className={k === "ruc" ? "ma-sri-tabla-form" : undefined}>{h[k] || "—"}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="ma-sri-tabla-nota">{filas.length} de {todas.length} descargas.</p>
        </div>
      )}
    </section>
  );
}

// ---------- Subpágina 3: Consolidación de documentos ----------
function SubConsolidacion() {
  const [form, setForm] = useState({ ruc: "", origen: "Recibidos", tipo: tiposDe("Recibidos")[0], estado_emitidos: ESTADOS_EMITIDOS[0], modo_fecha: "Rango de meses", anio: ANIO_ACTUAL, mes_inicio: 1, mes_fin: 12, dia: 0, incluir_xml: true, incluir_pdf: true });
  const [estado, setEstado] = useState("idle");
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState("");
  const [bajando, setBajando] = useState("");
  const set = (k) => (e) => {
    const v = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((f) => (k === "origen" ? { ...f, origen: v, tipo: tipoValido(v, f.tipo) } : { ...f, [k]: v }));
  };

  async function consolidar() {
    setError(""); setResultado(null);
    if (!/^\d{13}$/.test(form.ruc.trim())) { setError("El RUC debe tener 13 dígitos."); return; }
    setEstado("procesando");
    try {
      const permiso = await sriPermiso(`SRI consolidar ${form.ruc.trim()}`);
      // Modo "Mes": el servicio toma mes_inicio como el mes y dia (0 = todo el mes).
      const esMes = form.modo_fecha === "Mes";
      const r = await sriConsolidar(permiso.url, permiso.token, {
        carpeta_base: `descargas/${form.ruc.trim()}`, origen: form.origen, ruc: form.ruc.trim(),
        tipo: form.tipo, estado: form.origen === "Emitidos" ? form.estado_emitidos : null,
        modo_fecha: form.modo_fecha, anio: Number(form.anio),
        mes_inicio: Number(form.mes_inicio), mes_fin: esMes ? Number(form.mes_inicio) : Number(form.mes_fin),
        dia: esMes ? Number(form.dia) : 0,
        incluir_xml: form.incluir_xml, incluir_pdf: form.incluir_pdf,
      });
      setResultado(r); setEstado("listo");
    } catch (e) { setError(e?.message || "No se pudo consolidar."); setEstado("error"); }
  }

  async function bajar(ruta, etiqueta) {
    if (!ruta) return;
    setBajando(etiqueta); setError("");
    try { const p = await sriPermiso(`SRI consolidar ${form.ruc.trim()}`); await sriDescargarArchivo(p.url, p.token, ruta); }
    catch (e) { setError(e?.message || "No se pudo descargar."); }
    finally { setBajando(""); }
  }

  return (
    <section className="ma-tarjeta ma-sri-descarga">
      <div className="ma-sri-descarga-cab">
        <h3>Consolidación de documentos</h3>
        <span>Une los reportes y documentos ya descargados de un RUC por período (sin volver a entrar al SRI).</span>
      </div>
      <div className="ma-sri-form">
        <label>RUC<input value={form.ruc} onChange={set("ruc")} inputMode="numeric" maxLength={13} placeholder="1791859596001" /></label>
        <label>Origen<select value={form.origen} onChange={set("origen")}><option>Recibidos</option><option>Emitidos</option></select></label>
        <label>Tipo<select value={form.tipo} onChange={set("tipo")}>{tiposDe(form.origen).map((t) => <option key={t}>{t}</option>)}</select></label>
        {form.origen === "Emitidos" && (
          <label>Estado de autorización<select value={form.estado_emitidos} onChange={set("estado_emitidos")}>{ESTADOS_EMITIDOS.map((e) => <option key={e}>{e}</option>)}</select></label>
        )}
        <label>Año<select value={form.anio} onChange={set("anio")}>{ANIOS.map((a) => <option key={a} value={a}>{a}</option>)}</select></label>
        <label>Modo de fecha<select value={form.modo_fecha} onChange={set("modo_fecha")}>{MODOS_FECHA.map((m) => <option key={m}>{m}</option>)}</select></label>
        {form.modo_fecha !== "Año completo" && (
          <label>{form.modo_fecha === "Rango de meses" ? "Mes inicio" : "Mes"}<select value={form.mes_inicio} onChange={set("mes_inicio")}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
        )}
        {form.modo_fecha === "Rango de meses" && (
          <label>Mes fin<select value={form.mes_fin} onChange={set("mes_fin")}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
        )}
        {form.modo_fecha === "Mes" && (
          <label>Día (0 = todo el mes)<input type="number" min={0} max={31} value={form.dia} onChange={set("dia")} /></label>
        )}
        <label className="ma-sri-check">Incluir<span className="ma-sri-check-fila">
          <label><input type="checkbox" checked={form.incluir_xml} onChange={set("incluir_xml")} /> XML</label>
          <label><input type="checkbox" checked={form.incluir_pdf} onChange={set("incluir_pdf")} /> PDF</label>
        </span></label>
      </div>
      <div className="ma-sri-descarga-acciones">
        <button type="button" className="ma-sri-boton-ejecutar" onClick={consolidar} disabled={estado === "procesando"}>{estado === "procesando" ? "Consolidando…" : "Consolidar"}</button>
      </div>
      {estado === "listo" && (
        <div className="ma-sri-resultado ma-sri-resultado-ok">
          <ResumenResultado r={resultado} titulo="✅ Consolidación lista" />
          {(resultado?.reporte_xml || resultado?.reporte_pdf) && (
            <div className="ma-sri-descarga-acciones">
              {resultado?.reporte_xml && <button type="button" className="ma-boton" onClick={() => bajar(resultado.reporte_xml, "xml")} disabled={Boolean(bajando)}>{bajando === "xml" ? "Preparando…" : "Descargar reporte XML (Excel)"}</button>}
              {resultado?.reporte_pdf && <button type="button" className="ma-boton" onClick={() => bajar(resultado.reporte_pdf, "pdf")} disabled={Boolean(bajando)}>{bajando === "pdf" ? "Preparando…" : "Descargar reporte PDF (Excel)"}</button>}
              {resultado?.destino && <button type="button" className="ma-boton" onClick={() => bajar(resultado.destino, "zip")} disabled={Boolean(bajando)}>{bajando === "zip" ? "Preparando…" : "Descargar consolidado (ZIP)"}</button>}
            </div>
          )}
        </div>
      )}
      {error && <div className="ma-sri-resultado ma-sri-resultado-error">{error}</div>}
    </section>
  );
}

// ---------- Subpágina: Reconstruir XML (PDF→XML de Emitidos, por mes) ----------
function SubReconstruccion() {
  const [ruc, setRuc] = useState("");
  const [estado, setEstado] = useState("idle");
  const [resultado, setResultado] = useState(null);
  const [permiso, setPermiso] = useState(null);
  const [error, setError] = useState("");
  const [bajando, setBajando] = useState(false);

  async function ejecutar() {
    setError(""); setResultado(null);
    if (!/^\d{13}$/.test(ruc.trim())) { setError("El RUC debe tener 13 dígitos."); return; }
    setEstado("procesando");
    try {
      const p = await sriPermiso(`SRI reconstruir ${ruc.trim()}`);
      const r = await sriReconstruir(p.url, p.token, { carpeta: `descargas/${ruc.trim()}` });
      setPermiso(p); setResultado(r); setEstado(r.ok === false ? "error" : "listo");
      if (r.ok === false) setError(r.message || "No se pudo reconstruir.");
    } catch (e) { setError(e?.message || "No se pudo reconstruir."); setEstado("error"); }
  }
  async function bajar() {
    if (!permiso || !resultado?.destino) return;
    setBajando(true); setError("");
    try { const p = await sriPermiso(`SRI reconstruir ${ruc.trim()}`); await sriDescargarArchivo(p.url, p.token, resultado.destino, `xml_reconstruidos_${ruc.trim()}.zip`); }
    catch (e) { setError(e?.message || "No se pudo descargar."); }
    finally { setBajando(false); }
  }

  return (
    <section className="ma-tarjeta ma-sri-descarga">
      <div className="ma-sri-descarga-cab">
        <h3>Reconstruir XML (Emitidos)</h3>
        <span>Arma los XML de los comprobantes emitidos desde los PDF/reportes ya descargados, agrupados por mes. Útil cuando el SRI ya no entrega el XML (más de ~1 mes). Los XML salen SIN firma: sirven para contabilidad y auditoría, no sustituyen al comprobante autorizado.</span>
      </div>
      <div className="ma-sri-form">
        <label>RUC del cliente<input value={ruc} onChange={(e) => setRuc(e.target.value)} inputMode="numeric" maxLength={13} placeholder="1791859596001" /></label>
      </div>
      <div className="ma-sri-descarga-acciones">
        <button type="button" className="ma-sri-boton-ejecutar" onClick={ejecutar} disabled={estado === "procesando"}>{estado === "procesando" ? "Reconstruyendo…" : "Reconstruir XML"}</button>
      </div>
      {estado === "listo" && <div className="ma-sri-resultado ma-sri-resultado-ok"><ResumenOffline r={resultado} titulo="✅ Reconstrucción lista" onDescargar={bajar} bajando={bajando} textoDescarga="Descargar XML (ZIP)" /></div>}
      {error && <div className="ma-sri-resultado ma-sri-resultado-error">{error}</div>}
    </section>
  );
}

// ---------- Subpágina: Cruce Retención ↔ Factura ----------
function SubCruceRetenciones() {
  const [form, setForm] = useState({ ruc: "", sentido: "emitidas", direccion: "facturas", subcarpeta_facturas: "", refrescar_portal: false, con_portal: false, clave: "" });
  const [fase, setFase] = useState("idle"); // idle|procesando|captcha|listo|error
  const [resultado, setResultado] = useState(null);
  const [permiso, setPermiso] = useState(null);
  const [progreso, setProgreso] = useState([]);
  const [captchaImg, setCaptchaImg] = useState(null);
  const [captchaCodigo, setCaptchaCodigo] = useState("");
  const [segundos, setSegundos] = useState(0);
  const [verVivo, setVerVivo] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [error, setError] = useState("");
  const [bajando, setBajando] = useState(false);
  const ctx = useRef({ url: "", token: "", id: "", vivo: false });
  const set = (k) => (e) => { const v = e.target.type === "checkbox" ? e.target.checked : e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  useEffect(() => () => { ctx.current.vivo = false; }, []);
  useEffect(() => {
    if (!(fase === "procesando" || fase === "captcha")) return undefined;
    const t = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [fase]);
  const trabajando = fase === "procesando" || fase === "captcha";

  async function poll() {
    if (!ctx.current.vivo) return;
    try {
      const est = await sriEstado(ctx.current.url, await tokenVigente(ctx), ctx.current.id);
      setProgreso(est.progreso || []);
      if (est.estado === "captcha") { setFase("captcha"); setCaptchaImg(est.captcha_img_b64 || null); }
      else if (est.estado === "listo") { ctx.current.vivo = false; setResultado(est.resultado || {}); setFase(est.resultado?.ok === false ? "error" : "listo"); if (est.resultado?.ok === false) setError(est.resultado.message || "Sin resultados."); return; }
      else if (est.estado === "error" || est.estado === "cancelado") { ctx.current.vivo = false; setError(est.error || "El cruce falló."); setFase("error"); return; }
      else { setFase("procesando"); setCaptchaImg(null); }
      setCancelando(Boolean(est.cancelando));
    } catch { /* red transitoria */ }
    setTimeout(poll, SONDEO_MS);
  }

  async function ejecutar() {
    setError(""); setResultado(null); setProgreso([]); setCaptchaImg(null); setSegundos(0); setCancelando(false);
    if (!/^\d{13}$/.test(form.ruc.trim())) { setError("El RUC debe tener 13 dígitos."); return; }
    if (form.con_portal && !form.clave) { setError("Falta la clave del SRI para buscar en el portal."); return; }
    const carpeta = `descargas/${form.ruc.trim()}`;
    setFase("procesando");
    try {
      const encargo = `SRI cruce ${form.ruc.trim()}`;
      const p = await sriPermiso(encargo);
      const params = { carpeta_retenciones: carpeta, base_ruc: carpeta, sentido: form.sentido, direccion: form.direccion };
      // Dirección "facturas": la carpeta de facturas define el período (incluye
      // los meses sin ninguna retención). Es una subcarpeta de descargas/<ruc>.
      const sub = form.subcarpeta_facturas.trim().replace(/^[/\\]+|[/\\]+$/g, "");
      if (form.direccion === "facturas" && sub) params.carpetas_facturas = [`${carpeta}/${sub}`];
      if (form.con_portal) { params.ruc = form.ruc.trim(); params.clave = form.clave; params.refrescar_portal = form.refrescar_portal; }
      const r = await sriCruceRetenciones(p.url, p.token, params);
      if (form.con_portal && r && r.id) {
        ctx.current = { ...sesionDesdePermiso(p), encargo, id: r.id, vivo: true };
        setPermiso(p); setForm((f) => ({ ...f, clave: "" }));
        poll();
      } else {
        setPermiso(p); setResultado(r); setFase(r.ok === false ? "error" : "listo");
        if (r.ok === false) setError(r.message || "No se pudo generar el cruce.");
      }
    } catch (e) { setError(e?.message || "No se pudo generar el cruce."); setFase("error"); }
  }

  async function enviarCaptcha() {
    if (!captchaCodigo.trim()) return;
    try { await sriEnviarCaptcha(ctx.current.url, await tokenVigente(ctx), ctx.current.id, captchaCodigo.trim()); setCaptchaCodigo(""); setCaptchaImg(null); setFase("procesando"); }
    catch (e) { setError(e?.message || "No se pudo enviar el captcha."); }
  }

  async function bajar() {
    if (!permiso || !resultado?.excel_path) return;
    setBajando(true); setError("");
    try { const p = await sriPermiso("SRI descarga de reporte"); await sriDescargarArchivo(p.url, p.token, resultado.excel_path); }
    catch (e) { setError(e?.message || "No se pudo descargar."); }
    finally { setBajando(false); }
  }

  return (
    <section className="ma-tarjeta ma-sri-descarga">
      <div className="ma-sri-descarga-cab">
        <h3>Retención ↔ Factura</h3>
        <span>Cruza los comprobantes de retención contra sus facturas de sustento. Ideal para verificar la retención que le hicimos al proveedor contra su factura de compra. Por defecto usa solo lo ya descargado; puedes pedir que el robot baje del SRI lo que falte.</span>
      </div>
      <div className="ma-sri-form">
        <label>RUC del cliente<input value={form.ruc} onChange={set("ruc")} inputMode="numeric" maxLength={13} placeholder="1791859596001" disabled={trabajando} /></label>
        <label>Sentido
          <select value={form.sentido} onChange={set("sentido")} disabled={trabajando}>
            <option value="emitidas">Retención emitida ↔ factura de compra (Recibidos)</option>
            <option value="recibidas">Retención recibida ↔ factura de venta (Emitidos)</option>
          </select>
        </label>
        <label>Dirección
          <select value={form.direccion} onChange={set("direccion")} disabled={trabajando}>
            <option value="facturas">Una fila por factura (busca su retención)</option>
            <option value="retenciones">Una fila por retención (busca su factura)</option>
          </select>
        </label>
        {form.direccion === "facturas" && (
          <label>Carpeta de facturas (recomendado)
            <input value={form.subcarpeta_facturas} onChange={set("subcarpeta_facturas")} placeholder={form.sentido === "recibidas" ? "Emitidos/Autorizados/Factura/2026" : "Recibidos/Factura/2026"} title={`Subcarpeta dentro de descargas/${form.ruc.trim() || "<ruc>"} con las facturas ya descargadas. Define el período del reporte: se revisan los meses que cubren esas facturas, también los que no tienen ninguna retención. Si la dejas vacía, el período sale de las retenciones.`} disabled={trabajando} />
          </label>
        )}
        <label className="ma-sri-check">Portal
          <span className="ma-sri-check-fila"><label><input type="checkbox" checked={form.con_portal} onChange={set("con_portal")} disabled={trabajando} /> Bajar del SRI lo que falte (login + captcha)</label></span>
        </label>
        {form.con_portal && (
          <label>Clave del SRI
            <input type="password" value={form.clave} onChange={set("clave")} placeholder="•••••••" autoComplete="off" disabled={trabajando} />
          </label>
        )}
        {form.con_portal && (
          <label className="ma-sri-check">Refrescar
            <span className="ma-sri-check-fila"><label><input type="checkbox" checked={form.refrescar_portal} onChange={set("refrescar_portal")} disabled={trabajando} /> Volver a consultar el portal aunque ya tenga las facturas</label></span>
          </label>
        )}
      </div>
      <div className="ma-sri-descarga-acciones">
        <button type="button" className="ma-sri-boton-ejecutar" onClick={ejecutar} disabled={trabajando}>{trabajando ? "Cruzando…" : "Generar cruce"}</button>
        {form.con_portal && <BotonDetener ctx={ctx} trabajando={trabajando} cancelando={cancelando} setError={setError} />}
        {form.con_portal && (
          <button type="button" className="ma-boton" onClick={() => setVerVivo((v) => !v)}>{verVivo ? "Ocultar vista en vivo" : "🔴 Ver el robot en vivo"}</button>
        )}
        {form.con_portal && <span className="ma-sri-descarga-clave-nota">La clave va directo al motor de la firma; no se guarda ni pasa por el servidor web.</span>}
      </div>

      {verVivo && form.con_portal && <VistaEnVivo encargo="SRI vista en vivo (cruce)" />}

      {captchaImg && (
        <div className="ma-sri-captcha" role="dialog" aria-label="Resolver captcha">
          <p><strong>El SRI pide un captcha.</strong> Escribe lo que ves:</p>
          <img alt="captcha del SRI" src={`data:image/png;base64,${captchaImg}`} className="ma-sri-captcha-img" />
          <div className="ma-sri-captcha-fila">
            <input value={captchaCodigo} onChange={(e) => setCaptchaCodigo(e.target.value)} placeholder="Código" autoFocus onKeyDown={(e) => e.key === "Enter" && enviarCaptcha()} />
            <button type="button" className="ma-sri-boton-ejecutar" onClick={enviarCaptcha}>Enviar</button>
          </div>
        </div>
      )}
      {trabajando && (
        <div className="ma-sri-trabajando">
          <span className="ma-sri-spinner" aria-hidden="true" />
          <span>El robot está trabajando en el servidor… <strong>{segundos}s</strong>{fase === "captcha" ? " · esperando que resuelvas el captcha" : (form.con_portal ? " · bajando del SRI lo que falte y cruzando" : " · cruzando")}</span>
        </div>
      )}
      {progreso.length > 0 && <ul className="ma-sri-progreso">{progreso.slice(-8).map((m, i) => <li key={i}>{m}</li>)}</ul>}
      {fase === "listo" && <div className="ma-sri-resultado ma-sri-resultado-ok"><ResumenOffline r={resultado} titulo="✅ Cruce listo" onDescargar={resultado?.excel_path ? bajar : null} bajando={bajando} textoDescarga="Descargar Excel" /></div>}
      {error && <div className="ma-sri-resultado ma-sri-resultado-error">{error}</div>}
    </section>
  );
}

// ---------- Subpágina: Factura ↔ Retención (sentido inverso: facturas sin retención) ----------
const _ETIQUETAS_FVR = {
  total_facturas: "Facturas revisadas", con_retencion: "Con retención", sin_retencion: "Sin retención",
  no_consultado: "No consultadas", error_consulta: "Error de consulta", duplicados: "Con retención duplicada",
  retenciones_encontradas: "Retenciones", retenciones_sin_factura: "Retenciones sin factura",
  otros_sustentos: "Otros sustentos", facturas_ilegibles: "Facturas ilegibles", retenciones_ilegibles: "Retenciones ilegibles",
};
function SubFacturaRetencion() {
  const [form, setForm] = useState({
    ruc: "", tipo_factura: "emitidas", sub_facturas: "", sub_retenciones: "", con_portal: false, clave: "",
    refrescar_portal: false, anio: ANIO_ACTUAL, mes_inicio: 1, mes_fin: 12,
  });
  const [fase, setFase] = useState("idle"); // idle|procesando|captcha|listo|error
  const [resultado, setResultado] = useState(null);
  const [permiso, setPermiso] = useState(null);
  const [progreso, setProgreso] = useState([]);
  const [captchaImg, setCaptchaImg] = useState(null);
  const [captchaCodigo, setCaptchaCodigo] = useState("");
  const [segundos, setSegundos] = useState(0);
  const [verVivo, setVerVivo] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [error, setError] = useState("");
  const [bajando, setBajando] = useState(false);
  const ctx = useRef({ url: "", token: "", id: "", vivo: false });
  const set = (k) => (e) => { const v = e.target.type === "checkbox" ? e.target.checked : e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  useEffect(() => () => { ctx.current.vivo = false; }, []);
  useEffect(() => {
    if (!(fase === "procesando" || fase === "captcha")) return undefined;
    const t = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [fase]);
  const trabajando = fase === "procesando" || fase === "captcha";
  const emitidas = form.tipo_factura === "emitidas";
  const limpiar = (s) => s.trim().replace(/^[/\\]+|[/\\]+$/g, "");

  async function poll() {
    if (!ctx.current.vivo) return;
    try {
      const est = await sriEstado(ctx.current.url, await tokenVigente(ctx), ctx.current.id);
      setProgreso(est.progreso || []);
      if (est.estado === "captcha") { setFase("captcha"); setCaptchaImg(est.captcha_img_b64 || null); }
      else if (est.estado === "listo") { ctx.current.vivo = false; setResultado(est.resultado || {}); setFase(est.resultado?.ok === false ? "error" : "listo"); if (est.resultado?.ok === false) setError(est.resultado.message || "Sin resultados."); return; }
      else if (est.estado === "error" || est.estado === "cancelado") { ctx.current.vivo = false; setError(est.error || "El cruce falló."); setFase("error"); return; }
      else { setFase("procesando"); setCaptchaImg(null); }
      setCancelando(Boolean(est.cancelando));
    } catch { /* red transitoria */ }
    setTimeout(poll, SONDEO_MS);
  }

  async function ejecutar() {
    setError(""); setResultado(null); setProgreso([]); setCaptchaImg(null); setSegundos(0); setCancelando(false);
    if (!/^\d{13}$/.test(form.ruc.trim())) { setError("El RUC debe tener 13 dígitos."); return; }
    if (form.con_portal && !form.clave) { setError("Falta la clave del SRI para consultar el portal."); return; }
    const subF = limpiar(form.sub_facturas);
    const subR = limpiar(form.sub_retenciones);
    if (!subF && !form.con_portal) { setError("Sin carpeta de facturas hay que consultar el portal: marca la casilla e ingresa la clave."); return; }
    if (!subF && form.con_portal && Number(form.mes_fin) < Number(form.mes_inicio)) { setError("El mes fin debe ser mayor o igual al mes inicio."); return; }
    const carpeta = `descargas/${form.ruc.trim()}`;
    const encargo = `SRI factura-retención ${form.ruc.trim()}`;
    setFase("procesando");
    try {
      const p = await sriPermiso(encargo);
      const params = { tipo_factura: form.tipo_factura, ruc: form.ruc.trim() };
      if (subF) params.carpetas_facturas = [`${carpeta}/${subF}`];
      if (subR) params.carpeta_retenciones = `${carpeta}/${subR}`;
      if (form.con_portal) {
        params.clave = form.clave; params.refrescar_portal = form.refrescar_portal;
        if (!subF) { params.anio = Number(form.anio); params.mes_inicio = Number(form.mes_inicio); params.mes_fin = Number(form.mes_fin); }
      }
      const r = await sriFacturaRetencion(p.url, p.token, params);
      if (form.con_portal && r && r.id) {
        ctx.current = { ...sesionDesdePermiso(p), encargo, id: r.id, vivo: true };
        setPermiso(p); setForm((f) => ({ ...f, clave: "" }));
        poll();
      } else {
        setPermiso(p); setResultado(r); setFase(r.ok === false ? "error" : "listo");
        if (r.ok === false) setError(r.message || "No se pudo generar el cruce.");
      }
    } catch (e) { setError(e?.message || "No se pudo generar el cruce."); setFase("error"); }
  }

  async function enviarCaptcha() {
    if (!captchaCodigo.trim()) return;
    try { await sriEnviarCaptcha(ctx.current.url, await tokenVigente(ctx), ctx.current.id, captchaCodigo.trim()); setCaptchaCodigo(""); setCaptchaImg(null); setFase("procesando"); }
    catch (e) { setError(e?.message || "No se pudo enviar el captcha."); }
  }

  async function bajar() {
    if (!permiso || !resultado?.excel_path) return;
    setBajando(true); setError("");
    try { const p = await sriPermiso("SRI descarga de reporte"); await sriDescargarArchivo(p.url, p.token, resultado.excel_path); }
    catch (e) { setError(e?.message || "No se pudo descargar."); }
    finally { setBajando(false); }
  }

  return (
    <section className="ma-tarjeta ma-sri-descarga">
      <div className="ma-sri-descarga-cab">
        <h3>Factura ↔ Retención</h3>
        <span>Parte de las facturas y busca la retención de cada una. El hallazgo principal son las <strong>facturas sin retención</strong>. Es el sentido inverso de «Retención ↔ Factura», que sigue disponible.</span>
      </div>
      <div className="ma-sri-form">
        <label>RUC del contribuyente auditado<input value={form.ruc} onChange={set("ruc")} inputMode="numeric" maxLength={13} placeholder="1791859596001" disabled={trabajando} /></label>
        <label>Tipo de factura
          <select value={form.tipo_factura} onChange={set("tipo_factura")} disabled={trabajando}>
            <option value="emitidas">Facturas emitidas — ventas realizadas por el contribuyente</option>
            <option value="recibidas">Facturas recibidas — compras realizadas por el contribuyente</option>
          </select>
        </label>
        <label>Carpeta de facturas (opcional)
          <input value={form.sub_facturas} onChange={set("sub_facturas")} placeholder={emitidas ? "Emitidos/Autorizados/Factura/2026" : "Recibidos/Factura/2026"} title={`Subcarpeta dentro de descargas/${form.ruc.trim() || "<ruc>"} con facturas ya descargadas (XML, Excel del reporte o PDF). Define el período del cruce. Si la dejas vacía, se consultan en el portal con el período de abajo.`} disabled={trabajando} />
        </label>
        <label>Carpeta de retenciones (opcional)
          <input value={form.sub_retenciones} onChange={set("sub_retenciones")} placeholder={emitidas ? "Recibidos/Comprobante de Retencion/2026" : "Emitidos/Autorizados/Comprobante de Retencion/2026"} title={`Subcarpeta dentro de descargas/${form.ruc.trim() || "<ruc>"} con retenciones ya descargadas. Si falta un mes, se baja del portal (con clave); si no hay clave, ese mes queda como «No consultado».`} disabled={trabajando} />
        </label>
        <label className="ma-sri-check">Portal
          <span className="ma-sri-check-fila"><label><input type="checkbox" checked={form.con_portal} onChange={set("con_portal")} disabled={trabajando} /> Consultar en el SRI lo que falte (login + captcha)</label></span>
        </label>
        {form.con_portal && (
          <label>Clave del SRI
            <input type="password" value={form.clave} onChange={set("clave")} placeholder="•••••••" autoComplete="off" disabled={trabajando} />
          </label>
        )}
        {form.con_portal && (
          <label className="ma-sri-check">Refrescar
            <span className="ma-sri-check-fila"><label><input type="checkbox" checked={form.refrescar_portal} onChange={set("refrescar_portal")} disabled={trabajando} /> Volver a consultar el portal aunque los archivos ya existan localmente</label></span>
          </label>
        )}
        {form.con_portal && !limpiar(form.sub_facturas) && (
          <>
            <label>Año a revisar<select value={form.anio} onChange={set("anio")} disabled={trabajando}>{ANIOS.map((a) => <option key={a} value={a}>{a}</option>)}</select></label>
            <label>Mes inicio<select value={form.mes_inicio} onChange={set("mes_inicio")} disabled={trabajando}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
            <label>Mes fin<select value={form.mes_fin} onChange={set("mes_fin")} disabled={trabajando}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
          </>
        )}
      </div>
      <p className="ma-sri-tabla-nota">
        {emitidas
          ? "Las facturas se consultan en el portal Emitidos y las retenciones se buscan en Recibidos. El sistema identifica qué facturas de venta tienen retención del cliente y cuáles no."
          : "Las facturas se consultan en el portal Recibidos y las retenciones se buscan en Emitidos. El sistema identifica qué facturas de compra tienen una retención emitida por el contribuyente y cuáles no."}
        {" "}Un mes sin ninguna retención también se revisa: el período lo marcan las facturas. Lo que no se pudo revisar sale como «No consultado», nunca como «Sin retención».
      </p>
      <div className="ma-sri-descarga-acciones">
        <button type="button" className="ma-sri-boton-ejecutar" onClick={ejecutar} disabled={trabajando}>{trabajando ? "Cruzando…" : "Generar cruce"}</button>
        {form.con_portal && <BotonDetener ctx={ctx} trabajando={trabajando} cancelando={cancelando} setError={setError} />}
        {form.con_portal && (
          <button type="button" className="ma-boton" onClick={() => setVerVivo((v) => !v)}>{verVivo ? "Ocultar vista en vivo" : "🔴 Ver el robot en vivo"}</button>
        )}
        {form.con_portal && <span className="ma-sri-descarga-clave-nota">La clave va directo al motor de la firma; no se guarda ni pasa por el servidor web.</span>}
      </div>

      {verVivo && form.con_portal && <VistaEnVivo encargo="SRI vista en vivo (factura-retención)" />}

      {captchaImg && (
        <div className="ma-sri-captcha" role="dialog" aria-label="Resolver captcha">
          <p><strong>El SRI pide un captcha.</strong> Escribe lo que ves:</p>
          <img alt="captcha del SRI" src={`data:image/png;base64,${captchaImg}`} className="ma-sri-captcha-img" />
          <div className="ma-sri-captcha-fila">
            <input value={captchaCodigo} onChange={(e) => setCaptchaCodigo(e.target.value)} placeholder="Código" autoFocus onKeyDown={(e) => e.key === "Enter" && enviarCaptcha()} />
            <button type="button" className="ma-sri-boton-ejecutar" onClick={enviarCaptcha}>Enviar</button>
          </div>
        </div>
      )}
      {trabajando && (
        <div className="ma-sri-trabajando">
          <span className="ma-sri-spinner" aria-hidden="true" />
          <span>El robot está trabajando en el servidor… <strong>{segundos}s</strong>{fase === "captcha" ? " · esperando que resuelvas el captcha" : (form.con_portal ? " · consultando el SRI y cruzando" : " · cruzando")}</span>
        </div>
      )}
      {progreso.length > 0 && <ul className="ma-sri-progreso">{progreso.slice(-8).map((m, i) => <li key={i}>{m}</li>)}</ul>}
      {fase === "listo" && resultado && (
        <div className="ma-sri-resultado ma-sri-resultado-ok">
          <div className="ma-sri-resumen">
            <div className="ma-sri-resumen-titulo">✅ Cruce listo</div>
            {resultado.message && <div className="ma-sri-resumen-msg">{resultado.message}</div>}
            {resultado.periodo_analizado && <div>Período analizado: <strong>{resultado.periodo_analizado}</strong></div>}
            {Array.isArray(resultado.meses_consultados) && resultado.meses_consultados.length > 0 && <div>Meses de retención revisados: {resultado.meses_consultados.join(", ")}</div>}
            {Array.isArray(resultado.meses_no_consultados) && resultado.meses_no_consultados.length > 0 && <div className="ma-sri-resultado-aviso">No revisados: {resultado.meses_no_consultados.join(", ")}</div>}
            <div className="ma-sri-resumen-conteos">
              {Object.entries(_ETIQUETAS_FVR).filter(([k]) => typeof resultado[k] === "number").map(([k, et]) => (
                <span key={k} className={k === "sin_retencion" && resultado[k] > 0 ? "ma-sri-resultado-aviso" : undefined}>{et}: <strong>{resultado[k]}</strong></span>
              ))}
            </div>
            {resultado.excel_path && (
              <div className="ma-sri-descarga-acciones">
                <button type="button" className="ma-boton" onClick={bajar} disabled={bajando}>{bajando ? "Preparando…" : "Descargar Excel (6 hojas)"}</button>
              </div>
            )}
            <details className="ma-sri-detalle"><summary>Ver detalle técnico</summary><pre>{JSON.stringify(resultado, null, 2)}</pre></details>
          </div>
        </div>
      )}
      {error && <div className="ma-sri-resultado ma-sri-resultado-error">{error}</div>}
    </section>
  );
}

// ---------- Subpágina: Valor neto (factura − notas de crédito) ----------
function SubValorNeto() {
  const [form, setForm] = useState({ ruc: "", con_portal: false, clave: "" });
  const [fase, setFase] = useState("idle"); // idle|procesando|captcha|listo|error
  const [resultado, setResultado] = useState(null);
  const [permiso, setPermiso] = useState(null);
  const [progreso, setProgreso] = useState([]);
  const [captchaImg, setCaptchaImg] = useState(null);
  const [captchaCodigo, setCaptchaCodigo] = useState("");
  const [segundos, setSegundos] = useState(0);
  const [verVivo, setVerVivo] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [error, setError] = useState("");
  const [bajando, setBajando] = useState(false);
  const ctx = useRef({ url: "", token: "", id: "", vivo: false });
  const set = (k) => (e) => { const v = e.target.type === "checkbox" ? e.target.checked : e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  useEffect(() => () => { ctx.current.vivo = false; }, []);
  useEffect(() => {
    if (!(fase === "procesando" || fase === "captcha")) return undefined;
    const t = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [fase]);
  const trabajando = fase === "procesando" || fase === "captcha";

  async function poll() {
    if (!ctx.current.vivo) return;
    try {
      const est = await sriEstado(ctx.current.url, await tokenVigente(ctx), ctx.current.id);
      setProgreso(est.progreso || []);
      if (est.estado === "captcha") { setFase("captcha"); setCaptchaImg(est.captcha_img_b64 || null); }
      else if (est.estado === "listo") { ctx.current.vivo = false; setResultado(est.resultado || {}); setFase(est.resultado?.ok === false ? "error" : "listo"); if (est.resultado?.ok === false) setError(est.resultado.message || "Sin resultados."); return; }
      else if (est.estado === "error" || est.estado === "cancelado") { ctx.current.vivo = false; setError(est.error || "El reporte falló."); setFase("error"); return; }
      else { setFase("procesando"); setCaptchaImg(null); }
      setCancelando(Boolean(est.cancelando));
    } catch { /* red transitoria */ }
    setTimeout(poll, SONDEO_MS);
  }

  async function ejecutar() {
    setError(""); setResultado(null); setProgreso([]); setCaptchaImg(null); setSegundos(0); setCancelando(false);
    if (!/^\d{13}$/.test(form.ruc.trim())) { setError("El RUC debe tener 13 dígitos."); return; }
    if (form.con_portal && !form.clave) { setError("Falta la clave del SRI para buscar en el portal."); return; }
    const carpeta = `descargas/${form.ruc.trim()}`;
    setFase("procesando");
    try {
      const encargo = `SRI valor neto ${form.ruc.trim()}`;
      const p = await sriPermiso(encargo);
      const params = { carpeta_nc: carpeta, ruc: form.ruc.trim() };
      if (form.con_portal) params.clave = form.clave;
      const r = await sriValorNeto(p.url, p.token, params);
      if (form.con_portal && r && r.id) {
        ctx.current = { ...sesionDesdePermiso(p), encargo, id: r.id, vivo: true };
        setPermiso(p); setForm((f) => ({ ...f, clave: "" }));
        poll();
      } else {
        setPermiso(p); setResultado(r); setFase(r.ok === false ? "error" : "listo");
        if (r.ok === false) setError(r.message || "No se pudo generar el reporte.");
      }
    } catch (e) { setError(e?.message || "No se pudo generar el reporte."); setFase("error"); }
  }

  async function enviarCaptcha() {
    if (!captchaCodigo.trim()) return;
    try { await sriEnviarCaptcha(ctx.current.url, await tokenVigente(ctx), ctx.current.id, captchaCodigo.trim()); setCaptchaCodigo(""); setCaptchaImg(null); setFase("procesando"); }
    catch (e) { setError(e?.message || "No se pudo enviar el captcha."); }
  }

  async function bajar() {
    if (!permiso || !resultado?.excel_path) return;
    setBajando(true); setError("");
    try { const p = await sriPermiso("SRI descarga de reporte"); await sriDescargarArchivo(p.url, p.token, resultado.excel_path); }
    catch (e) { setError(e?.message || "No se pudo descargar."); }
    finally { setBajando(false); }
  }

  return (
    <section className="ma-tarjeta ma-sri-descarga">
      <div className="ma-sri-descarga-cab">
        <h3>Valor neto (factura − notas de crédito)</h3>
        <span>Cruza cada nota de crédito contra su factura para obtener el valor neto de compra. Por defecto usa lo ya descargado; puedes pedir que el robot baje del SRI las facturas modificadas que falten.</span>
      </div>
      <div className="ma-sri-form">
        <label>RUC del cliente<input value={form.ruc} onChange={set("ruc")} inputMode="numeric" maxLength={13} placeholder="1791859596001" disabled={trabajando} /></label>
        <label className="ma-sri-check">Portal
          <span className="ma-sri-check-fila"><label><input type="checkbox" checked={form.con_portal} onChange={set("con_portal")} disabled={trabajando} /> Bajar del SRI las facturas que falten (login + captcha)</label></span>
        </label>
        {form.con_portal && (
          <label>Clave del SRI
            <input type="password" value={form.clave} onChange={set("clave")} placeholder="•••••••" autoComplete="off" disabled={trabajando} />
          </label>
        )}
      </div>
      <div className="ma-sri-descarga-acciones">
        <button type="button" className="ma-sri-boton-ejecutar" onClick={ejecutar} disabled={trabajando}>{trabajando ? "Calculando…" : "Generar valor neto"}</button>
        {form.con_portal && <BotonDetener ctx={ctx} trabajando={trabajando} cancelando={cancelando} setError={setError} />}
        {form.con_portal && (
          <button type="button" className="ma-boton" onClick={() => setVerVivo((v) => !v)}>{verVivo ? "Ocultar vista en vivo" : "🔴 Ver el robot en vivo"}</button>
        )}
        {form.con_portal && <span className="ma-sri-descarga-clave-nota">La clave va directo al motor de la firma; no se guarda ni pasa por el servidor web.</span>}
      </div>

      {verVivo && form.con_portal && <VistaEnVivo encargo="SRI vista en vivo (valor neto)" />}

      {captchaImg && (
        <div className="ma-sri-captcha" role="dialog" aria-label="Resolver captcha">
          <p><strong>El SRI pide un captcha.</strong> Escribe lo que ves:</p>
          <img alt="captcha del SRI" src={`data:image/png;base64,${captchaImg}`} className="ma-sri-captcha-img" />
          <div className="ma-sri-captcha-fila">
            <input value={captchaCodigo} onChange={(e) => setCaptchaCodigo(e.target.value)} placeholder="Código" autoFocus onKeyDown={(e) => e.key === "Enter" && enviarCaptcha()} />
            <button type="button" className="ma-sri-boton-ejecutar" onClick={enviarCaptcha}>Enviar</button>
          </div>
        </div>
      )}
      {trabajando && (
        <div className="ma-sri-trabajando">
          <span className="ma-sri-spinner" aria-hidden="true" />
          <span>El robot está trabajando en el servidor… <strong>{segundos}s</strong>{fase === "captcha" ? " · esperando que resuelvas el captcha" : (form.con_portal ? " · bajando del SRI las facturas que falten" : " · calculando")}</span>
        </div>
      )}
      {progreso.length > 0 && <ul className="ma-sri-progreso">{progreso.slice(-8).map((m, i) => <li key={i}>{m}</li>)}</ul>}
      {fase === "listo" && <div className="ma-sri-resultado ma-sri-resultado-ok"><ResumenOffline r={resultado} titulo="✅ Reporte listo" onDescargar={resultado?.excel_path ? bajar : null} bajando={bajando} textoDescarga="Descargar Excel" /></div>}
      {error && <div className="ma-sri-resultado ma-sri-resultado-error">{error}</div>}
    </section>
  );
}

// ---------- Subpágina: Declaraciones presentadas (login + captcha) ----------
function SubDeclaraciones() {
  const anioActual = ANIO_ACTUAL;
  const [form, setForm] = useState({ ruc: "", clave: "", obligacion: "iva_104", anio: anioActual, mes: 1, documento: DOCS_DECL[0] });
  const [fase, setFase] = useState("idle"); // idle|procesando|captcha|listo|error
  const [resultado, setResultado] = useState(null);
  const [permiso, setPermiso] = useState(null);
  const [progreso, setProgreso] = useState([]);
  const [captchaImg, setCaptchaImg] = useState(null);
  const [captchaCodigo, setCaptchaCodigo] = useState("");
  const [segundos, setSegundos] = useState(0);
  const [verVivo, setVerVivo] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [error, setError] = useState("");
  const [bajando, setBajando] = useState(false);
  const ctx = useRef({ url: "", token: "", id: "", vivo: false });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  useEffect(() => () => { ctx.current.vivo = false; }, []);
  useEffect(() => {
    if (!(fase === "procesando" || fase === "captcha")) return undefined;
    const t = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [fase]);
  const trabajando = fase === "procesando" || fase === "captcha";
  const esMensual = OBLIGACIONES_DECL.find((o) => o.id === form.obligacion)?.mensual;

  async function poll() {
    if (!ctx.current.vivo) return;
    try {
      const est = await sriEstado(ctx.current.url, await tokenVigente(ctx), ctx.current.id);
      setProgreso(est.progreso || []);
      if (est.estado === "captcha") { setFase("captcha"); setCaptchaImg(est.captcha_img_b64 || null); }
      else if (est.estado === "listo") { ctx.current.vivo = false; setResultado(est.resultado || {}); setFase(est.resultado?.ok === false ? "error" : "listo"); if (est.resultado?.ok === false) setError(est.resultado.message || "Sin resultados."); return; }
      else if (est.estado === "error" || est.estado === "cancelado") { ctx.current.vivo = false; setError(est.error || "La descarga falló."); setFase("error"); return; }
      else { setFase("procesando"); setCaptchaImg(null); }
      setCancelando(Boolean(est.cancelando));
    } catch { /* red transitoria */ }
    setTimeout(poll, SONDEO_MS);
  }

  async function ejecutar() {
    setError(""); setResultado(null); setProgreso([]); setCaptchaImg(null); setSegundos(0); setCancelando(false);
    if (!/^\d{13}$/.test(form.ruc.trim())) { setError("El RUC debe tener 13 dígitos."); return; }
    if (!form.clave) { setError("Falta la clave del SRI del cliente."); return; }
    setFase("procesando");
    try {
      const encargo = `SRI declaración ${form.ruc.trim()}`;
      const p = await sriPermiso(encargo);
      const params = { ruc: form.ruc.trim(), clave: form.clave, obligacion: form.obligacion, anio: Number(form.anio), documento: form.documento };
      if (esMensual) params.mes = Number(form.mes);
      const r = await sriDeclaracionesDescargar(p.url, p.token, params);
      setPermiso(p); setForm((f) => ({ ...f, clave: "" }));
      if (r && r.id) { ctx.current = { ...sesionDesdePermiso(p), encargo, id: r.id, vivo: true }; poll(); }
      else { setResultado(r); setFase(r?.ok === false ? "error" : "listo"); }
    } catch (e) { setError(e?.message || "No se pudo descargar la declaración."); setFase("error"); }
  }

  async function enviarCaptcha() {
    if (!captchaCodigo.trim()) return;
    try { await sriEnviarCaptcha(ctx.current.url, await tokenVigente(ctx), ctx.current.id, captchaCodigo.trim()); setCaptchaCodigo(""); setCaptchaImg(null); setFase("procesando"); }
    catch (e) { setError(e?.message || "No se pudo enviar el captcha."); }
  }

  async function bajar() {
    if (!permiso || !resultado?.archivo) return;
    setBajando(true); setError("");
    try { const p = await sriPermiso("SRI descarga de declaración"); await sriDescargarArchivo(p.url, p.token, resultado.archivo); }
    catch (e) { setError(e?.message || "No se pudo descargar."); }
    finally { setBajando(false); }
  }

  return (
    <section className="ma-tarjeta ma-sri-descarga">
      <div className="ma-sri-descarga-cab">
        <h3>Declaraciones presentadas</h3>
        <span>Descarga del portal del SRI el formulario de una declaración ya presentada (IVA, Retenciones, Renta). Requiere iniciar sesión en el SRI del cliente; si pide captcha, aparece aquí.</span>
      </div>
      <div className="ma-sri-form">
        <label>RUC del cliente<input value={form.ruc} onChange={set("ruc")} inputMode="numeric" maxLength={13} placeholder="1791859596001" disabled={trabajando} /></label>
        <label>Clave del SRI<input type="password" value={form.clave} onChange={set("clave")} placeholder="•••••••" autoComplete="off" disabled={trabajando} /></label>
        <label>Obligación
          <select value={form.obligacion} onChange={set("obligacion")} disabled={trabajando}>{OBLIGACIONES_DECL.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}</select>
        </label>
        <label>Año
          <select value={form.anio} onChange={set("anio")} disabled={trabajando}>{ANIOS.map((a) => <option key={a} value={a}>{a}</option>)}</select>
        </label>
        {esMensual && (
          <label>Mes
            <select value={form.mes} onChange={set("mes")} disabled={trabajando}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select>
          </label>
        )}
        <label>Documento
          <select value={form.documento} onChange={set("documento")} disabled={trabajando}>{DOCS_DECL.map((d) => <option key={d}>{d}</option>)}</select>
        </label>
      </div>
      <div className="ma-sri-descarga-acciones">
        <button type="button" className="ma-sri-boton-ejecutar" onClick={ejecutar} disabled={trabajando}>{trabajando ? "Descargando…" : "Descargar declaración"}</button>
        <BotonDetener ctx={ctx} trabajando={trabajando} cancelando={cancelando} setError={setError} />
        <button type="button" className="ma-boton" onClick={() => setVerVivo((v) => !v)}>{verVivo ? "Ocultar vista en vivo" : "🔴 Ver el robot en vivo"}</button>
        <span className="ma-sri-descarga-clave-nota">La clave va directo al motor de la firma; no se guarda ni pasa por el servidor web.</span>
      </div>

      {verVivo && <VistaEnVivo encargo="SRI vista en vivo (declaraciones)" />}

      {captchaImg && (
        <div className="ma-sri-captcha" role="dialog" aria-label="Resolver captcha">
          <p><strong>El SRI pide un captcha.</strong> Escribe lo que ves:</p>
          <img alt="captcha del SRI" src={`data:image/png;base64,${captchaImg}`} className="ma-sri-captcha-img" />
          <div className="ma-sri-captcha-fila">
            <input value={captchaCodigo} onChange={(e) => setCaptchaCodigo(e.target.value)} placeholder="Código" autoFocus onKeyDown={(e) => e.key === "Enter" && enviarCaptcha()} />
            <button type="button" className="ma-sri-boton-ejecutar" onClick={enviarCaptcha}>Enviar</button>
          </div>
        </div>
      )}
      {trabajando && (
        <div className="ma-sri-trabajando">
          <span className="ma-sri-spinner" aria-hidden="true" />
          <span>El robot está trabajando en el servidor… <strong>{segundos}s</strong>{fase === "captcha" ? " · esperando que resuelvas el captcha" : " · entrando al SRI y descargando"}</span>
        </div>
      )}
      {progreso.length > 0 && <ul className="ma-sri-progreso">{progreso.slice(-8).map((m, i) => <li key={i}>{m}</li>)}</ul>}
      {fase === "listo" && <div className="ma-sri-resultado ma-sri-resultado-ok"><ResumenOffline r={resultado} titulo="✅ Declaración descargada" onDescargar={resultado?.archivo ? bajar : null} bajando={bajando} textoDescarga="Descargar archivo" /></div>}
      {error && <div className="ma-sri-resultado ma-sri-resultado-error">{error}</div>}
    </section>
  );
}

// ---------- Subpágina 4: Ayuda + alcance ----------
const FUENTES = [
  { nombre: "Robot del SRI", texto: "Descarga los comprobantes electrónicos emitidos y recibidos, incluidas las retenciones.", formatos: ["XML", "PDF"] },
  { nombre: "Declaraciones", texto: "Formularios ya presentados de IVA (104), Retenciones (103) y Renta Sociedades (101): declaración completa, perfilada o comprobante.", formatos: ["PDF"] },
  { nombre: "Anexos tributarios", texto: "ATS, RDEP, dividendos, accionistas y demás. Pendiente: la sección de anexos del portal aún no está mapeada; el robot responde «no disponible».", formatos: ["Pendiente"] },
  { nombre: "Contabilidad del cliente", texto: "Mayor o diario, auxiliares de ventas y compras, nómina y maestros.", formatos: ["Excel", "CSV"] },
];
function SubAyuda() {
  return (
    <section className="ma-sri-ayuda">
      <section className="ma-tarjeta">
        <h3>Cómo usar el robot del SRI</h3>
        <ol className="ma-sri-ayuda-lista">
          <li><strong>Descarga:</strong> pon el RUC y la clave del SRI del cliente, elige el período y los formatos, y pulsa «Descargar». Si el SRI muestra un captcha, aparecerá aquí para que lo escribas. Al terminar, baja los archivos con «Descargar archivos (ZIP)».</li>
          <li><strong>Reporte por fechas:</strong> arma un Excel con lo ya descargado de un RUC entre dos fechas, sin entrar al SRI.</li>
          <li><strong>Historial:</strong> revisa las descargas ya realizadas.</li>
          <li><strong>Consolidación:</strong> une los documentos ya descargados de un RUC por período en un solo reporte.</li>
        </ol>
        <p className="ma-sri-tabla-nota">La clave del SRI del cliente viaja del navegador directo al motor de la firma, se usa solo para esa descarga y no se guarda ni pasa por el servidor web.</p>
      </section>
      <section className="ma-grid ma-sri-fuentes">
        {FUENTES.map((f) => (
          <div className="ma-tarjeta ma-sri-tarjeta-fuente" key={f.nombre}>
            <span className="ma-sri-fuente-nombre">{f.nombre}</span>
            <span className="ma-sri-fuente-texto">{f.texto}</span>
            <div className="ma-sri-formatos">{f.formatos.map((x) => <span className="ma-sri-chip" key={x}>{x}</span>)}</div>
          </div>
        ))}
      </section>
    </section>
  );
}

export default function CumplimientoSRI({ ir }) {
  const [sub, setSub] = useState("descarga");
  return (
    <section className="ma-pagina ma-sri-pagina">
      <div className="ma-sri-breadcrumb">
        <button type="button" className="ma-sri-link" onClick={() => ir("portada")}>Motor de Auditoría Analítica</button>
        <span className="ma-sri-sep">/</span><span>Cumplimiento tributario · SRI</span>
      </div>
      <div className="ma-sri-encabezado">
        <h2>{META.titulo}</h2>
        <button type="button" className="ma-boton" onClick={() => ir("portada")}>← Volver a la portada</button>
      </div>

      <nav aria-label="Pantallas del robot" className="ma-sri-subnav">
        {SUBS.map((s) => (
          <button key={s.id} type="button" className={`ma-sri-subnav-tab${sub === s.id ? " activo" : ""}`} onClick={() => setSub(s.id)}>
            {s.titulo}
          </button>
        ))}
      </nav>

      {sub === "descarga" && <SubDescarga />}
      {sub === "reportefechas" && <SubReporteFechas />}
      {sub === "reportes" && <SubReportes />}
      {sub === "consolidacion" && <SubConsolidacion />}
      {sub === "reconstruccion" && <SubReconstruccion />}
      {sub === "cruce" && <SubCruceRetenciones />}
      {sub === "facturaret" && <SubFacturaRetencion />}
      {sub === "valorneto" && <SubValorNeto />}
      {sub === "declaraciones" && <SubDeclaraciones />}
      {sub === "ayuda" && <SubAyuda />}
    </section>
  );
}
