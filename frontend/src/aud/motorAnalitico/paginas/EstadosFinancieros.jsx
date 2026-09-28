import { useState } from "react";
import { PAGINAS } from "../paginas.js";
import {
  motorBalancesHomologar, motorBalancesAnalisis, motorBalancesAnalisisPapel,
} from "../../../api.js";
import "./EstadosFinancieros.css";

const META = PAGINAS.find((p) => p.id === "estados");

const money = (v) => Number(v || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (v) => (v === null || v === undefined || v === "" ? "—" : `${(Number(v) * 100).toFixed(2)} %`);
const veces = (v) => (v === null || v === undefined || v === "" ? "—" : Number(v).toFixed(2));
const fmtRatio = (fila, v) => (fila.formato === "pct" ? pct(v) : veces(v));

export default function EstadosFinancieros({ ir }) {
  const [archivos, setArchivos] = useState([]);
  const [esf, setEsf] = useState(null);
  const [eri, setEri] = useState(null);
  const [analisis, setAnalisis] = useState(null);
  const [errores, setErrores] = useState([]);
  const [estado, setEstado] = useState("esf"); // pestaña ESF/ERI
  const [cargando, setCargando] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const analizar = async () => {
    setErrorMsg(""); setErrores([]); setAnalisis(null); setCargando(true);
    try {
      const hom = await motorBalancesHomologar(archivos);
      setErrores(hom.errores || []);
      const res = await motorBalancesAnalisis(hom.esf, hom.eri);
      setEsf(hom.esf); setEri(hom.eri); setAnalisis(res);
    } catch (e) {
      setErrorMsg(e?.message || "No se pudo analizar los estados.");
    } finally {
      setCargando(false);
    }
  };

  const descargarPapel = async () => {
    if (!esf || !eri) return;
    setDescargando(true); setErrorMsg("");
    try {
      const blob = await motorBalancesAnalisisPapel(esf, eri);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "papel-estados-financieros.xlsx"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErrorMsg(e?.message || "No se pudo generar el papel de trabajo.");
    } finally {
      setDescargando(false);
    }
  };

  const detalle = analisis ? analisis[estado] : null;
  const periodos = detalle?.periodos || [];
  const ratios = analisis?.ratios;
  const expect = analisis?.expectativa_esf;

  return (
    <section className="ma-pagina ma-estados-pagina">
      <div className="ma-estados-breadcrumb">
        <button type="button" className="ma-estados-link" onClick={() => ir("portada")}>
          Motor de Auditoría Analítica
        </button>
        <span className="ma-estados-sep">/</span>
        <span>Análisis de estados financieros</span>
      </div>

      <div className="ma-estados-encabezado">
        <h2>{META.titulo}</h2>
        <button type="button" className="ma-boton" onClick={() => ir("portada")}>← Volver a la portada</button>
      </div>
      <p className="ma-estados-intro">
        Análisis horizontal y vertical, ratios de la firma y expectativa vs. real (NIA 520) sobre los estados
        homologados del Motor de balances. Sube el balance de comprobación / los estados (uno o varios períodos,
        con la columna de homologación Super Cías cuando exista).
      </p>

      <div className="ma-estados-motor">
        <div className="ma-estados-subir">
          <input type="file" multiple accept=".xlsx,.xlsm,.csv" disabled={cargando}
                 onChange={(e) => setArchivos(Array.from(e.target.files || []))} />
          <button className="ma-boton accent" disabled={cargando || archivos.length === 0} onClick={analizar}>
            {cargando ? "Analizando…" : "Homologar y analizar"}
          </button>
        </div>
        {errorMsg && <p className="ma-estados-error" role="alert">{errorMsg}</p>}
        {errores.length > 0 && (
          <div className="ma-estados-avisos" role="alert">
            {errores.map((e, i) => <div key={i}>No se pudo leer {e.archivo}: {e.error}</div>)}
          </div>
        )}
      </div>

      {analisis && (
        <>
          {/* Ratios */}
          <section className="ma-estados-bloque">
            <div className="ma-estados-titulo-fila">
              <h3>Ratios financieros</h3>
              <button className="ma-boton accent" disabled={descargando} onClick={descargarPapel}>
                {descargando ? "Generando…" : "Descargar papel de trabajo"}
              </button>
            </div>
            <div className="ma-tabla-wrap">
              <table className="ma-tabla">
                <thead><tr><th>Ratio</th>{(ratios?.periodos || []).map((p) => <th key={p}>{p}</th>)}</tr></thead>
                <tbody>
                  {(ratios?.filas || []).map((f) => (
                    <tr key={f.nombre}>
                      <td>{f.nombre}</td>
                      {f.valores.map((v, i) => <td key={i} className="ma-estados-num">{fmtRatio(f, v)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Horizontal / vertical */}
          <section className="ma-estados-bloque">
            <div className="ma-estados-titulo-fila">
              <h3>Análisis horizontal y vertical</h3>
              <div className="ma-estados-tabs">
                <button className={estado === "esf" ? "ma-estados-tab activa" : "ma-estados-tab"} onClick={() => setEstado("esf")}>ESF</button>
                <button className={estado === "eri" ? "ma-estados-tab activa" : "ma-estados-tab"} onClick={() => setEstado("eri")}>ERI</button>
              </div>
            </div>
            <div className="ma-tabla-wrap">
              <table className="ma-tabla">
                <thead>
                  <tr>
                    <th>Código</th><th>Rubro</th>
                    {periodos.map((p) => <th key={p}>{p}</th>)}
                    <th>Variación</th><th>Var %</th><th>Vertical %</th>
                  </tr>
                </thead>
                <tbody>
                  {(detalle?.lineas || []).map((l) => (
                    <tr key={l.codigo} className={l.codigo.length <= 1 ? "ma-estados-total" : ""}>
                      <td className="ma-estados-mono">{l.codigo}</td>
                      <td>{l.etiqueta}</td>
                      {l.valores.map((v, i) => <td key={i} className="ma-estados-num">{money(v)}</td>)}
                      <td className="ma-estados-num">{l.variacion !== undefined ? money(l.variacion) : "—"}</td>
                      <td className="ma-estados-num">{pct(l.variacion_pct)}</td>
                      <td className="ma-estados-num">{pct(l.vertical?.[l.vertical.length - 1])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* NIA 520 */}
          {expect?.aplicable && (
            <section className="ma-estados-bloque">
              <h3>Expectativa vs. real — NIA 520 <span className="ma-estados-sub">(umbral {pct(expect.umbral_pct)})</span></h3>
              <div className="ma-tabla-wrap">
                <table className="ma-tabla">
                  <thead><tr><th>Código</th><th>Rubro</th><th>Expectativa</th><th>Real</th><th>Diferencia</th><th>Dif %</th><th>¿Explicar?</th></tr></thead>
                  <tbody>
                    {expect.lineas.map((l) => (
                      <tr key={l.codigo} className={l.supera_umbral ? "ma-estados-alerta" : ""}>
                        <td className="ma-estados-mono">{l.codigo}</td>
                        <td>{l.etiqueta}</td>
                        <td className="ma-estados-num">{money(l.expectativa)}</td>
                        <td className="ma-estados-num">{money(l.real)}</td>
                        <td className="ma-estados-num">{money(l.diferencia)}</td>
                        <td className="ma-estados-num">{pct(l.diferencia_pct)}</td>
                        <td className="ma-estados-centro">{l.supera_umbral ? "Explicar" : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </section>
  );
}
