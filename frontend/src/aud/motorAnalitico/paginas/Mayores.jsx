import { Fragment, useEffect, useRef, useState } from "react";
import { PAGINAS } from "../paginas.js";
import { ErrorMotor, LIMITE_ARCHIVO_BYTES, SONDEO_MS, archivoDemasiadoGrande } from "../clienteMotor.js";
import { SEVERIDADES, filasBandeja, mensajeError, paginas as totalPaginas, resumenSeveridad, terminado } from "../bandeja.js";
import { CAMPOS, INICIALES, aEnvio, resumenErrores, validar } from "../parametrosEncargo.js";
import { ESTADOS, filasSuficiencia, resumenLectura } from "../suficiencia.js";
import "./Mayores.css";

// Transcripción de Mayores.dc.html: bloque «Pruebas de asientos» (5 bloques
// del lienzo → encabezado + 4 secciones). Solo «Pruebas de asientos» es
// operativa (Task 3); «Asientos manuales», «Explorador» y «Buscar concepto»
// quedan en construcción (SP7), con sus cifras de ejemplo como «sin datos».
//
// Contrato real del motor (motor-auditoria-analitica@sp2a-trabajos,
// servicio/trabajos.py y motor/nucleo.py::Excepcion.a_dict — ver bandeja.js):
// GET /trabajos/{id} → {id, estado, origen, creado, terminado, sha256, total, por_severidad, errores}
// GET /trabajos/{id}/excepciones → {total, pagina, tam, excepciones: [...]}

const META = PAGINAS.find((p) => p.id === "mayores");
const TAM_PAGINA = 50;
const DEBOUNCE_MS = 400;
const MAXLEN_REGLA = 20;
const MAXLEN_TEXTO = 100;

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
const TRABAJO_VENCIDO = "El trabajo ya no existe en el motor (vence a las 8 h o el motor se reinició): vuelve a correrlo.";

const FILTROS_VACIOS = { severidad: "", regla: "", texto: "" };
const LIMITE_MB = Math.round(LIMITE_ARCHIVO_BYTES / (1024 * 1024));

// ESTADOS (suficiencia.js) trae frases con espacios y tildes: se mapean a un
// sufijo de clase CSS estable en vez de derivarlo del texto.
const CLASE_ESTADO_SUFICIENCIA = {
  [ESTADOS.corrio]: "corrio",
  [ESTADOS.noCorrio]: "no-corrio",
  [ESTADOS.sinDatos]: "sin-datos",
};
const MAX_ASIENTOS_MOSTRADOS = 10;

// El armazón desmonta esta página al navegar a otra; el último trabajo se
// recuerda por cliente (cambia con el proyecto) para retomarlo al volver.
const ULTIMO_TRABAJO = new WeakMap();

export default function Mayores({ ir, cliente, disponible, EnConstruccion }) {
  const [archivo, setArchivo] = useState(null);
  const [parametros, setParametros] = useState(INICIALES);
  const [mayorArchivo, setMayorArchivo] = useState(null);
  const [balanceArchivo, setBalanceArchivo] = useState(null);
  const [trabajo, setTrabajo] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [cargando, setCargando] = useState(false);
  const [entrada, setEntrada] = useState({ regla: "", texto: "" }); // valores del input, sin debounce
  const [filtros, setFiltros] = useState(FILTROS_VACIOS);           // valores aplicados a la consulta
  const [pagina, setPagina] = useState(1);
  const [excepciones, setExcepciones] = useState({ total: 0, excepciones: [] });
  const [seleccion, setSeleccion] = useState(null);
  const secuenciaRef = useRef(0);

  // Al cambiar de cliente (otro proyecto/encargo) se reinicia todo el estado:
  // un trabajo del cliente anterior no debe seguir vivo en pantalla.
  useEffect(() => {
    setArchivo(null);
    setParametros(INICIALES);
    setMayorArchivo(null);
    setBalanceArchivo(null);
    setTrabajo(null);
    setErrorMsg("");
    setEntrada({ regla: "", texto: "" });
    setFiltros(FILTROS_VACIOS);
    setPagina(1);
    setExcepciones({ total: 0, excepciones: [] });
    setSeleccion(null);
    const id = ULTIMO_TRABAJO.get(cliente);
    if (id) {
      cliente.trabajo(id)
        .then((r) => setTrabajo((t) => t ?? r))
        .catch(() => ULTIMO_TRABAJO.delete(cliente));
    }
  }, [cliente]);

  // Sondeo del trabajo: setTimeout encadenado (no setInterval), agenda la
  // siguiente consulta solo cuando llega la respuesta. Descarta respuestas
  // de un trabajo que ya no es el activo (`t?.id === id`). Un 404 (vencido
  // a las 8 h, o el motor se reinició) detiene el sondeo y limpia el trabajo.
  useEffect(() => {
    if (!trabajo?.id || terminado(trabajo.estado)) return undefined;
    const id = trabajo.id;
    let vivo = true;
    let temporizador = null;

    async function sondear() {
      try {
        const r = await cliente.trabajo(id);
        if (!vivo) return;
        setTrabajo((t) => (t?.id === id ? r : t));
        if (!terminado(r.estado)) temporizador = setTimeout(sondear, SONDEO_MS);
      } catch (e) {
        if (!vivo) return;
        if (e instanceof ErrorMotor && e.estado === 404) {
          setTrabajo((t) => (t?.id === id ? null : t));
          ULTIMO_TRABAJO.delete(cliente);
          setErrorMsg(TRABAJO_VENCIDO);
          return;
        }
        setErrorMsg(mensajeError(e));
        temporizador = setTimeout(sondear, SONDEO_MS);
      }
    }

    temporizador = setTimeout(sondear, SONDEO_MS);
    return () => { vivo = false; clearTimeout(temporizador); };
  }, [trabajo?.id, trabajo?.estado, cliente]);

  // Debounce de regla/texto: 400 ms sin escribir antes de aplicar el filtro.
  useEffect(() => {
    const h = setTimeout(() => {
      setFiltros((f) => ({ ...f, regla: entrada.regla, texto: entrada.texto }));
      setPagina(1);
    }, DEBOUNCE_MS);
    return () => clearTimeout(h);
  }, [entrada.regla, entrada.texto]);

  // Excepciones cuando el trabajo está listo, o al cambiar filtros/página.
  // Contador de secuencia: descarta una respuesta vieja si ya se disparó
  // una consulta más nueva (filtro cambiado rápido, o cambio de página).
  useEffect(() => {
    if (trabajo?.estado !== "listo") return;
    const yo = ++secuenciaRef.current;
    cliente.excepciones(trabajo.id, { ...filtros, pagina, tam: TAM_PAGINA })
      .then((r) => { if (secuenciaRef.current === yo) setExcepciones(r); })
      .catch((e) => { if (secuenciaRef.current === yo) setErrorMsg(mensajeError(e)); });
  }, [trabajo?.estado, trabajo?.id, filtros, pagina, cliente]);

  const iniciar = async (accion) => {
    setErrorMsg("");
    setCargando(true);
    setSeleccion(null);
    try {
      const nuevo = await accion();
      ULTIMO_TRABAJO.set(cliente, nuevo.id);
      setTrabajo(nuevo);
      setEntrada({ regla: "", texto: "" });
      setFiltros(FILTROS_VACIOS);
      setPagina(1);
      setExcepciones({ total: 0, excepciones: [] });
    } catch (e) {
      setErrorMsg(mensajeError(e));
    } finally {
      setCargando(false);
    }
  };

  // Rechaza en el navegador un archivo de más de 50 MB (mismo límite del
  // motor, servicio/app.py::MAX_BYTES) antes de intentar subirlo: si se deja
  // pasar, la subida se corta a medio camino y el trabajo queda huérfano.
  const elegirArchivo = (setter) => (e) => {
    const f = e.target.files?.[0] || null;
    if (f && archivoDemasiadoGrande(f)) {
      setErrorMsg(`El archivo pesa más de ${LIMITE_MB} MB, el límite del motor: elige uno más pequeño.`);
      setter(null);
      e.target.value = "";
      return;
    }
    setter(f);
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
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (e) {
      setErrorMsg(mensajeError(e));
    }
  };

  const cambiarSeveridad = (valor) => {
    setFiltros((f) => ({ ...f, severidad: valor }));
    setPagina(1);
  };

  const copiarHash = (hash) => {
    try { navigator.clipboard.writeText(hash); } catch { /* sin portapapeles en este contexto */ }
  };

  const totalPag = totalPaginas(excepciones.total, TAM_PAGINA);
  const filas = filasBandeja(excepciones);

  // Parámetros del encargo: validación en el navegador en cada cambio
  // (Task 4, punto 1) y, aparte, los errores por campo que devuelva el
  // motor (forma {campo, motivo}) cuando el trabajo termina en error.
  const erroresParametros = validar(parametros);
  const erroresMotorPorCampo = {};
  const erroresLectura = [];
  if (trabajo?.estado === "error") {
    for (const e of trabajo.errores || []) {
      if (e.campo) erroresMotorPorCampo[e.campo] = e.motivo;
      else erroresLectura.push(e);
    }
  }
  const botonMayorDeshabilitado =
    !disponible || cargando || !mayorArchivo || Object.keys(erroresParametros).length > 0;

  // Un trabajo que falla por parámetros debe decir por qué: el resumen
  // (campo → motivo, incluido balance) vive fuera del <details> y lo abre
  // automáticamente si hay algo que revisar (validación local o del motor).
  const resumenCamposErrores = resumenErrores(erroresParametros, erroresMotorPorCampo, erroresMotorPorCampo.balance);
  const hayErroresParaRevisar = resumenCamposErrores.length > 0;

  const resumen = resumenLectura(trabajo?.lectura);
  const filasSufi = filasSuficiencia(trabajo?.suficiencia);
  const barreraAsientos = trabajo?.barreras?.asientos_descuadrados;
  const barreraCuadre = trabajo?.barreras?.cuadre_contra_balance;

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
              <input type="file" aria-label="Plantilla del motor (.xlsx)" accept=".xlsx" disabled={!disponible || cargando}
                     onChange={elegirArchivo(setArchivo)} />
              <button className="ma-boton" disabled={!disponible || cargando || !archivo}
                      onClick={() => iniciar(() => cliente.crearConArchivo(archivo))}>
                Subir y correr
              </button>
            </div>
          </div>
          <span className="ma-mayores-aviso">Solo datos anonimizados hasta SP4.</span>

          <div className="ma-mayores-mayor">
            <h4>Subir el mayor del cliente</h4>
            <p className="ma-mayores-nota-fija">
              Sin estos parámetros ninguna prueba corre: el motor no usa montos por defecto (NIA 320/450/530).
            </p>

            {hayErroresParaRevisar && (
              <div className="ma-mayores-resumen-errores" role="alert">
                <strong>Revisa estos campos:</strong>
                <ul>
                  {resumenCamposErrores.map((e) => (
                    <li key={e.campo}>{e.etiqueta}: {e.motivo}</li>
                  ))}
                </ul>
              </div>
            )}

            <details className="ma-mayores-parametros" open={hayErroresParaRevisar}>
              <summary>Parámetros del encargo</summary>
              <div className="ma-mayores-campos">
                {CAMPOS.map((campo) => {
                  const error = erroresParametros[campo.id] || erroresMotorPorCampo[campo.id];
                  const inputId = `ma-param-${campo.id}`;
                  return (
                    <div key={campo.id} className={`ma-mayores-campo${campo.tipo === "casilla" ? " casilla" : ""}`}>
                      {campo.tipo === "casilla" ? (
                        <label htmlFor={inputId}>
                          <input id={inputId} type="checkbox" checked={!!parametros[campo.id]}
                                 disabled={!disponible || cargando}
                                 onChange={(e) => setParametros((p) => ({ ...p, [campo.id]: e.target.checked }))} />
                          {campo.etiqueta}
                        </label>
                      ) : (
                        <>
                          <label htmlFor={inputId}>{campo.etiqueta}</label>
                          {campo.tipo === "opciones" ? (
                            <select id={inputId} value={parametros[campo.id]} disabled={!disponible || cargando}
                                    onChange={(e) => setParametros((p) => ({ ...p, [campo.id]: e.target.value }))}>
                              <option value="">—</option>
                              {campo.opciones.map((o) => <option key={o} value={o}>{o}</option>)}
                            </select>
                          ) : (
                            <input id={inputId} type={campo.tipo === "date" ? "date" : "text"}
                                   value={parametros[campo.id]} disabled={!disponible || cargando}
                                   placeholder={campo.tipo === "fechas" ? "2026-01-01, 2026-05-01" : undefined}
                                   onChange={(e) => setParametros((p) => ({ ...p, [campo.id]: e.target.value }))} />
                          )}
                        </>
                      )}
                      <span className="ma-mayores-norma">{campo.nia}</span>
                      {error && <span className="ma-mayores-campo-error">{error}</span>}
                    </div>
                  );
                })}
              </div>
            </details>

            <div className="ma-mayores-acciones">
              <label className="ma-mayores-campo-archivo">
                Mayor (.xlsx, .xlsm, .csv)
                <input type="file" aria-label="Mayor del cliente" accept=".xlsx,.xlsm,.csv"
                       disabled={!disponible || cargando}
                       onChange={elegirArchivo(setMayorArchivo)} />
              </label>
              <label className="ma-mayores-campo-archivo">
                Balance (opcional)
                <input type="file" aria-label="Balance del cliente" accept=".xlsx,.xlsm,.csv"
                       disabled={!disponible || cargando}
                       onChange={elegirArchivo(setBalanceArchivo)} />
                {erroresMotorPorCampo.balance && <span className="ma-mayores-campo-error">{erroresMotorPorCampo.balance}</span>}
              </label>
              <button className="ma-boton accent" disabled={botonMayorDeshabilitado}
                      onClick={() => iniciar(() => cliente.crearConMayor(mayorArchivo, aEnvio(parametros), balanceArchivo))}>
                Subir el mayor y correr
              </button>
            </div>
            <span className="ma-mayores-aviso">Solo datos anonimizados hasta SP4.</span>
          </div>

          {errorMsg && <p className="ma-mayores-error">{errorMsg}</p>}

          {trabajo && (
            <div className="ma-mayores-trabajo">
              <span>Estado: <strong>{ESTADO_TEXTO[trabajo.estado] || trabajo.estado}</strong></span>
              {trabajo.origen && <span> · Origen: {trabajo.origen}</span>}
            </div>
          )}

          {trabajo?.estado === "error" && erroresLectura.length > 0 && (
            <div className="ma-tabla-wrap">
              <table className="ma-tabla">
                <thead><tr><th>Hoja</th><th>Fila</th><th>Columna</th><th>Motivo</th></tr></thead>
                <tbody>
                  {erroresLectura.map((e, i) => (
                    <tr key={i}><td>{e.hoja}</td><td>{e.fila}</td><td>{e.columna}</td><td>{e.motivo}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {resumen && (
            <div className="ma-mayores-lectura">
              <h4>Lectura del archivo</h4>
              <ul className="ma-mayores-lectura-lista">
                <li>{resumen.filas}</li>
                <li>{resumen.cuentas}</li>
                {resumen.periodo && <li>Período: {resumen.periodo}</li>}
                {resumen.hojas && <li>Hojas leídas: {resumen.hojas}</li>}
                {resumen.columnas && <li>Columnas detectadas: {resumen.columnas}</li>}
                {resumen.vacias && <li>Columnas detectadas pero vacías: {resumen.vacias}</li>}
                {resumen.huella && <li className="ma-mayores-mono">Huella: {resumen.huella}</li>}
              </ul>
            </div>
          )}

          {trabajo?.suficiencia && (
            <div className="ma-mayores-suficiencia">
              <div className="ma-mayores-titulo">
                <h4>Suficiencia de la evidencia</h4>
                <span className="ma-mayores-badge">
                  {trabajo.suficiencia.estado} · {trabajo.suficiencia.disponibles} de{" "}
                  {trabajo.suficiencia.disponibles + trabajo.suficiencia.no_disponibles} pruebas disponibles
                </span>
              </div>
              <div className="ma-tabla-wrap">
                <table className="ma-tabla">
                  <thead><tr><th>Regla</th><th>Estado</th><th>Detalle</th></tr></thead>
                  <tbody>
                    {filasSufi.map((f) => (
                      <tr key={f.regla}>
                        <td className="ma-mayores-mono">{f.regla}</td>
                        <td>
                          <span className={`ma-mayores-suf ma-mayores-suf-${CLASE_ESTADO_SUFICIENCIA[f.estado]}`}>
                            {f.estado}
                          </span>
                        </td>
                        <td>{f.detalle}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <span className="ma-mayores-nota-fija">
                Una prueba que no corrió no significa que no haya excepciones.
              </span>
            </div>
          )}

          {barreraAsientos && !barreraAsientos.pasa && (
            <div className="ma-mayores-barrera">
              <strong>
                {barreraAsientos.total} asiento(s) descuadrado(s): las pruebas de asientos no corrieron.
              </strong>
              <ul>
                {barreraAsientos.asientos.slice(0, MAX_ASIENTOS_MOSTRADOS).map((a) => (
                  <li key={a.asiento_id}>Asiento {a.asiento_id}: diferencia {a.diferencia}</li>
                ))}
              </ul>
            </div>
          )}

          {barreraCuadre?.evaluada && (
            <div className={`ma-mayores-cuadre ${barreraCuadre.pasa ? "ok" : "warn"}`}>
              <strong>Cuadre contra el balance: diferencia total {barreraCuadre.diferencia_total}</strong>
              {barreraCuadre.diferencias.length > 0 && (
                <ul>
                  {barreraCuadre.diferencias.map((d) => (
                    <li key={d.cuenta}>
                      Cuenta {d.cuenta}: mayor {d.mayor} vs. balance {d.balance} (diferencia {d.diferencia})
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {trabajo?.estado === "listo" && (
            <>
              <div className="ma-grid ma-mayores-resumen">
                {resumenSeveridad(trabajo.por_severidad).map(([sev, n]) => (
                  <div key={sev} className="ma-tarjeta">
                    <span className={`ma-sev-${sev}`}>{sev}</span>
                    <strong>{n}</strong>
                  </div>
                ))}
                <div className="ma-tarjeta"><span>Total</span><strong>{trabajo.total}</strong></div>
              </div>

              <div className="ma-mayores-filtros">
                <select aria-label="Filtrar por severidad" value={filtros.severidad} onChange={(e) => cambiarSeveridad(e.target.value)}>
                  <option value="">Todas</option>
                  {SEVERIDADES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <input aria-label="Filtrar por regla" placeholder="Regla" maxLength={MAXLEN_REGLA} value={entrada.regla}
                       onChange={(e) => setEntrada((f) => ({ ...f, regla: e.target.value }))} />
                <input aria-label="Buscar en entidad o descripción" placeholder="Buscar texto" maxLength={MAXLEN_TEXTO} value={entrada.texto}
                       onChange={(e) => setEntrada((f) => ({ ...f, texto: e.target.value }))} />
              </div>

              <div className="ma-tabla-wrap">
                <table className="ma-tabla">
                  <thead>
                    <tr><th>Severidad</th><th>Regla</th><th>NIA</th><th>Entidad</th><th>Descripción</th><th>Monto</th></tr>
                  </thead>
                  <tbody>
                    {filas.map((f, i) => (
                      <tr key={f.hash || i} onClick={() => setSeleccion(f)}>
                        <td><span className={`ma-sev-${f.severidad}`}>{f.severidad}</span></td>
                        <td>{f.reglaId}</td>
                        <td>{f.nia}</td>
                        <td>{f.entidad}</td>
                        <td>{f.descripcion}</td>
                        <td>{f.monto.sinDatos
                          ? <span className="ma-sindatos">{f.monto.texto}</span>
                          : f.monto.texto}</td>
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
                  {seleccion.reglasConcurrentes?.length > 0 && (
                    <p>Reglas concurrentes: {seleccion.reglasConcurrentes.join(", ")}</p>
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
