import { PAGINAS } from "../paginas.js";
import "./EstadosFinancieros.css";

const META = PAGINAS.find((p) => p.id === "estados");

// Contenido transcrito de EstadosFinancieros.dc.html (bloque `bloques` del script).
const BLOQUES = [
  {
    titulo: "Horizontal y vertical",
    texto: "Compara cada rubro entre períodos y contra el total del grupo.",
    puntos: [
      "Variación absoluta y porcentual",
      "Peso de cada rubro en su grupo",
      "Marca lo que supera la materialidad de ejecución",
    ],
    norma: "NIA 315 · NIA 520",
  },
  {
    titulo: "Ratios por período",
    texto: "Indicadores de la firma calculados sobre los estados homologados.",
    puntos: [
      "Liquidez: razón corriente, DSO, DPO, DIO",
      "Endeudamiento: pasivo/activo, deuda/EBITDA",
      "Cobertura: DSCR e ICR",
      "Rentabilidad por período",
    ],
    norma: "Perfil financiero de la firma",
  },
  {
    titulo: "Expectativa contra lo real",
    texto: "El auditor define la expectativa y el umbral; el motor explica la diferencia.",
    puntos: [
      "Expectativa por tendencia, presupuesto o razonabilidad",
      "Umbral de diferencia aceptable",
      "Diferencias que exigen explicación",
    ],
    norma: "NIA 520",
  },
];

// `rubros` del script: nunca se fusionan grupos NIIF distintos.
const RUBROS = [
  "Efectivo y equivalentes",
  "Cuentas por cobrar",
  "Inventarios",
  "Propiedades, planta y equipo",
  "Ingresos de actividades ordinarias",
];

const COLUMNAS_VARIACION = ["Año anterior", "Año actual", "Variación", "% del total", "Frente a materialidad"];

export default function EstadosFinancieros({ ir, EnConstruccion }) {
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
        <button type="button" className="ma-boton" onClick={() => ir("portada")}>
          ← Volver a la portada
        </button>
      </div>

      <EnConstruccion sp={META.sp} />

      <div className="ma-estados-fuente">
        <span>
          Fuente: estados de situación financiera y de resultados{" "}
          <strong>homologados por el Motor de balances</strong> (formato Superintendencia, N períodos).
        </span>
        <span
          className="ma-estados-enlace-inerte"
          title="Motor de balances es otra herramienta del catálogo AUD; el enlace directo entre tarjetas no está definido"
        >
          Abrir Motor de balances →
        </span>
      </div>

      <div className="ma-grid ma-estados-bloques">
        {BLOQUES.map((b) => (
          <article className="ma-tarjeta ma-estados-tarjeta" key={b.titulo}>
            <div className="ma-estados-tarjeta-cab">
              <h3>{b.titulo}</h3>
              <span className="ma-estados-badge">En diseño</span>
            </div>
            <p>{b.texto}</p>
            <ul className="ma-estados-puntos">
              {b.puntos.map((pt) => (
                <li key={pt}>{pt}</li>
              ))}
            </ul>
            <span className="ma-estados-norma">{b.norma}</span>
          </article>
        ))}
      </div>

      <section aria-label="Vista de variaciones" className="ma-tarjeta ma-estados-variaciones">
        <div className="ma-estados-variaciones-cab">
          <h3>Vista de variaciones</h3>
          <span>Estructura; los valores salen de los estados homologados del encargo</span>
        </div>
        <div className="ma-tabla-wrap">
          <table className="ma-tabla ma-estados-tabla">
            <thead>
              <tr>
                <th scope="col">Rubro</th>
                {COLUMNAS_VARIACION.map((c) => (
                  <th scope="col" key={c}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {RUBROS.map((r) => (
                <tr key={r}>
                  <td>{r}</td>
                  {COLUMNAS_VARIACION.map((c) => (
                    <td key={c}>
                      <span className="ma-sindatos">sin datos</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <span className="ma-estados-nota">
          Cada rubro NIIF se presenta por separado: inventarios, cuentas por cobrar y propiedades, planta y
          equipo nunca se fusionan.
        </span>
      </section>
    </section>
  );
}
