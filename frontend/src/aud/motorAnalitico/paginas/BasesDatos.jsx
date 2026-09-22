import { PAGINAS } from "../paginas.js";
import "./BasesDatos.css";

const META = PAGINAS.find((p) => p.id === "bases");

// Catálogo de bases y pruebas transcrito de BasesDatos.dc.html (bloque `bases` del script).
// `estado`: "disponible" | "diseno" | "aparte" (Nómina, herramienta aparte).
const BASES = [
  {
    titulo: "Ventas e ingresos",
    fuente: "XML emitidos + mayor (cuentas 4)",
    estado: "disponible",
    accion: "Ejecutar pruebas",
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
    accion: "Ejecutar pruebas",
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
    accion: "Ejecutar pruebas",
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
    accion: "Ejecutar pruebas",
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
    accion: "Abrir Payroll Audit Suite",
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
    accion: "Próximamente",
    pruebas: [
      { id: "Cruce", nombre: "Declaración aduanera contra inventarios o costos y factura del exterior" },
      { id: "NIC 2", nombre: "Costo de importación capitalizado vs llevado a gasto" },
      { id: "SRI", nombre: "ISD pagado y pagos al exterior con sus retenciones" },
      { id: "Corte", nombre: "Importaciones en tránsito al cierre" },
    ],
  },
];

const ETIQUETA = { disponible: "Disponible", diseno: "En diseño", aparte: "Herramienta aparte" };

export default function BasesDatos({ ir, EnConstruccion }) {
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
        Cada base se prueba completa contra sus maestros. Los cruces con declaraciones, anexos y comprobantes
        del SRI están en Cumplimiento tributario · SRI.
      </p>

      <EnConstruccion sp={META.sp} />

      <div className="ma-grid ma-bases-grid">
        {BASES.map((b) => (
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
            {b.estado === "aparte" ? (
              <span
                className="ma-bases-boton ma-bases-boton-aparte"
                title="Herramienta aparte (AuditBrain Payroll Audit Suite); sin enlace directo todavía"
              >
                {b.accion}
              </span>
            ) : (
              <button
                type="button"
                className={`ma-bases-boton ma-bases-boton-${b.estado}`}
                disabled
                title="Disponible cuando se active SP3"
              >
                {b.accion}
              </button>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
