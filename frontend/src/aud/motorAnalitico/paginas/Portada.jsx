import { PAGINAS } from "../paginas.js";
import "./Portada.css";

// Transcripción de Main.dc.html (Task 4). Bloques del lienzo → bloques del JSX:
// 1) migas de pan; 2) cabecera (título + selector de encargo + botón);
// 3) resumen del encargo (4 tarjetas); 4) áreas de análisis (7 tarjetas);
// 5) excepciones prioritarias; 6) pie de página; 7) accesos a Revisión con
// agentes y Hoja de ruta (regla de conversión #6). Portada no lleva
// <EnConstruccion /> (regla #5: es la página de entrada, no una franja).
// El encabezado global (logo AUDIT-IA, nav de módulos, usuario) y el "Motor
// en línea" del lienzo los da ya el armazón (ma-nav / ma-estado).

const AREAS = [
  {
    id: "mayores",
    titulo: "Análisis de mayores y diarios",
    texto: "Pruebas de asientos (NIA 240), asientos manuales fuera de patrón, explorador por cuenta, mes y usuario, y búsqueda de conceptos en todo el diario.",
    incluye: ["8 pruebas de asientos", "Explorador (cubos)", "Buscar concepto"],
    trazo: "M4 5h16M4 10h16M4 15h10M4 20h7",
  },
  {
    id: "estados",
    titulo: "Análisis de estados financieros",
    texto: "Variaciones horizontales y verticales, ratios por período y expectativa contra lo real (NIA 520), sobre los estados homologados del Motor de balances.",
    incluye: ["Horizontal y vertical", "Ratios", "Expectativa vs real"],
    trazo: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  },
  {
    id: "bases",
    titulo: "Análisis de bases de datos",
    texto: "Ventas, compras y gastos, proveedores y partes relacionadas y nómina: cada base probada completa contra sus maestros.",
    incluye: ["Ventas · 10", "Compras · 7", "Gastos · 6", "Proveedores · 7"],
    trazo: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  },
  {
    id: "sri",
    titulo: "Cumplimiento tributario · SRI",
    texto: "Declaraciones y anexos tributarios (XML, Excel, PDF) contra la contabilidad, y los comprobantes electrónicos del robot del SRI: ventas, compras, retenciones, duplicados, saltos de facturación y empresas fantasmas.",
    incluye: ["Comprobantes SRI", "Declaraciones", "Anexos", "Empresas fantasmas"],
    trazo: "M6 3h9l4 4v14H6zM9 12l2 2 4-4",
  },
  {
    id: "niif",
    titulo: "Políticas contables NIIF",
    texto: "Manuales de políticas para NIIF completas y PYMES, política contra registro, recálculo de estimaciones (NIA 540), checklist de revelaciones y cambios de política (NIC 8).",
    incluye: ["Manual de políticas", "Estimaciones", "Revelaciones", "Completas y PYMES"],
    trazo: "M4 4h11l5 5v11H4zM8 13h8M8 17h5M8 9h4",
  },
  {
    id: "muestras",
    titulo: "Selección de muestras",
    texto: "Sobre mayores de gastos, estado de resultados, ventas, compras o importaciones: partidas clave, valores atípicos, selección dirigida y MUS, con cédula de selección y documentos a pedir.",
    incluye: ["Partidas clave", "Atípicos", "Dirigida", "MUS · NIA 530"],
    trazo: "M4 4h16v16H4zM8 8h2v2H8zM14 8h2v2h-2zM8 14h2v2H8zM14 14h2v2h-2z",
  },
  {
    id: "reportes",
    titulo: "Reportes",
    texto: "Constructor de reportes: eliges base, variables y prueba, y guardas la combinación como receta reutilizable en cualquier encargo. Papel de trabajo en Excel y PDF.",
    incluye: ["Constructor", "Recetas", "Exportar a Excel"],
    trazo: "M6 3h9l4 4v14H6zM9 12h7M9 16h7M9 8h3",
  },
];

// Excepciones de ejemplo del lienzo: montos y fechas son cifras de
// demostración → «sin datos» (regla #4). Reglas, prioridades y roles
// genéricos («Jefe de Compras») se conservan.
const EXCEPCIONES = [
  {
    p: "P0",
    reglas: "AST-001 · 004 · VTA-009",
    texto: (
      <>
        Asiento manual de <span className="ma-sindatos">sin datos</span> a ingresos, glosa «ajuste», capturado después
        del cierre.
      </>
    ),
  },
  {
    p: "P0",
    reglas: "PRV-002 · PRV-003",
    texto: "Proveedor cuyo RUC y cuenta bancaria coinciden con los del Jefe de Compras.",
  },
  {
    p: "P1",
    reglas: "VTA-003",
    texto: (
      <>
        Nota de crédito por <span className="ma-sindatos">sin datos</span> emitida el{" "}
        <span className="ma-sindatos">sin datos</span>, posterior al cierre.
      </>
    ),
  },
];

export default function Portada({ ir }) {
  return (
    <section className="ma-pagina ma-portada">
      <div className="ma-portada-migas">
        AUD <span>/</span> Análisis <span>/</span> <b>Motor de Auditoría Analítica</b>
      </div>

      <div className="ma-portada-cab">
        <div className="ma-portada-titulo">
          <h1>Motor de Auditoría Analítica</h1>
          <p>
            Analiza el 100&nbsp;% de la población del encargo y la reduce a excepciones trazables con regla, norma,
            monto y evidencia. El auditor revisa, decide y firma.
          </p>
        </div>
        <div className="ma-portada-controles">
          <label>
            Encargo
            <select disabled defaultValue="demo" title="Selección de encargo: disponible con la ingesta (SP3)">
              <option value="demo">DEMO · Ejercicio sintético 2026</option>
            </select>
          </label>
          <button
            type="button"
            className="ma-boton"
            disabled
            title="Cargar insumos del encargo: disponible con la ingesta (SP3)"
          >
            Cargar insumos
          </button>
        </div>
      </div>

      <section aria-label="Resumen del encargo" className="ma-portada-resumen">
        <div className="ma-tarjeta">
          <span>Población analizada</span>
          <strong>
            <span className="ma-sindatos">sin datos</span>
          </strong>
          <span>
            <span className="ma-sindatos">sin datos</span> líneas de mayor · <span className="ma-sindatos">sin datos</span>{" "}
            XML
          </span>
        </div>
        <div className="ma-tarjeta">
          <span>Excepciones para revisión</span>
          <strong>
            <span className="ma-sindatos">sin datos</span>
          </strong>
          <span>
            <span className="ma-sindatos">sin datos</span> de la población
          </span>
        </div>
        <div className="ma-tarjeta">
          <span>Por prioridad</span>
          <div className="ma-portada-prioridad">
            <span className="ma-sev-P0">
              <span className="ma-sindatos">sin datos</span> P0
            </span>
            <span className="ma-sev-P1">
              <span className="ma-sindatos">sin datos</span> P1
            </span>
            <span className="ma-sev-P2">
              <span className="ma-sindatos">sin datos</span> P2
            </span>
          </div>
        </div>
        <div className="ma-tarjeta">
          <span>Etapa del encargo</span>
          <strong>
            <span className="ma-sindatos">sin datos</span>
          </strong>
          <span>
            paso <span className="ma-sindatos">sin datos</span> de <span className="ma-sindatos">sin datos</span> ·
            pruebas terminadas
          </span>
        </div>
      </section>

      <section aria-label="Áreas de análisis" className="ma-portada-areas">
        {AREAS.map((a) => {
          const meta = PAGINAS.find((p) => p.id === a.id);
          return (
            <button key={a.id} type="button" className="ma-tarjeta ma-portada-area" onClick={() => ir(a.id)}>
              <div className="ma-portada-area-cab">
                <span className="ma-portada-icono" aria-hidden="true">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d={a.trazo} />
                  </svg>
                </span>
                <span className="ma-portada-area-titulo">{a.titulo}</span>
                <span className={meta?.operativa ? "ma-portada-etiqueta ma-portada-etiqueta-op" : "ma-portada-etiqueta"}>
                  {meta?.operativa ? "Operativa" : `En construcción · ${meta?.sp}`}
                </span>
              </div>
              <p>{a.texto}</p>
              <div className="ma-portada-chips">
                {a.incluye.map((i) => (
                  <span key={i}>{i}</span>
                ))}
              </div>
              <span className="ma-portada-entrar">Entrar →</span>
            </button>
          );
        })}
      </section>

      <section aria-label="Excepciones prioritarias" className="ma-tarjeta ma-portada-excepciones">
        <div className="ma-portada-excepciones-cab">
          <h2>Excepciones prioritarias</h2>
          <span>Requieren investigación; no son conclusiones</span>
          <button type="button" className="link ma-portada-ver-agentes" onClick={() => ir("agentes")}>
            Revisión con agentes (<span className="ma-sindatos">sin datos</span>) →
          </button>
        </div>
        {EXCEPCIONES.map((e, i) => (
          <div className="ma-portada-excepcion" key={i}>
            <span className={`ma-sev-${e.p}`}>{e.p}</span>
            <span className="ma-portada-excepcion-reglas">{e.reglas}</span>
            <span>{e.texto}</span>
          </div>
        ))}
      </section>

      <footer className="ma-portada-pie">
        <span className="ma-portada-barra" aria-hidden="true" />
        <span>
          Las reglas deterministas detectan y cuantifican; la IA solo prioriza y redacta.{" "}
          <strong>Ninguna cifra la produce un modelo de lenguaje.</strong>
        </span>
        <span className="ma-portada-firma">AuditConsulting Auditores Cía. Ltda.</span>
      </footer>

      <nav aria-label="Otras páginas del motor" className="ma-portada-otras">
        <button type="button" className="ma-boton" onClick={() => ir("agentes")}>
          Revisión con agentes →
        </button>
        <button type="button" className="ma-boton" onClick={() => ir("ruta")}>
          Hoja de ruta →
        </button>
      </nav>
    </section>
  );
}
