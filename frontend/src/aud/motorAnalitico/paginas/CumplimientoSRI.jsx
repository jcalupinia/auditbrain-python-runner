import { useEffect, useRef, useState } from "react";
import { PAGINAS } from "../paginas.js";
import {
  sriPermiso,
  sriDescargar,
  sriEstado,
  sriEnviarCaptcha,
  sriDescargarZip,
  sriConsolidar,
  sriHistorial,
} from "../../../api.js";
import "./CumplimientoSRI.css";

const META = PAGINAS.find((p) => p.id === "sri");

// Subpáginas = las pestañas del robot del SRI (aplicacion.py de copia-robot-audit).
const SUBS = [
  { id: "descarga", titulo: "Descarga de comprobantes" },
  { id: "reportes", titulo: "Reportes e historial" },
  { id: "consolidacion", titulo: "Consolidación de documentos" },
  { id: "ayuda", titulo: "Ayuda" },
];

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const ANIO_ACTUAL = new Date().getFullYear();
const ANIOS = Array.from({ length: 10 }, (_, i) => ANIO_ACTUAL - i);
const TIPOS = ["Todos", "Facturas", "Notas de crédito", "Notas de débito", "Retenciones", "Liquidaciones"];
const MODOS_FECHA = ["Mes", "Rango de meses", "Año completo"];
const ESTADOS_EMITIDOS = ["Todos", "Autorizado", "No autorizado"];
// Vista en vivo del robot (noVNC, solo lectura, tailnet-only).
const VNC_URL = "https://auditia.tail70d973.ts.net:8446/vnc.html?autoconnect=1&resize=scale&view_only=1&reconnect=1";

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

// ---------- Subpágina 1: Descarga (login + filtros + captcha relay) ----------
function SubDescarga() {
  const [form, setForm] = useState({
    ruc: "", clave: "", origen: "Recibidos", tipo: "Todos",
    modo_fecha: "Mes", anio: ANIO_ACTUAL, mes: 1, mes_fin: 12, dia: 0,
    estado_emitidos: "Todos", formatoXML: true, formatoPDF: true, modo_rapido: false,
  });
  const [fase, setFase] = useState("idle"); // idle|procesando|captcha|listo|error
  const [progreso, setProgreso] = useState([]);
  const [captchaImg, setCaptchaImg] = useState(null);
  const [captchaCodigo, setCaptchaCodigo] = useState("");
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState("");
  const [bajando, setBajando] = useState(false);
  const [segundos, setSegundos] = useState(0);
  const [verVivo, setVerVivo] = useState(false);
  const ctx = useRef({ url: "", token: "", id: "", vivo: false });
  useEffect(() => () => { ctx.current.vivo = false; }, []);
  useEffect(() => {
    if (!(fase === "procesando" || fase === "captcha")) return undefined;
    const t = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [fase]);

  const set = (k) => (e) => {
    const v = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [k]: v }));
  };
  const trabajando = fase === "procesando" || fase === "captcha";

  async function poll() {
    if (!ctx.current.vivo) return;
    try {
      const est = await sriEstado(ctx.current.url, ctx.current.token, ctx.current.id);
      setProgreso(est.progreso || []);
      if (est.estado === "captcha") { setFase("captcha"); setCaptchaImg(est.captcha_img_b64 || null); }
      else if (est.estado === "listo") { ctx.current.vivo = false; setResultado(est.resultado || {}); setFase("listo"); return; }
      else if (est.estado === "error") { ctx.current.vivo = false; setError(est.error || "La descarga falló."); setFase("error"); return; }
      else { setFase("procesando"); setCaptchaImg(null); }
    } catch { /* red transitoria: seguimos */ }
    setTimeout(poll, 1500);
  }

  async function lanzar() {
    setError(""); setResultado(null); setProgreso([]); setCaptchaImg(null); setSegundos(0);
    if (!/^\d{13}$/.test(form.ruc.trim())) { setError("El RUC debe tener 13 dígitos."); return; }
    if (!form.clave) { setError("Falta la clave del SRI del cliente."); return; }
    const formatos = [form.formatoXML && "XML", form.formatoPDF && "PDF"].filter(Boolean);
    setFase("procesando");
    try {
      const permiso = await sriPermiso(`SRI ${form.ruc.trim()}`);
      const { id } = await sriDescargar(permiso.url, permiso.token, {
        ruc: form.ruc.trim(), clave: form.clave, origen: form.origen, tipo: form.tipo,
        modo_fecha: form.modo_fecha, anio: Number(form.anio), mes: Number(form.mes),
        mes_fin: Number(form.mes_fin), dia: Number(form.dia),
        estado_emitidos: form.origen === "Emitidos" ? form.estado_emitidos : null,
        formatos, modo_rapido: form.modo_rapido,
      });
      ctx.current = { url: permiso.url, token: permiso.token, id, vivo: true };
      setForm((f) => ({ ...f, clave: "" }));
      poll();
    } catch (e) { setError(e?.message || "No se pudo iniciar la descarga."); setFase("error"); }
  }

  async function enviarCaptcha() {
    if (!captchaCodigo.trim()) return;
    try {
      await sriEnviarCaptcha(ctx.current.url, ctx.current.token, ctx.current.id, captchaCodigo.trim());
      setCaptchaCodigo(""); setCaptchaImg(null); setFase("procesando");
    } catch (e) { setError(e?.message || "No se pudo enviar el captcha."); }
  }

  async function bajarZip() {
    setBajando(true); setError("");
    try { await sriDescargarZip(ctx.current.url, ctx.current.token, ctx.current.id); }
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
          <select value={form.tipo} onChange={set("tipo")} disabled={trabajando}>{TIPOS.map((t) => <option key={t}>{t}</option>)}</select>
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
          <label>Estado (emitidos)
            <select value={form.estado_emitidos} onChange={set("estado_emitidos")} disabled={trabajando}>{ESTADOS_EMITIDOS.map((e) => <option key={e}>{e}</option>)}</select>
          </label>
        )}
        <label className="ma-sri-check">Formatos
          <span className="ma-sri-check-fila">
            <label><input type="checkbox" checked={form.formatoXML} onChange={set("formatoXML")} disabled={trabajando} /> XML</label>
            <label><input type="checkbox" checked={form.formatoPDF} onChange={set("formatoPDF")} disabled={trabajando} /> PDF</label>
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

      {verVivo && (
        <div className="ma-sri-vivo">
          <div className="ma-sri-vivo-cab">
            <span>🔴 Robot en vivo — solo lectura</span>
            <span className="ma-sri-vivo-nota">Requiere estar en la red Tailscale de la firma. Verás el navegador del robot navegando el SRI en tiempo real.</span>
          </div>
          <iframe title="Robot SRI en vivo" src={VNC_URL} className="ma-sri-vivo-frame" allow="fullscreen" />
        </div>
      )}

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
      {progreso.length > 0 && <ul className="ma-sri-progreso">{progreso.slice(-8).map((m, i) => <li key={i}>{m}</li>)}</ul>}
      {fase === "listo" && <div className="ma-sri-resultado ma-sri-resultado-ok"><ResumenResultado r={resultado} titulo="✅ Descarga completada" /></div>}
      {error && <div className="ma-sri-resultado ma-sri-resultado-error">{error}</div>}
    </section>
  );
}

// ---------- Subpágina 2: Reportes e historial ----------
function SubReportes() {
  const [historial, setHistorial] = useState(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  async function cargar() {
    setCargando(true); setError("");
    try {
      const permiso = await sriPermiso("SRI historial");
      const r = await sriHistorial(permiso.url, permiso.token);
      setHistorial(r.historial || []);
    } catch (e) { setError(e?.message || "No se pudo cargar el historial."); }
    finally { setCargando(false); }
  }
  useEffect(() => { cargar(); }, []);

  const filas = Array.isArray(historial) ? historial : [];
  return (
    <section className="ma-tarjeta ma-sri-tabla-bloque">
      <div className="ma-sri-descarga-cab">
        <h3>Reportes e historial</h3>
        <span>Descargas registradas en el servidor. Los archivos de cada descarga se bajan desde la pestaña «Descarga» (botón ZIP) al terminar.</span>
      </div>
      <div className="ma-sri-descarga-acciones">
        <button type="button" className="ma-boton" onClick={cargar} disabled={cargando}>{cargando ? "Cargando…" : "Actualizar historial"}</button>
      </div>
      {error && <div className="ma-sri-resultado ma-sri-resultado-error">{error}</div>}
      {filas.length === 0 && !cargando && !error && <p className="ma-sri-tabla-nota">Sin descargas registradas todavía.</p>}
      {filas.length > 0 && (
        <div className="ma-tabla-wrap">
          <table className="ma-tabla ma-sri-tabla">
            <thead><tr><th>Fecha</th><th>RUC</th><th>Origen</th><th>Período</th><th>Tipo</th><th>Resultado</th></tr></thead>
            <tbody>
              {filas.map((h, i) => (
                <tr key={i}>
                  <td>{h.fecha || h.timestamp || "—"}</td>
                  <td className="ma-sri-tabla-form">{h.ruc || "—"}</td>
                  <td>{h.origen || "—"}</td>
                  <td>{[h.anio, h.mes, h.dia].filter((x) => x || x === 0).join("/") || "—"}</td>
                  <td>{h.tipo || "—"}</td>
                  <td>{typeof h.resultado === "object" ? (h.resultado?.estado || "ok") : (h.resultado ?? "—")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// ---------- Subpágina 3: Consolidación de documentos ----------
function SubConsolidacion() {
  const [form, setForm] = useState({ ruc: "", origen: "Recibidos", tipo: "Todos", modo_fecha: "Rango de meses", anio: ANIO_ACTUAL, mes_inicio: 1, mes_fin: 12, incluir_xml: true, incluir_pdf: true });
  const [estado, setEstado] = useState("idle");
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState("");
  const set = (k) => (e) => { const v = e.target.type === "checkbox" ? e.target.checked : e.target.value; setForm((f) => ({ ...f, [k]: v })); };

  async function consolidar() {
    setError(""); setResultado(null);
    if (!/^\d{13}$/.test(form.ruc.trim())) { setError("El RUC debe tener 13 dígitos."); return; }
    setEstado("procesando");
    try {
      const permiso = await sriPermiso(`SRI consolidar ${form.ruc.trim()}`);
      const r = await sriConsolidar(permiso.url, permiso.token, {
        carpeta_base: `descargas/${form.ruc.trim()}`, origen: form.origen, ruc: form.ruc.trim(),
        tipo: form.tipo, modo_fecha: form.modo_fecha, anio: Number(form.anio),
        mes_inicio: Number(form.mes_inicio), mes_fin: Number(form.mes_fin),
        incluir_xml: form.incluir_xml, incluir_pdf: form.incluir_pdf,
      });
      setResultado(r); setEstado("listo");
    } catch (e) { setError(e?.message || "No se pudo consolidar."); setEstado("error"); }
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
        <label>Tipo<select value={form.tipo} onChange={set("tipo")}>{TIPOS.map((t) => <option key={t}>{t}</option>)}</select></label>
        <label>Año<select value={form.anio} onChange={set("anio")}>{ANIOS.map((a) => <option key={a} value={a}>{a}</option>)}</select></label>
        <label>Mes inicio<select value={form.mes_inicio} onChange={set("mes_inicio")}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
        <label>Mes fin<select value={form.mes_fin} onChange={set("mes_fin")}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
        <label className="ma-sri-check">Incluir<span className="ma-sri-check-fila">
          <label><input type="checkbox" checked={form.incluir_xml} onChange={set("incluir_xml")} /> XML</label>
          <label><input type="checkbox" checked={form.incluir_pdf} onChange={set("incluir_pdf")} /> PDF</label>
        </span></label>
      </div>
      <div className="ma-sri-descarga-acciones">
        <button type="button" className="ma-sri-boton-ejecutar" onClick={consolidar} disabled={estado === "procesando"}>{estado === "procesando" ? "Consolidando…" : "Consolidar"}</button>
      </div>
      {estado === "listo" && <div className="ma-sri-resultado ma-sri-resultado-ok"><ResumenResultado r={resultado} titulo="✅ Consolidación lista" /></div>}
      {error && <div className="ma-sri-resultado ma-sri-resultado-error">{error}</div>}
    </section>
  );
}

// ---------- Subpágina 4: Ayuda + alcance ----------
const FUENTES = [
  { nombre: "Robot del SRI", texto: "Descarga los comprobantes electrónicos emitidos y recibidos, incluidas las retenciones.", formatos: ["XML", "PDF"] },
  { nombre: "Declaraciones", texto: "Formularios presentados en el período, originales y sustitutivas.", formatos: ["PDF", "XML"] },
  { nombre: "Anexos tributarios", texto: "ATS, RDEP, dividendos, accionistas, partes relacionadas y demás.", formatos: ["XML", "Excel"] },
  { nombre: "Contabilidad del cliente", texto: "Mayor o diario, auxiliares de ventas y compras, nómina y maestros.", formatos: ["Excel", "CSV"] },
];
function SubAyuda() {
  return (
    <section className="ma-sri-ayuda">
      <section className="ma-tarjeta">
        <h3>Cómo usar el robot del SRI</h3>
        <ol className="ma-sri-ayuda-lista">
          <li><strong>Descarga:</strong> pon el RUC y la clave del SRI del cliente, elige el período y los formatos, y pulsa «Descargar». Si el SRI muestra un captcha, aparecerá aquí para que lo escribas. Al terminar, baja los archivos con «Descargar archivos (ZIP)».</li>
          <li><strong>Reportes e historial:</strong> revisa las descargas ya realizadas.</li>
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
      {sub === "reportes" && <SubReportes />}
      {sub === "consolidacion" && <SubConsolidacion />}
      {sub === "ayuda" && <SubAyuda />}
    </section>
  );
}
