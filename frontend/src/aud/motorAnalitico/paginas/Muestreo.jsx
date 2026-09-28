import { useEffect, useRef, useState } from "react";
import { PAGINAS } from "../paginas.js";
import { mensajeError } from "../bandeja.js";
import "./Muestreo.css";

const META = PAGINAS.find((p) => p.id === "muestras");

// Bases del motor (por prefijo de cuenta; ver motor muestreo_servicio.PREFIJO_BASE).
const BASES = [
  { clave: "gastos", nombre: "Mayor de gastos", detalle: "Cuentas 5" },
  { clave: "ventas", nombre: "Ventas / ingresos", detalle: "Cuentas 4" },
  { clave: "costos", nombre: "Costos", detalle: "Cuentas 6" },
  { clave: "todo", nombre: "Todo el mayor", detalle: "Sin filtro de cuenta" },
];

// Métodos implementados en el motor (NIA 530).
const METODOS = [
  { id: "mus", titulo: "MUS (unidad monetaria)", texto: "Selección sistemática proporcional al importe, con arranque aleatorio reproducible.", criterio: "NIA 530 · error tolerable + confianza" },
  { id: "partidas_clave", titulo: "Partidas clave", texto: "Toda partida cuyo importe ≥ umbral entra al 100 %, fuera del muestreo.", criterio: "Importe ≥ umbral" },
  { id: "aleatorio", titulo: "Aleatorio simple", texto: "Selección sin reemplazo con igual probabilidad y semilla reproducible.", criterio: "Tamaño n · semilla" },
  { id: "sistematico", titulo: "Sistemático", texto: "Cada k-ésimo registro con arranque aleatorio sobre la población ordenada.", criterio: "Tamaño n · semilla" },
];

const CONFIANZAS = ["0.95", "0.90", "0.80", "0.99"];
const ORDEN_RESUMEN = [
  ["metodo", "Método"], ["tamano_poblacion", "Tamaño de la población"],
  ["valor_poblacion", "Valor de la población"], ["umbral", "Umbral"],
  ["confianza", "Confianza"], ["error_tolerable", "Error tolerable"],
  ["intervalo_muestreo", "Intervalo de muestreo"], ["arranque_aleatorio", "Arranque aleatorio"],
  ["semilla", "Semilla"], ["seleccion_cierta", "Selección cierta"],
  ["seleccion_sistematica", "Selección sistemática"], ["tamano_muestra", "Tamaño de la muestra"],
  ["valor_muestreado", "Valor muestreado"], ["cobertura", "Cobertura del valor"],
];

const elegir = (set) => (e) => set(e.target.files?.[0] || null);
const dinero = (t) => {
  const n = Number(t);
  return Number.isFinite(n) ? n.toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : t;
};
const valorResumen = (clave, v) => {
  if (clave === "cobertura") return `${(Number(v) * 100).toFixed(2)} %`;
  if (["valor_poblacion", "valor_muestreado", "error_tolerable", "umbral", "intervalo_muestreo", "arranque_aleatorio"].includes(clave)) return dinero(v);
  return String(v);
};

export default function Muestreo({ ir, cliente, disponible }) {
  const [archivo, setArchivo] = useState(null);
  const [base, setBase] = useState("gastos");
  const [metodo, setMetodo] = useState("mus");
  const [semilla, setSemilla] = useState("20260101");
  const [errorTolerable, setErrorTolerable] = useState("");
  const [confianza, setConfianza] = useState("0.95");
  const [umbral, setUmbral] = useState("");
  const [tamano, setTamano] = useState("60");
  const [resultado, setResultado] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const montado = useRef(true);
  useEffect(() => () => { montado.current = false; }, []);
  useEffect(() => { setResultado(null); }, [cliente]);

  const parametros = () => {
    const p = { base, semilla: Number(semilla) };
    if (metodo === "mus") { p.error_tolerable = errorTolerable; p.confianza = Number(confianza); }
    if (metodo === "partidas_clave") { p.umbral = umbral; delete p.semilla; }
    if (metodo === "aleatorio" || metodo === "sistematico") p.tamano = Number(tamano);
    return p;
  };

  const faltaParametro = (
    !archivo ||
    (metodo === "mus" && (!errorTolerable || !semilla)) ||
    (metodo === "partidas_clave" && !umbral) ||
    ((metodo === "aleatorio" || metodo === "sistematico") && (!tamano || !semilla))
  );

  const seleccionar = async () => {
    setErrorMsg("");
    setCargando(true);
    setResultado(null);
    try {
      const r = await cliente.muestreo(archivo, metodo, parametros());
      if (montado.current) setResultado(r);
    } catch (e) {
      if (montado.current) setErrorMsg(mensajeError(e));
    } finally {
      if (montado.current) setCargando(false);
    }
  };

  const descargarPapel = async () => {
    setErrorMsg("");
    setDescargando(true);
    try {
      const blob = await cliente.papelMuestreo(archivo, metodo, parametros());
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `papel-muestreo-${metodo}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErrorMsg(mensajeError(e));
    } finally {
      if (montado.current) setDescargando(false);
    }
  };

  const abrirHtml = async () => {
    setErrorMsg("");
    try {
      const blob = await cliente.papelMuestreo(archivo, metodo, parametros(), "html");
      window.open(URL.createObjectURL(new Blob([blob], { type: "text/html" })), "_blank");
    } catch (e) {
      setErrorMsg(mensajeError(e));
    }
  };

  const resumen = resultado?.resumen || {};
  const seleccion = resultado?.seleccion || [];

  return (
    <section className="ma-pagina ma-muestras">
      <div className="ma-muestras-breadcrumb">
        <button type="button" className="ma-muestras-link" onClick={() => ir("portada")}>
          Motor de Auditoría Analítica
        </button>
        <span> / </span>
        <span>Selección de muestras</span>
      </div>

      <div className="ma-muestras-encabezado">
        <div className="ma-muestras-titulo">
          <h2>Selección de muestras</h2>
          <p>
            Combina partidas clave, muestreo estadístico y MUS sobre el mayor del cliente. Todo queda
            documentado con semilla y cobertura (NIA 530). Los valores atípicos (GAS-006) y la selección
            dirigida por criterios están en «Bases de datos».
          </p>
        </div>
        <button type="button" className="ma-boton" onClick={() => ir("portada")}>
          ← Volver a la portada
        </button>
      </div>

      <div className="ma-grid ma-muestras-cols2">
        <section aria-label="Base y archivo" className="ma-tarjeta ma-muestras-seccion">
          <h3>1 · Qué quieres muestrear</h3>
          <div className="ma-muestras-fuentes">
            {BASES.map((f) => (
              <button type="button" key={f.clave}
                      aria-pressed={f.clave === base}
                      className={f.clave === base ? "ma-muestras-fuente activa" : "ma-muestras-fuente"}
                      onClick={() => setBase(f.clave)}>
                <span className="ma-muestras-fuente-nombre">{f.nombre}</span>
                <span className="ma-muestras-fuente-detalle">{f.detalle}</span>
              </button>
            ))}
          </div>
          <label className="ma-muestras-archivo">
            Mayor del cliente (.xlsx, .xlsm, .csv)
            <input type="file" accept=".xlsx,.xlsm,.csv" disabled={!disponible || cargando}
                   onChange={elegir(setArchivo)} />
          </label>
          <span className="ma-muestras-nota">Solo datos anonimizados hasta SP4.</span>
        </section>

        <section aria-label="Parámetros" className="ma-tarjeta ma-muestras-seccion">
          <h3>2 · Parámetros del encargo</h3>
          <div className="ma-muestras-parametros">
            {metodo === "mus" && (
              <>
                <label>
                  Error tolerable (USD)
                  <input type="text" inputMode="decimal" placeholder="≤ materialidad de ejecución"
                         value={errorTolerable} onChange={(e) => setErrorTolerable(e.target.value)} />
                </label>
                <label>
                  Nivel de confianza
                  <select value={confianza} onChange={(e) => setConfianza(e.target.value)}>
                    {CONFIANZAS.map((c) => <option key={c} value={c}>{(Number(c) * 100).toFixed(0)} %</option>)}
                  </select>
                </label>
              </>
            )}
            {metodo === "partidas_clave" && (
              <label>
                Umbral (USD)
                <input type="text" inputMode="decimal" placeholder="p. ej. materialidad de ejecución"
                       value={umbral} onChange={(e) => setUmbral(e.target.value)} />
              </label>
            )}
            {(metodo === "aleatorio" || metodo === "sistematico") && (
              <label>
                Tamaño de la muestra (n)
                <input type="text" inputMode="numeric" value={tamano} onChange={(e) => setTamano(e.target.value)} />
              </label>
            )}
            {metodo !== "partidas_clave" && (
              <label>
                Semilla (obligatoria)
                <input type="text" inputMode="numeric" placeholder="p. ej. fecha del encargo"
                       value={semilla} onChange={(e) => setSemilla(e.target.value)} />
              </label>
            )}
          </div>
        </section>
      </div>

      <section aria-label="Métodos" className="ma-tarjeta ma-muestras-seccion">
        <div className="ma-muestras-titulo-fila">
          <h3>3 · Método de selección</h3>
          <span className="ma-muestras-nota">NIA 530 — la semilla queda en el papel de trabajo</span>
        </div>
        <div className="ma-grid ma-muestras-metodos">
          {METODOS.map((m) => (
            <label key={m.id} className={m.id === metodo ? "ma-tarjeta ma-muestras-metodo activa" : "ma-tarjeta ma-muestras-metodo"}>
              <div className="ma-muestras-metodo-fila">
                <input type="radio" name="metodo" checked={m.id === metodo} onChange={() => setMetodo(m.id)} />
                <span className="ma-muestras-metodo-titulo">{m.titulo}</span>
              </div>
              <span className="ma-muestras-metodo-texto">{m.texto}</span>
              <span className="ma-muestras-metodo-criterio">{m.criterio}</span>
            </label>
          ))}
        </div>
        <div className="ma-muestras-titulo-fila">
          {errorMsg && <span className="ma-muestras-error" role="alert">{errorMsg}</span>}
          <button type="button" className="ma-boton ma-muestras-cta accent"
                  disabled={!disponible || cargando || faltaParametro} onClick={seleccionar}>
            {cargando ? "Seleccionando…" : "Seleccionar muestra"}
          </button>
        </div>
      </section>

      {resultado && (
        <>
          <section aria-label="Método aplicado" className="ma-tarjeta ma-muestras-seccion">
            <div className="ma-muestras-titulo-fila">
              <h3>Bloque metodológico</h3>
              <button type="button" className="ma-boton accent" disabled={descargando} onClick={descargarPapel}>
                {descargando ? "Generando…" : "Descargar papel (Excel)"}
              </button>
              <button type="button" className="ma-boton" onClick={abrirHtml}>Abrir HTML / PDF</button>
            </div>
            <div className="ma-muestras-demo">
              {ORDEN_RESUMEN.filter(([k]) => resumen[k] !== undefined).map(([k, etiqueta]) => (
                <div className="ma-muestras-demo-campo" key={k}>
                  <span className="ma-muestras-nota">{etiqueta}</span>
                  <span>{valorResumen(k, resumen[k])}</span>
                </div>
              ))}
            </div>
          </section>

          <section aria-label="Cédula de selección" className="ma-tarjeta ma-muestras-seccion ma-muestras-cedula">
            <div className="ma-muestras-titulo-fila">
              <h3>Cédula de selección ({seleccion.length})</h3>
            </div>
            <div className="ma-tabla-wrap">
              <table className="ma-tabla">
                <thead>
                  <tr>
                    <th scope="col">N.º</th><th scope="col">Cuenta</th><th scope="col">Asiento</th>
                    <th scope="col">Fecha</th><th scope="col">Descripción</th>
                    <th scope="col">Importe</th><th scope="col">Marca</th>
                  </tr>
                </thead>
                <tbody>
                  {seleccion.length === 0 ? (
                    <tr><td colSpan={7} className="ma-sindatos">Sin partidas seleccionadas.</td></tr>
                  ) : (
                    seleccion.slice(0, 500).map((f, i) => (
                      <tr key={i}>
                        <td>{i + 1}</td><td>{f.cuenta}</td><td>{f.asiento}</td><td>{f.fecha}</td>
                        <td>{f.descripcion}</td>
                        <td className="ma-muestras-monto">{dinero(f.importe)}</td>
                        <td>{f.marca}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {seleccion.length > 500 && (
              <span className="ma-muestras-nota">Se muestran las primeras 500; el papel de trabajo trae las {seleccion.length}.</span>
            )}
          </section>
        </>
      )}

      <section aria-label="Evaluación" className="ma-tarjeta ma-muestras-seccion ma-muestras-evaluacion">
        <div>
          <h3>Evaluación de la muestra</h3>
          <p>
            Con los errores encontrados en cada partida, el motor calcula el límite superior de error contra el
            tolerable (precisión básica + error proyectado + margen incremental). Las subvaloraciones se informan
            aparte. La conclusión es del auditor.
          </p>
        </div>
      </section>
    </section>
  );
}
