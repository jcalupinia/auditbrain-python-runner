import { PAGINAS } from "../paginas.js";
import "./Constructor.css";

const META = PAGINAS.find((p) => p.id === "reportes");

const BASES = [
  { clave: "ventas", nombre: "Ventas", fuente: "XML emitidos",
    filas: ["Cliente", "Producto", "Vendedor", "Establecimiento"],
    filtros: ["Fecha en el ejercicio", "Estado = autorizado"], titulo: "Ventas por cliente y mes" },
  { clave: "compras", nombre: "Compras", fuente: "XML recibidos",
    filas: ["Proveedor", "Tipo de comprobante", "Tarifa de IVA", "Cuenta contable"],
    filtros: ["Monto ≥ materialidad", "Estado = autorizado"], titulo: "Compras por proveedor y mes" },
  { clave: "gastos", nombre: "Gastos", fuente: "Mayor · cuentas 5",
    filas: ["Cuenta", "Proveedor", "Centro de costo", "Usuario que registró"],
    filtros: ["Cuentas 5*", "Origen = manual"], titulo: "Gastos por cuenta y mes" },
  { clave: "ingresos", nombre: "Ingresos", fuente: "Mayor · cuentas 4",
    filas: ["Cuenta", "Cliente", "Establecimiento", "Usuario que registró"],
    filtros: ["Cuentas 4*"], titulo: "Ingresos por cuenta y mes" },
  { clave: "mayor", nombre: "Mayor / diario", fuente: "Todos los asientos",
    filas: ["Cuenta", "Usuario que registró", "Origen del asiento", "Contrapartida"],
    filtros: ["Glosa contiene…"], titulo: "Asientos por cuenta y mes" },
  { clave: "nomina", nombre: "Nómina", fuente: "Rol de pagos",
    filas: ["Empleado", "Cargo", "Departamento", "Cuenta bancaria"],
    filtros: ["Activos en el ejercicio"], titulo: "Nómina por departamento y mes" },
];

const PRUEBAS = [
  { nombre: "Top N por importe", ref: "SUMMARIZE" },
  { nombre: "Duplicados", ref: "DUPLICATES" },
  { nombre: "Variación contra el año anterior", ref: "NIA 520" },
  { nombre: "Importes redondos", ref: "GAS-004" },
  { nombre: "Ley de Benford", ref: "GAS-005" },
  { nombre: "Fuera de horario o fin de semana", ref: "AST-002/003" },
];

const RECETAS = [
  { nombre: "Top 20 proveedores por mes con duplicados", base: "Compras" },
  { nombre: "Ventas de los últimos 5 días del ejercicio por cliente", base: "Ventas" },
  { nombre: "Gastos manuales con importe redondo", base: "Gastos" },
  { nombre: "Asientos fuera de horario por usuario", base: "Mayor" },
];

const MESES = ["Ene", "Feb", "Mar", "…", "Nov", "Dic"];

const BASE_DEFECTO = BASES[1]; // compras, igual al estado inicial del lienzo

export default function Constructor({ ir, EnConstruccion }) {
  return (
    <section className="ma-pagina ma-reportes">
      <div className="ma-reportes-encabezado">
        <div className="ma-reportes-titulo">
          <div className="ma-reportes-breadcrumb">
            <span>AUD</span>
            <span> / </span>
            <span>Análisis</span>
            <span> / </span>
            <button type="button" className="ma-reportes-link" onClick={() => ir("portada")}>
              Motor de Auditoría Analítica
            </button>
            <span> / </span>
            <span>Reportes</span>
          </div>
          <h2>Constructor de reportes</h2>
          <p>
            Como una macro, pero reproducible: eliges la base, las variables y la prueba; el motor calcula sobre el
            100 % de la población y guarda los parámetros para que el revisor obtenga el mismo resultado.
          </p>
        </div>
        <span className="ma-reportes-badge">Boceto · {META.sp}</span>
        <button type="button" className="ma-boton" onClick={() => ir("portada")}>
          ← Volver a la portada
        </button>
      </div>

      <EnConstruccion sp={META.sp} />

      <div className="ma-reportes-layout">
        <aside aria-label="Configuración del reporte" className="ma-reportes-aside">
          <section className="ma-tarjeta ma-reportes-seccion">
            <h3>1 · Base de datos</h3>
            <div className="ma-reportes-bases">
              {BASES.map((b) => (
                <button
                  type="button"
                  key={b.clave}
                  disabled
                  aria-pressed={b.clave === BASE_DEFECTO.clave}
                  className={b.clave === BASE_DEFECTO.clave ? "ma-reportes-base activa" : "ma-reportes-base"}
                  title={`Disponible en ${META.sp}`}
                >
                  <span className="ma-reportes-base-nombre">{b.nombre}</span>
                  <span className="ma-reportes-base-fuente">{b.fuente}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="ma-tarjeta ma-reportes-seccion">
            <h3>2 · Variables</h3>
            <label className="ma-reportes-campo">
              Filas
              <select disabled defaultValue={BASE_DEFECTO.filas[0]}>
                {BASE_DEFECTO.filas.map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label className="ma-reportes-campo">
              Columnas
              <select disabled defaultValue="Mes">
                <option>Mes</option>
                <option>Trimestre</option>
                <option>Usuario que registró</option>
                <option>Sin columnas</option>
              </select>
            </label>
            <label className="ma-reportes-campo">
              Medida
              <select disabled defaultValue="Suma del importe">
                <option>Suma del importe</option>
                <option>Número de registros</option>
                <option>Promedio</option>
                <option>Máximo</option>
                <option>Variación contra el año anterior</option>
              </select>
            </label>
            <div className="ma-reportes-campo">
              Filtros
              <div className="ma-reportes-filtros">
                {BASE_DEFECTO.filtros.map((f) => (
                  <span key={f} className="ma-reportes-filtro">
                    {f}
                  </span>
                ))}
                <button type="button" className="ma-reportes-agregar" disabled title={`Disponible en ${META.sp}`}>
                  + filtro
                </button>
              </div>
            </div>
          </section>

          <section className="ma-tarjeta ma-reportes-seccion">
            <h3>3 · Prueba analítica</h3>
            {PRUEBAS.map((p) => (
              <label key={p.ref} className="ma-reportes-prueba">
                <input type="checkbox" disabled />
                <span className="ma-reportes-prueba-nombre">{p.nombre}</span>
                <span className="ma-reportes-prueba-ref">{p.ref}</span>
              </label>
            ))}
          </section>
        </aside>

        <section aria-label="Resultado" className="ma-reportes-resultado">
          <div className="ma-tarjeta ma-reportes-barra">
            <span className="ma-reportes-nota">Reporte:</span>
            <span className="ma-reportes-reporte-titulo">{BASE_DEFECTO.titulo}</span>
            <div className="ma-reportes-acciones">
              <button type="button" className="ma-boton" disabled title={`Disponible en ${META.sp}`}>
                Guardar como receta
              </button>
              <button type="button" className="ma-boton" disabled title={`Disponible en ${META.sp}`}>
                Exportar a Excel
              </button>
              <button type="button" className="ma-boton ma-reportes-ejecutar" disabled title={`Disponible en ${META.sp}`}>
                Ejecutar
              </button>
            </div>
          </div>

          <div className="ma-tarjeta ma-reportes-seccion">
            <div className="ma-reportes-titulo-fila">
              <h3>Vista previa</h3>
              <span className="ma-reportes-nota">Estructura del reporte; los valores aparecen al ejecutarlo sobre el encargo</span>
            </div>
            <div className="ma-tabla-wrap">
              <table className="ma-tabla">
                <thead>
                  <tr>
                    <th scope="col">{BASE_DEFECTO.filas[0]}</th>
                    {MESES.map((m, i) => (
                      <th scope="col" key={`${m}-${i}`}>{m}</th>
                    ))}
                    <th scope="col">Señal</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td colSpan={MESES.length + 2} className="ma-sindatos">
                      sin datos
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="ma-grid ma-reportes-cols2">
            <div className="ma-tarjeta ma-reportes-seccion">
              <h3>Recetas guardadas</h3>
              {RECETAS.map((r) => (
                <span key={r.nombre} className="ma-reportes-receta">
                  <span className="ma-reportes-receta-nombre">{r.nombre}</span>
                  <span className="ma-reportes-nota">{r.base}</span>
                </span>
              ))}
            </div>
            <div className="ma-tarjeta ma-reportes-seccion">
              <h3>Trazabilidad de la ejecución</h3>
              <p>
                Cada ejecución guarda la base, las variables, los filtros, la prueba, la materialidad del encargo y el
                código SHA-256 de los archivos. Otro auditor puede repetirla y obtener exactamente lo mismo.
              </p>
              <div className="ma-reportes-codigo">
                <span>base = {"<base elegida>"}</span>
                <span>filas = {"<criterio elegido>"} · columnas = mes</span>
                <span>pruebas = {"<pruebas marcadas>"}</span>
                <span>esquema de hash = 2</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}
