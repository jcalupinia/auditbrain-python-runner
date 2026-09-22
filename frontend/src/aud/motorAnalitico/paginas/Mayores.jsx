import { Fragment, useEffect, useRef, useState } from "react";
import { PAGINAS } from "../paginas.js";
import { ErrorMotor, SONDEO_MS } from "../clienteMotor.js";
import { SEVERIDADES, dinero, paginas as totalPaginas, resumenSeveridad, terminado } from "../bandeja.js";
import "./Mayores.css";

// Transcripción de Mayores.dc.html: bloque «Pruebas de asientos» (5 bloques
// del lienzo → encabezado + 4 secciones). Solo «Pruebas de asientos» es
// operativa (Task 3); «Asientos manuales», «Explorador» y «Buscar concepto»
// quedan en construcción (SP7), con sus cifras de ejemplo como «sin datos».

const META = PAGINAS.find((p) => p.id === "mayores");
const TAM_PAGINA = 50;

// Nombres de pruebas y reglas: contenido normativo del lienzo, no cifras de
// demostración — se conservan tal cual (regla de conversión #4).
const PRUEBAS_ASIENTOS = [
  { id: "AST-001", nombre: "Asiento manual contra cuenta de ingreso" },
  { id: "AST-002", nombre: "Asiento en fin de semana o feriado" },
  { id: "AST-003", nombre: "Asiento registrado fuera de horario" },
  { id: "AST-004", nombre: "Asiento de cierre registrado tarde" },
  { id: "AST-005", nombre: "Asiento reversado en el período siguiente" },
  { id: "AST-006", nombre: "Asiento contra cuenta de uso infrecuente" },
  { id: "AST-007", nombre: "Asiento sin glosa o con glosa genérica" },
  { id: "AST-008", nombre: "Comprobante contable descuadrado" },
];

const PROCESOS_MANUALES = ["Ventas", "Compras", "Nómina", "Tesorería", "Cierre"];
const CUENTAS_MATRIZ = ["Ingresos (4)", "Costo de ventas", "Gastos (5)", "Caja y bancos", "Provisiones y estimaciones"];
const MESES = ["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
const CUENTAS_EXPLORADOR = ["Ingresos", "Cuenta puente", "Gastos adm.", "Provisiones", "Proveedores"];
const AGRUPACIONES = ["Por cuenta contable", "Por mes", "Por usuario que registró"];

const ESTADO_TEXTO = { en_cola: "En cola", procesando: "Procesando", listo: "Listo", error: "Con errores" };

function mensajeError(e) {
  if (e?.name === "AbortError") return "El motor no respondió a tiempo.";
  if (e instanceof ErrorMotor && e.estado === 429) return "Ya tienes 3 trabajos en curso: espera a que terminen.";
  return e?.message || "Error al comunicarse con el motor.";
}

export default function Mayores({ ir, cliente, disponible, EnConstruccion }) {
  const [archivo, setArchivo] = useState(null);
  const [trabajo, setTrabajo] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [cargando, setCargando] = useState(false);
  const [filtros, setFiltros] = useState({ severidad: "", regla: "", texto: "" });
  const [pagina, setPagina] = useState(1);
  const [excepciones, setExcepciones] = useState({ items: [], total: 0 });
  const [seleccion, setSeleccion] = useState(null);
  const intervaloRef = useRef(null);

  // Sondeo del trabajo hasta que termine (SONDEO_MS: el motor admite 30 peticiones/min).
  useEffect(() => {
    clearInterval(intervaloRef.current);
    if (!trabajo?.id || terminado(trabajo.estado)) return undefined;
    intervaloRef.current = setInterval(async () => {
      try {
        setTrabajo(await cliente.trabajo(trabajo.id));
      } catch (e) {
        setErrorMsg(mensajeError(e));
      }
    }, SONDEO_MS);
    return () => clearInterval(intervaloRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trabajo?.id, trabajo?.estado, cliente]);

  // Excepciones cuando el trabajo está listo, o al cambiar filtros/página.
  useEffect(() => {
    if (trabajo?.estado !== "listo") return;
    cliente.excepciones(trabajo.id, { ...filtros, pagina, tam: TAM_PAGINA })
      .then(setExcepciones)
      .catch((e) => setErrorMsg(mensajeError(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trabajo?.estado, trabajo?.id, filtros, pagina, cliente]);

  const iniciar = async (accion) => {
    setErrorMsg("");
    setCargando(true);
    setSeleccion(null);
    try {
      setTrabajo(await accion());
      setFiltros({ severidad: "", regla: "", texto: "" });
      setPagina(1);
    } catch (e) {
      setErrorMsg(mensajeError(e));
    } finally {
      setCargando(false);
    }
  };

  const descargarPlantilla = async () => {
    setErrorMsg("");
    try {
      const blob = await cliente.plantilla();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "plantilla-motor-analitico.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErrorMsg(mensajeError(e));
    }
  };

  const cambiarFiltro = (campo, valor) => {
    setFiltros((f) => ({ ...f, [campo]: valor }));
    setPagina(1);
  };

  const copiarHash = (hash) => {
    try { navigator.clipboard.writeText(hash); } catch { /* sin portapapeles en este contexto */ }
  };

  const totalPag = totalPaginas(excepciones.total, TAM_PAGINA);

  return (
    <section className="ma-pagina ma-mayores">
      <div className="ma-mayores-crumb">
        <button className="link" onClick={() => ir("portada")}>Motor de Auditoría Analítica</button>
        <span> / </span>
        <span>Análisis de mayores y diarios</span>
      </div>
      <div className="ma-mayores-head">
        <h2>{META.titulo}</h2>
        <button className="ma-boton" onClick={() => ir("portada")}>← Volver a la portada</button>
      </div>
      <nav className="ma-mayores-subnav" aria-label="Secciones de mayores y diarios">
        <a href="#ma-pruebas">Pruebas de asientos</a>
        <a href="#ma-manuales">Asientos manuales</a>
        <a href="#ma-explorador">Explorador</a>
        <a href="#ma-concepto">Buscar concepto</a>
      </nav>

      {/* Bloque 1: Pruebas de asientos · NIA 240 párr. 32(a) — operativo */}
      <section id="ma-pruebas" aria-label="Pruebas de asientos" className="ma-mayores-seccion">
        <div className="ma-mayores-titulo">
          <h3>Pruebas de asientos · NIA 240 párr. 32(a)</h3>
          <span className={`ma-mayores-badge ${disponible ? "ok" : "warn"}`}>
            {disponible ? "Disponible" : "Sin conexión"}
          </span>
        </div>
        <div className="ma-grid">
          {PRUEBAS_ASIENTOS.map((p) => (
            <div key={p.id} className="ma-tarjeta">
              <span className="ma-mayores-mono">{p.id}</span>
              <span>{p.nombre}</span>
            </div>
          ))}
        </div>

        <div className="ma-mayores-motor">
          <h4>Correr el motor</h4>
          {!disponible && <p className="ma-mayores-hint">Revisa la conexión arriba.</p>}
          <div className="ma-mayores-acciones">
            <button className="ma-boton accent" disabled={!disponible || cargando}
                    onClick={() => iniciar(() => cliente.crearDemo())}>
              Correr demo sintético
            </button>
            <button className="ma-boton" disabled={!disponible || cargando} onClick={descargarPlantilla}>
              Descargar plantilla
            </button>
            <div className="ma-mayores-subir">
              <input type="file" accept=".xlsx" disabled={!disponible || cargando}
                     onChange={(e) => setArchivo(e.target.files?.[0] || null)} />
              <button className="ma-boton" disabled={!disponible || cargando || !archivo}
                      onClick={() => iniciar(() => cliente.crearConArchivo(archivo))}>
                Subir y correr
              </button>
            </div>
          </div>
          <span className="ma-mayores-aviso">Solo datos anonimizados hasta SP4.</span>

          {errorMsg && <p className="ma-mayores-error">{errorMsg}</p>}

          {trabajo && (
            <div className="ma-mayores-trabajo">
              <span>Estado: <strong>{ESTADO_TEXTO[trabajo.estado] || trabajo.estado}</strong></span>
              {trabajo.origen && <span> · Origen: {trabajo.origen}</span>}
            </div>
          )}

          {trabajo?.estado === "error" && (
            <div className="ma-tabla-wrap">
              <table className="ma-tabla">
                <thead><tr><th>Hoja</th><th>Fila</th><th>Columna</th><th>Motivo</th></tr></thead>
                <tbody>
                  {(trabajo.errores || []).map((e, i) => (
                    <tr key={i}><td>{e.hoja}</td><td>{e.fila}</td><td>{e.columna}</td><td>{e.motivo}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {trabajo?.estado === "listo" && (
            <>
              <div className="ma-grid ma-mayores-resumen">
                {resumenSeveridad(trabajo.resumen).map(([sev, n]) => (
                  <div key={sev} className="ma-tarjeta">
                    <span className={`ma-sev-${sev}`}>{sev}</span>
                    <strong>{n}</strong>
                  </div>
                ))}
                <div className="ma-tarjeta"><span>Total</span><strong>{excepciones.total}</strong></div>
              </div>

              <div className="ma-mayores-filtros">
                <select value={filtros.severidad} onChange={(e) => cambiarFiltro("severidad", e.target.value)}>
                  <option value="">Todas</option>
                  {SEVERIDADES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <input placeholder="Regla" value={filtros.regla} onChange={(e) => cambiarFiltro("regla", e.target.value)} />
                <input placeholder="Buscar texto" value={filtros.texto} onChange={(e) => cambiarFiltro("texto", e.target.value)} />
              </div>

              <div className="ma-tabla-wrap">
                <table className="ma-tabla">
                  <thead>
                    <tr><th>Severidad</th><th>Regla</th><th>NIA</th><th>Entidad</th><th>Descripción</th><th>Monto</th></tr>
                  </thead>
                  <tbody>
                    {excepciones.items.map((e, i) => (
                      <tr key={e.id || i} onClick={() => setSeleccion(e)}>
                        <td><span className={`ma-sev-${e.severidad}`}>{e.severidad}</span></td>
                        <td>{e.regla}</td>
                        <td>{e.nia}</td>
                        <td>{e.entidad}</td>
                        <td>{e.descripcion}</td>
                        <td>{dinero(e.monto)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="ma-mayores-paginador">
                <button className="ma-boton" disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}>Anterior</button>
                <span>Página {pagina} de {totalPag}</span>
                <button className="ma-boton" disabled={pagina >= totalPag} onClick={() => setPagina((p) => p + 1)}>Siguiente</button>
              </div>

              {seleccion && (
                <div className="ma-mayores-detalle">
                  <h4>Detalle</h4>
                  <p>{seleccion.descripcion}</p>
                  {seleccion.reglas_concurrentes?.length > 0 && (
                    <p>Reglas concurrentes: {seleccion.reglas_concurrentes.join(", ")}</p>
                  )}
                  <pre>{JSON.stringify(seleccion.evidencia, null, 2)}</pre>
                  {seleccion.hash && (
                    <div className="ma-mayores-hash">
                      <span className="ma-mayores-mono">{seleccion.hash}</span>
                      <button className="ma-boton" onClick={() => copiarHash(seleccion.hash)}>Copiar</button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </section>

      {/* Bloque 2: Asientos manuales fuera de patrón — en construcción (SP7) */}
      <section id="ma-manuales" aria-label="Asientos manuales fuera de patrón" className="ma-mayores-seccion">
        <div className="ma-mayores-titulo">
          <h3>Asientos manuales fuera de patrón</h3>
          <span className="ma-mayores-badge warn">Falta tu criterio</span>
        </div>
        <EnConstruccion sp={META.sp}>
          Matriz de dónde un asiento manual es normal y dónde no. El auditor la define por encargo; el motor marca
          cada manual que caiga en una celda «no esperado».
        </EnConstruccion>
        <div className="ma-tabla-wrap">
          <table className="ma-tabla">
            <thead>
              <tr>
                <th>Grupo de cuentas</th>
                {PROCESOS_MANUALES.map((p) => <th key={p}>{p}</th>)}
              </tr>
            </thead>
            <tbody>
              {CUENTAS_MATRIZ.map((c) => (
                <tr key={c}>
                  <td>{c}</td>
                  {PROCESOS_MANUALES.map((p) => (
                    <td key={p}><span className="ma-sindatos">sin datos</span></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <span className="ma-mayores-nota">
          Ejemplo para discutir: los valores de la matriz los fija el auditor responsable.
        </span>
      </section>

      <div className="ma-mayores-cols">
        {/* Bloque 3: Explorador de mayores — en construcción (SP7) */}
        <section id="ma-explorador" aria-label="Explorador de mayores" className="ma-mayores-seccion">
          <div className="ma-mayores-titulo">
            <h3>Explorador de mayores</h3>
            <span className="ma-mayores-badge warn">Boceto · {META.sp}</span>
          </div>
          <EnConstruccion sp={META.sp} />
          <div className="ma-mayores-chips">
            <span className="ma-mayores-chip">Filas: <strong>Cuenta</strong></span>
            <span className="ma-mayores-chip">Columnas: <strong>Mes</strong></span>
            <span className="ma-mayores-chip">Filtro: <strong>Origen = manual</strong></span>
            <span className="ma-mayores-chip dashed">+ dimensión</span>
          </div>
          <div role="img" aria-label="Mapa de calor de asientos manuales por cuenta y mes" className="ma-mayores-calor">
            <span />
            {MESES.map((m, i) => <span key={i} className="ma-mayores-mes">{m}</span>)}
            {CUENTAS_EXPLORADOR.map((c) => (
              <Fragment key={c}>
                <span className="ma-mayores-calorcuenta">{c}</span>
                {MESES.map((_, i) => <span key={i} className="ma-sindatos ma-mayores-celda">·</span>)}
              </Fragment>
            ))}
          </div>
          <p className="ma-mayores-nota">Vista ilustrativa. Un clic en una celda baja al asiento y a su comprobante.</p>
        </section>

        {/* Bloque 4: Buscar un concepto en todo el diario — en construcción (SP7) */}
        <section id="ma-concepto" aria-label="Buscar un concepto" className="ma-mayores-seccion">
          <h3>Buscar un concepto en todo el diario</h3>
          <EnConstruccion sp={META.sp} />
          <label htmlFor="ma-concepto-q">Glosa, proveedor, RUC o palabra clave</label>
          <div className="ma-mayores-buscar">
            <input id="ma-concepto-q" type="search" placeholder="p. ej. anticipo, reverso, ajuste" disabled />
            <button className="ma-boton" disabled>Buscar</button>
          </div>
          <span className="ma-mayores-nota">
            Resultado agrupado por cuenta, mes y usuario, con los casos fuera del patrón resaltados.
          </span>
          <div className="ma-mayores-agrupaciones">
            {AGRUPACIONES.map((g) => (
              <div key={g} className="ma-mayores-agrupacion">
                <span>{g}</span>
                <span className="ma-sindatos">sin datos</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
