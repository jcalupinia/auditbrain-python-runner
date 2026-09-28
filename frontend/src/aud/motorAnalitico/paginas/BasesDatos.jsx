import { useEffect, useRef, useState } from "react";
import { PAGINAS } from "../paginas.js";
import {
  SEVERIDADES, filasBandeja, mensajeError, resumenSeveridad, terminado,
} from "../bandeja.js";
import "./BasesDatos.css";

const META = PAGINAS.find((p) => p.id === "bases");

// Catálogo de bases y pruebas transcrito de BasesDatos.dc.html (bloque `bases` del script).
// `base`: la clave que el motor usa para filtrar (motor/nucleo.py::BASES). Las bases sin
// clave (`estado` aparte/diseno) no se ejecutan aquí: son herramientas separadas.
const BASES = [
  {
    titulo: "Ventas e ingresos",
    fuente: "XML emitidos + mayor (cuentas 4)",
    estado: "disponible",
    base: "ventas",
    pruebas: [
      { id: "VTA-001", nombre: "Brecha en la secuencia de facturación" },
      { id: "VTA-002", nombre: "Facturación retroactiva" },
      { id: "VTA-003", nombre: "Nota de crédito posterior al cierre" },
      { id: "VTA-004", nombre: "Concentración de ventas en el cierre" },
      { id: "VTA-005", nombre: "Precio fuera del rango histórico" },
      { id: "VTA-006", nombre: "IVA recalculado difiere del declarado" },
      { id: "VTA-007", nombre: "Cliente nuevo con volumen material al cierre" },
      { id: "VTA-008 · 009", nombre: "Venta no registrada o ingreso sin comprobante" },
      { id: "VTA-010", nombre: "Venta a empleado registrado en nómina" },
    ],
  },
  {
    titulo: "Compras y conciliación SRI",
    fuente: "XML recibidos + mayor",
    estado: "disponible",
    base: "compras",
    pruebas: [
      { id: "CON-001", nombre: "Gasto sin comprobante autorizado" },
      { id: "CON-002", nombre: "Comprobante autorizado no registrado" },
      { id: "CON-003", nombre: "Diferencia de importe comprobante vs. registro" },
      { id: "CON-004", nombre: "Registro en período distinto (corte)" },
      { id: "CON-005", nombre: "Comprobante no autorizado usado como sustento" },
      { id: "CON-006", nombre: "Comprobante aritméticamente inconsistente" },
      { id: "CON-007", nombre: "Clave de acceso inválida" },
    ],
  },
  {
    titulo: "Gastos",
    fuente: "Mayor (cuentas 5) + pagos",
    estado: "disponible",
    base: "gastos",
    pruebas: [
      { id: "GAS-001", nombre: "Fraccionamiento bajo el umbral de aprobación" },
      { id: "GAS-002", nombre: "Pago posiblemente duplicado" },
      { id: "GAS-003", nombre: "Mismo comprobante registrado más de una vez" },
      { id: "GAS-004", nombre: "Concentración de importes redondos" },
      { id: "GAS-005", nombre: "Ley de Benford" },
      { id: "GAS-006", nombre: "Gasto atípico frente a su cuenta" },
    ],
  },
  {
    titulo: "Proveedores y partes relacionadas",
    fuente: "Maestro de proveedores + nómina",
    estado: "disponible",
    base: "proveedores",
    pruebas: [
      { id: "PRV-001", nombre: "RUC de proveedor inválido" },
      { id: "PRV-002", nombre: "Proveedor con cédula de empleado" },
      { id: "PRV-003 · 004", nombre: "Cuenta bancaria compartida con empleado u otro proveedor" },
      { id: "PRV-005", nombre: "Proveedor creado y pagado de inmediato" },
      { id: "PRV-006", nombre: "Proveedor con una sola operación material" },
      { id: "PRV-007", nombre: "Ausencia de segregación de funciones" },
    ],
  },
  {
    titulo: "Nómina",
    fuente: "AuditBrain Payroll Audit Suite (herramienta aparte)",
    estado: "aparte",
    base: null,
    pruebas: [
      { id: "Payroll", nombre: "Recálculo de sueldos, décimos, fondos de reserva, vacaciones y aportes IESS" },
      { id: "Payroll", nombre: "Conciliaciones de roles contra IESS, mayor y bancos" },
      { id: "Payroll", nombre: "Anomalías de nómina, jubilación patronal y desahucio" },
      { id: "Motor", nombre: "Empleado que es proveedor o cliente (PRV-002/003, VTA-010)" },
    ],
  },
  {
    titulo: "Importaciones",
    fuente: "Declaraciones aduaneras (SENAE) + mayor",
    estado: "diseno",
    base: null,
    pruebas: [
      { id: "Cruce", nombre: "Declaración aduanera contra inventarios o costos y factura del exterior" },
      { id: "NIC 2", nombre: "Costo de importación capitalizado vs llevado a gasto" },
      { id: "SRI", nombre: "ISD pagado y pagos al exterior con sus retenciones" },
      { id: "Corte", nombre: "Importaciones en tránsito al cierre" },
    ],
  },
];

const ETIQUETA = { disponible: "Disponible", diseno: "En diseño", aparte: "Herramienta aparte" };
// Bases con clave del motor (ejecutables desde esta página), en orden de pestaña.
const BASES_MOTOR = BASES.filter((b) => b.base);
const TAM_PAGINA = 50;
const SONDEO_MS = 5000;
const EXC_VACIAS = { total: 0, pagina: 1, excepciones: [] };

const elegir = (set) => (e) => set(e.target.files?.[0] || null);
const totalPaginas = (total) => Math.max(1, Math.ceil((total || 0) / TAM_PAGINA));

export default function BasesDatos({ ir, cliente, disponible }) {
  const [archivo, setArchivo] = useState(null);
  const [trabajo, setTrabajo] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [baseActiva, setBaseActiva] = useState(BASES_MOTOR[0].base);
  const [excepciones, setExcepciones] = useState(EXC_VACIAS);
  const [pagina, setPagina] = useState(1);
  const [descargando, setDescargando] = useState(false);
  const montado = useRef(true);

  useEffect(() => () => { montado.current = false; }, []);

  // Al cambiar de encargo (cliente) se descarta el trabajo anterior.
  useEffect(() => {
    setTrabajo(null);
    setExcepciones(EXC_VACIAS);
    setErrorMsg("");
    setBaseActiva(BASES_MOTOR[0].base);
    setPagina(1);
  }, [cliente]);

  // Sondeo del trabajo: setTimeout encadenado. Se detiene cuando el trabajo
  // ya no es el activo, terminó, o el motor lo perdió (404).
  useEffect(() => {
    if (!trabajo?.id || terminado(trabajo.estado)) return undefined;
    const id = trabajo.id;
    let vivo = true;
    const tick = async () => {
      try {
        const r = await cliente.trabajo(id);
        if (!vivo || !montado.current) return;
        setTrabajo((t) => (t?.id === id ? r : t));
        if (!terminado(r.estado)) setTimeout(tick, SONDEO_MS);
      } catch (e) {
        if (!vivo || !montado.current) return;
        setErrorMsg(mensajeError(e));
        setTrabajo((t) => (t?.id === id ? null : t));
      }
    };
    const reloj = setTimeout(tick, SONDEO_MS);
    return () => { vivo = false; clearTimeout(reloj); };
  }, [trabajo?.id, trabajo?.estado, cliente]);

  // Excepciones de la base activa cuando el trabajo está listo (o al cambiar
  // base/página). Un contador evita que una respuesta lenta pise a otra.
  useEffect(() => {
    if (trabajo?.estado !== "listo") { setExcepciones(EXC_VACIAS); return undefined; }
    let vigente = true;
    cliente.excepciones(trabajo.id, { base: baseActiva, pagina, tam: TAM_PAGINA })
      .then((r) => { if (vigente && montado.current) setExcepciones(r); })
      .catch((e) => { if (vigente && montado.current) setErrorMsg(mensajeError(e)); });
    return () => { vigente = false; };
  }, [trabajo?.estado, trabajo?.id, baseActiva, pagina, cliente]);

  const iniciar = async (crear) => {
    setErrorMsg("");
    setCargando(true);
    try {
      const nuevo = await crear();
      if (!montado.current) return;
      setTrabajo(nuevo);
      setExcepciones(EXC_VACIAS);
      setPagina(1);
      setBaseActiva(BASES_MOTOR[0].base);
    } catch (e) {
      if (montado.current) setErrorMsg(mensajeError(e));
    } finally {
      if (montado.current) setCargando(false);
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

  const descargarPapel = async () => {
    if (!trabajo?.id) return;
    setErrorMsg("");
    setDescargando(true);
    try {
      const blob = await cliente.papelBases(trabajo.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `papel-bases-datos-${trabajo.id}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErrorMsg(mensajeError(e));
    } finally {
      if (montado.current) setDescargando(false);
    }
  };

  const listo = trabajo?.estado === "listo";
  const porBase = trabajo?.por_base || {};
  const filas = filasBandeja(excepciones);
  const totalPag = totalPaginas(excepciones.total);
  const baseCard = BASES.find((b) => b.base === baseActiva);

  return (
    <section className="ma-pagina ma-bases-pagina">
      <div className="ma-bases-breadcrumb">
        <button type="button" className="ma-bases-link" onClick={() => ir("portada")}>
          Motor de Auditoría Analítica
        </button>
        <span className="ma-bases-sep">/</span>
        <span>Análisis de bases de datos</span>
      </div>

      <div className="ma-bases-encabezado">
        <h2>{META.titulo}</h2>
        <div className="ma-bases-acciones">
          <button type="button" className="ma-bases-boton-primario" onClick={() => ir("reportes")}>
            Armar un reporte propio
          </button>
          <button type="button" className="ma-boton" onClick={() => ir("portada")}>
            ← Volver a la portada
          </button>
        </div>
      </div>
      <p className="ma-bases-intro">
        Cada base se prueba completa contra sus maestros. Sube la plantilla del motor con el mayor, los
        comprobantes, las ventas, el maestro de proveedores y la nómina; el motor corre las 38 reglas y
        agrupa las excepciones por base. Los cruces con declaraciones y anexos del SRI están en
        Cumplimiento tributario · SRI.
      </p>

      {/* Correr el motor */}
      <div className="ma-bases-motor">
        <h3>Correr el motor sobre las bases</h3>
        {!disponible && <p className="ma-bases-hint">Revisa la conexión con el motor arriba.</p>}
        <div className="ma-bases-motor-acciones">
          <button className="ma-boton accent" disabled={!disponible || cargando}
                  onClick={() => iniciar(() => cliente.crearDemo())}>
            Correr demo sintético
          </button>
          <button className="ma-boton" disabled={!disponible || cargando} onClick={descargarPlantilla}>
            Descargar plantilla
          </button>
          <div className="ma-bases-subir">
            <input type="file" aria-label="Plantilla del motor (.xlsx)" accept=".xlsx"
                   disabled={!disponible || cargando} onChange={elegir(setArchivo)} />
            <button className="ma-boton" disabled={!disponible || cargando || !archivo}
                    onClick={() => iniciar(() => cliente.crearConArchivo(archivo))}>
              Subir y correr
            </button>
          </div>
        </div>
        <span className="ma-bases-aviso">Solo datos anonimizados hasta SP4.</span>
        {errorMsg && <p className="ma-bases-error" role="alert">{errorMsg}</p>}
        {trabajo && (
          <div className="ma-bases-trabajo">
            <span>Estado: <strong>{trabajo.estado}</strong></span>
            {trabajo.origen && <span> · Origen: {trabajo.origen}</span>}
            {trabajo.sha256 && <span className="ma-bases-mono"> · Huella: {trabajo.sha256.slice(0, 16)}…</span>}
          </div>
        )}
      </div>

      {listo && (
        <>
          <div className="ma-grid ma-bases-resumen">
            {resumenSeveridad(trabajo.por_severidad).map(([sev, n]) => (
              <div key={sev} className="ma-tarjeta">
                <span className={`ma-sev-${sev}`}>{sev}</span>
                <strong>{n}</strong>
              </div>
            ))}
            <div className="ma-tarjeta"><span>Total</span><strong>{trabajo.total}</strong></div>
            <button className="ma-boton accent ma-bases-papel" disabled={descargando}
                    onClick={descargarPapel}>
              {descargando ? "Generando…" : "Descargar papel de trabajo"}
            </button>
          </div>

          <nav className="ma-bases-tabs" aria-label="Bases del motor">
            {BASES_MOTOR.map((b) => (
              <button key={b.base}
                      className={b.base === baseActiva ? "ma-bases-tab activa" : "ma-bases-tab"}
                      aria-current={b.base === baseActiva ? "true" : undefined}
                      onClick={() => { setBaseActiva(b.base); setPagina(1); }}>
                {b.titulo}
                <span className="ma-bases-tab-conteo">{porBase[b.base] || 0}</span>
              </button>
            ))}
          </nav>

          <div className="ma-bases-detalle">
            <div className="ma-bases-detalle-cab">
              <div>
                <h3>{baseCard?.titulo}</h3>
                <span className="ma-bases-fuente">Fuente: {baseCard?.fuente}</span>
              </div>
              <span className="ma-bases-conteo-grande">
                {excepciones.total} excepción(es)
              </span>
            </div>

            {filas.length === 0 ? (
              <p className="ma-bases-vacio">Sin excepciones en esta base.</p>
            ) : (
              <>
                <div className="ma-tabla-wrap">
                  <table className="ma-tabla">
                    <thead>
                      <tr><th>Severidad</th><th>Regla</th><th>NIA</th><th>Entidad</th><th>Descripción</th><th>Monto</th></tr>
                    </thead>
                    <tbody>
                      {filas.map((f, i) => (
                        <tr key={f.hash || i}>
                          <td><span className={`ma-sev-${f.severidad}`}>{f.severidad}</span></td>
                          <td className="ma-bases-mono">{f.reglaId}</td>
                          <td>{f.nia}</td>
                          <td>{f.entidad}</td>
                          <td>{f.descripcion}</td>
                          <td className={f.monto.sinDatos ? "ma-bases-sindatos" : "ma-bases-monto"}>
                            {f.monto.texto}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {totalPag > 1 && (
                  <div className="ma-bases-paginacion">
                    <button className="ma-boton" disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}>
                      ← Anterior
                    </button>
                    <span>Página {excepciones.pagina} de {totalPag}</span>
                    <button className="ma-boton" disabled={pagina >= totalPag} onClick={() => setPagina((p) => p + 1)}>
                      Siguiente →
                    </button>
                  </div>
                )}
              </>
            )}

            <details className="ma-bases-pruebas-lista">
              <summary>Pruebas de esta base ({baseCard?.pruebas.length})</summary>
              <ul className="ma-bases-pruebas">
                {baseCard?.pruebas.map((p, i) => (
                  <li key={`${p.id}-${i}`}>
                    <span className="ma-bases-id">{p.id}</span>
                    <span>{p.nombre}</span>
                  </li>
                ))}
              </ul>
            </details>
          </div>
        </>
      )}

      {/* Herramientas aparte / en diseño: catálogo de referencia (no ejecutable aquí) */}
      <div className="ma-grid ma-bases-grid">
        {BASES.filter((b) => b.estado !== "disponible").map((b) => (
          <article className="ma-tarjeta ma-bases-tarjeta" key={b.titulo}>
            <div className="ma-bases-tarjeta-cab">
              <h3>{b.titulo}</h3>
              <span className={`ma-bases-estado ma-bases-estado-${b.estado}`}>{ETIQUETA[b.estado]}</span>
            </div>
            <span className="ma-bases-fuente">Fuente: {b.fuente}</span>
            <ul className="ma-bases-pruebas">
              {b.pruebas.map((p, i) => (
                <li key={`${p.id}-${i}`}>
                  <span className="ma-bases-id">{p.id}</span>
                  <span>{p.nombre}</span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}
