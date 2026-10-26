import { useState } from "react";
import MotorIngestaTool from "./MotorIngestaTool.jsx";
import CapaMapeoTool from "./CapaMapeoTool.jsx";
import ExtractorNarrativoTool from "./ExtractorNarrativoTool.jsx";
import ResolutorSemanticoTool from "./ResolutorSemanticoTool.jsx";
import { cargarMasiva, consultarMasiva } from "./api.js";
import "./ingesta.css";

const TABS = [
  ["masiva", "Carga masiva de mayores"],
  ["general", "Clasificación y normalización"],
  ["mapeo", "Mapeo de columnas"],
  ["narrativo", "Documentos narrativos"],
  ["resolver", "Revisión semántica"],
];

function CargaMasiva() {
  const [archivo, setArchivo] = useState(null);
  const [cliente, setCliente] = useState("");
  const [encargo, setEncargo] = useState("");
  const [periodo, setPeriodo] = useState("");
  const [mapeo, setMapeo] = useState('{"cuenta":0,"fecha":1,"debe":2,"haber":3}');
  const [formato, setFormato] = useState("secciones");
  const [resultado, setResultado] = useState(null);
  const [filas, setFilas] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function ejecutar(e) {
    e.preventDefault();
    if (!archivo || busy) return;
    setBusy(true); setError(""); setResultado(null); setFilas([]);
    try {
      const confirmado = JSON.parse(mapeo);
      const r = await cargarMasiva(archivo, {
        cliente_id: cliente.trim(), encargo_id: encargo.trim(),
        periodo: periodo.trim(), tipo_documento: "mayor",
        mapeo_confirmado: confirmado, formato_mayor: formato,
      });
      setResultado(r);
      const pagina = await consultarMasiva(r.dataset_id, cliente.trim(), encargo.trim(), 20);
      setFilas(pagina.filas || []);
    } catch (err) {
      setError(err.message || "Error en carga masiva");
    } finally { setBusy(false); }
  }
  return (
    <section className="ing-form" aria-label="Carga masiva">
      <h3>Mayor contable · carga incremental</h3>
      <p className="muted">Seleccione un archivo CSV o XLSX de su equipo. Los movimientos se procesan por lotes y se consultan paginados. No equivale a sincronizar SharePoint.</p>
      <form onSubmit={ejecutar}>
        <div className="ing-row">
          <label>Cliente / RUC <input required value={cliente} maxLength={128} onChange={e => setCliente(e.target.value)} /></label>
          <label>Encargo <input required value={encargo} maxLength={128} onChange={e => setEncargo(e.target.value)} /></label>
          <label>Período <input required value={periodo} maxLength={128} onChange={e => setPeriodo(e.target.value)} placeholder="2026" /></label>
        </div>
        <div className="ing-row">
          <label>Formato de mayor
            <select value={formato} onChange={e => setFormato(e.target.value)}>
              <option value="secciones">Mayor detallado por cuenta (MANACRIPEX)</option>
              <option value="tabular">Tabla plana CSV/XLSX</option>
            </select>
          </label>
          <label>Mayor CSV/XLSX <input type="file" required accept=".csv,.xlsx" onChange={e => setArchivo(e.target.files?.[0] || null)} /></label>
          <label>Mapeo confirmado (campo: índice de columna) <textarea required value={mapeo} rows={3} onChange={e => setMapeo(e.target.value)} /></label>
        </div>
        <p className="muted">Antes de cargar, utilice la pestaña «Mapeo de columnas» para verificar el formato del archivo. Esta carga usa exclusivamente el mapeo que usted confirma.</p>
        <button className="btn" type="submit" disabled={busy || !archivo}>{busy ? "Procesando…" : "Cargar mayor y registrar población"}</button>
      </form>
      <details><summary>Archivo desde SharePoint</summary><p role="status">La selección directa todavía no está habilitada: requiere un conector autenticado en el servidor y autorización por expediente. No introduzca enlaces privados ni tokens aquí.</p></details>
      {error && <p className="nf-error" role="alert">{error}</p>}
      {resultado && <div className="ing-card" role="status">
        <h4>Población registrada</h4>
        <p>ID: <code>{resultado.dataset_id}</code></p>
        <p>Estado: {resultado.estado} · Movimientos: {resultado.total_filas} · Con excepciones: {resultado.filas_revision}</p>
        {resultado.control_mayor && <p>Control del reporte: {resultado.control_mayor.cuentas} cuentas · Debe {resultado.control_mayor.debe} · Haber {resultado.control_mayor.haber} · Conciliado: {resultado.control_mayor.cuadra_reporte ? "Sí" : "No"}</p>}
      </div>}
      {filas.length > 0 && <details><summary>Primeros {filas.length} movimientos (consulta paginada)</summary><pre style={{overflowX:"auto"}}>{JSON.stringify(filas, null, 2)}</pre></details>}
    </section>
  );
}

export default function IngestaUnificadaTool({ initialTab = "masiva" }) {
  const [tab, setTab] = useState(initialTab);
  return <section className="ing-tool">
    <header className="ing-head"><h2>Motor de Ingesta · Centro de trabajo</h2><p>Una sola pantalla para clasificación, mapeo, carga masiva y revisión.</p></header>
    <nav aria-label="Funciones del Motor de Ingesta" className="ing-row" style={{flexWrap:"wrap",gap:8}}>
      {TABS.map(([id,label]) => <button type="button" key={id} className={id === tab ? "btn" : "btn secondary"} aria-current={id === tab ? "page" : undefined} onClick={() => setTab(id)}>{label}</button>)}
    </nav>
    {tab === "masiva" && <CargaMasiva />}
    {tab === "general" && <MotorIngestaTool />}
    {tab === "mapeo" && <CapaMapeoTool />}
    {tab === "narrativo" && <ExtractorNarrativoTool />}
    {tab === "resolver" && <ResolutorSemanticoTool />}
  </section>;
}
