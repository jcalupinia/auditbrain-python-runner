import { PAGINAS } from "../paginas.js";
import "./PoliticasNIIF.css";

const META = PAGINAS.find((p) => p.id === "niif");

const SECCIONES_PYMES = [
  ["Sec. 3", "Presentación de estados financieros"],
  ["Sec. 7", "Estado de flujos de efectivo"],
  ["Sec. 8", "Notas a los estados financieros"],
  ["Sec. 9", "Estados consolidados y separados"],
  ["Sec. 10", "Políticas, estimaciones y errores"],
  ["Sec. 11", "Instrumentos financieros básicos"],
  ["Sec. 12", "Otros instrumentos financieros"],
  ["Sec. 13", "Inventarios"],
  ["Sec. 14", "Inversiones en asociadas"],
  ["Sec. 15", "Negocios conjuntos"],
  ["Sec. 16", "Propiedades de inversión"],
  ["Sec. 17", "Propiedades, planta y equipo"],
  ["Sec. 18", "Activos intangibles"],
  ["Sec. 19", "Combinaciones de negocios y plusvalía"],
  ["Sec. 20", "Arrendamientos"],
  ["Sec. 21", "Provisiones y contingencias"],
  ["Sec. 22", "Pasivos y patrimonio"],
  ["Sec. 23", "Ingresos de actividades ordinarias"],
  ["Sec. 24", "Subvenciones del gobierno"],
  ["Sec. 25", "Costos por préstamos"],
  ["Sec. 26", "Pagos basados en acciones"],
  ["Sec. 27", "Deterioro del valor de los activos"],
  ["Sec. 28", "Beneficios a los empleados"],
  ["Sec. 29", "Impuesto a las ganancias"],
  ["Sec. 30", "Conversión de moneda extranjera"],
  ["Sec. 32", "Hechos posteriores"],
  ["Sec. 33", "Partes relacionadas"],
  ["Sec. 34", "Actividades especializadas"],
  ["Sec. 35", "Transición a la NIIF para las PYMES"],
];

const PASOS = [
  { n: "PASO 1", titulo: "Marco y cliente", texto: "Completas o PYMES, actividad del cliente y ejercicio." },
  { n: "PASO 2", titulo: "Rubros", texto: "Solo las normas o secciones que aplican a sus saldos y operaciones." },
  { n: "PASO 3", titulo: "Decisiones", texto: "Las opciones de política que la norma permite, una por rubro." },
  { n: "PASO 4", titulo: "Manual", texto: "Word con la redacción de la firma, listo para revisión y aprobación." },
];

const DECISIONES = [
  { pregunta: "Medición posterior de propiedades, planta y equipo", opciones: "Costo · Revaluación" },
  { pregunta: "Fórmula de costo de inventarios", opciones: "Promedio ponderado · FIFO" },
  { pregunta: "Propiedades de inversión", opciones: "Costo · Valor razonable" },
  { pregunta: "Ganancias y pérdidas actuariales (NIC 19)", opciones: "Otro resultado integral" },
  { pregunta: "Arrendamientos de corto plazo o bajo valor", opciones: "Exención · Reconocer" },
];

const MATRIZ = [
  { norma: "NIC 16 · PYMES 17", rubro: "Propiedades, planta y equipo", ejemplo: "La política dice vehículos a 5 años y el mayor deprecia a 10; activos totalmente depreciados que siguen en uso." },
  { norma: "NIC 2 · PYMES 13", rubro: "Inventarios", ejemplo: "La política dice costo promedio y el kárdex usa el último costo." },
  { norma: "NIIF 15 · PYMES 23", rubro: "Ingresos", ejemplo: "Se reconoce al entregar, pero hay facturas de diciembre con guía de remisión de enero." },
  { norma: "NIC 8 · PYMES 10", rubro: "Marco aplicable", ejemplo: "Cliente en PYMES con un tratamiento propio de NIIF completas, o al revés." },
];

const ETIQUETA_ESTADO = { existe: "En Command Center", base: "Base lista", nuevo: "Por construir" };

const ESTIMACIONES = [
  { norma: "NIC 2 · PYMES 13", que: "Valor neto de realización contra costo", excepcion: "Productos con VNR menor al costo sin deterioro", estado: "existe" },
  { norma: "NIIF 9 · PYMES 11", que: "Pérdida crediticia por antigüedad de cartera", excepcion: "Cartera de más de 360 días sin provisión", estado: "existe" },
  { norma: "NIC 19 · PYMES 28", que: "Estudio actuarial contra nómina y mayor", excepcion: "Empleados con más de 10 años fuera del estudio; desahucio sin provisionar", estado: "nuevo" },
  { norma: "NIIF 16 · PYMES 20", que: "Gastos de arriendo recurrentes en el mayor", excepcion: "Local arrendado 3 años registrado solo como gasto", estado: "base" },
  { norma: "NIC 36 · PYMES 27", que: "Indicios de deterioro", excepcion: "Unidad con pérdidas en 3 períodos sin análisis de deterioro", estado: "nuevo" },
  { norma: "NIC 12 · PYMES 29", que: "Diferencias temporarias por rubro", excepcion: "Provisión de jubilación no deducible sin impuesto diferido", estado: "nuevo" },
  { norma: "NIC 37 · PYMES 21", que: "Provisiones sin movimiento y litigios", excepcion: "Provisión intacta desde hace dos años", estado: "nuevo" },
];

const REVELACIONES = [
  "Partes relacionadas · NIC 24",
  "Supuestos actuariales · NIC 19",
  "Hechos posteriores · NIC 10",
  "Empresa en marcha",
  "Políticas significativas",
];

export default function PoliticasNIIF({ ir, EnConstruccion }) {
  return (
    <section className="ma-pagina ma-niif">
      <div className="ma-niif-breadcrumb">
        <button type="button" className="ma-niif-link" onClick={() => ir("portada")}>
          Motor de Auditoría Analítica
        </button>
        <span> / </span>
        <span>Políticas contables NIIF</span>
      </div>

      <div className="ma-niif-encabezado">
        <h2>Políticas contables NIIF</h2>
        <div className="ma-niif-marco" role="group" aria-label="Marco contable">
          <button type="button" className="ma-niif-tab activa" disabled aria-pressed="true" title={`Disponible en ${META.sp}`}>
            NIIF completas
          </button>
          <button type="button" className="ma-niif-tab" disabled aria-pressed="false" title={`Disponible en ${META.sp}`}>
            NIIF para las PYMES
          </button>
        </div>
        <button type="button" className="ma-boton" onClick={() => ir("portada")}>
          ← Volver a la portada
        </button>
      </div>

      <p className="ma-niif-intro">
        Comprueba que lo que el cliente dice aplicar coincide con lo que registró, recalcula las estimaciones y genera el
        manual de políticas contables. El juicio sobre las estimaciones es del auditor (NIA 540).
      </p>

      <EnConstruccion sp={META.sp} />

      <nav className="ma-niif-nav" aria-label="Secciones de la página">
        <a href="#niif-manual">Manual de políticas</a>
        <a href="#niif-matriz">Política vs registro</a>
        <a href="#niif-estimaciones">Estimaciones</a>
        <a href="#niif-revelaciones">Revelaciones y NIC 8</a>
      </nav>

      <section id="niif-manual" aria-label="Generador de manuales de políticas contables" className="ma-tarjeta ma-niif-seccion">
        <div className="ma-niif-titulo-fila">
          <h3>Manual de políticas contables</h3>
          <span className="ma-niif-badge">Por construir</span>
          <span className="ma-niif-biblioteca">
            Biblioteca: <span className="ma-sindatos">sin datos</span> fichas de NIIF para las PYMES
          </span>
        </div>

        <div className="ma-grid ma-niif-pasos">
          {PASOS.map((p) => (
            <div className="ma-tarjeta" key={p.n}>
              <span className="ma-niif-paso-n">{p.n}</span>
              <span className="ma-niif-paso-titulo">{p.titulo}</span>
              <span className="ma-niif-paso-texto">{p.texto}</span>
            </div>
          ))}
        </div>

        <div className="ma-niif-rubros">
          <div className="ma-niif-titulo-fila">
            <h4>Rubros que incluye el manual · NIIF para las PYMES</h4>
            <span className="ma-niif-nota">Disponible en {META.sp} · marca solo lo que aplica al cliente</span>
          </div>
          <div className="ma-niif-rubros-grid">
            {SECCIONES_PYMES.map(([cod, nombre]) => (
              <label className="ma-niif-rubro" key={cod}>
                <input type="checkbox" disabled />
                <span className="ma-niif-rubro-cod">{cod}</span>
                <span>{nombre}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="ma-niif-manual-grid">
          <div className="ma-tarjeta">
            <h4>Decisiones de política que pregunta el generador</h4>
            {DECISIONES.map((d) => (
              <div className="ma-niif-decision" key={d.pregunta}>
                <span>{d.pregunta}</span>
                <span className="ma-niif-decision-opciones">{d.opciones}</span>
              </div>
            ))}
          </div>
          <div className="ma-tarjeta">
            <h4>Cada ficha de la biblioteca (.md)</h4>
            <ul className="ma-niif-lista">
              <li>Alcance y definiciones clave, redactados por la firma</li>
              <li>Opciones de política que permite la norma</li>
              <li>Texto modelo de la política para cada opción</li>
              <li>Revelaciones que exige, con referencia al párrafo</li>
              <li>Diferencias entre completas y PYMES</li>
              <li>Particularidades de Ecuador (Supercias, SRI)</li>
            </ul>
            <div className="ma-niif-botones">
              <button type="button" className="ma-boton" disabled title={`Disponible en ${META.sp}`}>
                Generar manual (Word)
              </button>
              <button type="button" className="ma-boton" disabled title={`Disponible en ${META.sp}`}>
                Vista previa
              </button>
              <span className="ma-niif-nota">Disponible en {META.sp}</span>
            </div>
          </div>
        </div>
      </section>

      <section id="niif-matriz" aria-label="Política contra registro" className="ma-tarjeta ma-niif-seccion">
        <div className="ma-niif-titulo-fila">
          <h3>Política contra registro</h3>
          <span className="ma-niif-nota">El manual aprobado se vuelve la regla que el motor compara con el mayor</span>
        </div>
        <div className="ma-grid">
          {MATRIZ.map((m) => (
            <div className="ma-tarjeta" key={m.norma + m.rubro}>
              <span className="ma-niif-norma">{m.norma}</span>
              <span className="ma-niif-rubro-nombre">{m.rubro}</span>
              <span className="ma-niif-ejemplo">{m.ejemplo}</span>
            </div>
          ))}
        </div>
      </section>

      <section id="niif-estimaciones" aria-label="Estimaciones" className="ma-tarjeta ma-niif-seccion">
        <h3>Recalcular estimaciones · NIA 540</h3>
        <div className="ma-tabla-wrap">
          <table className="ma-tabla">
            <thead>
              <tr>
                <th scope="col">Norma</th>
                <th scope="col">Qué recalcula o busca</th>
                <th scope="col">Excepción típica</th>
                <th scope="col">Estado</th>
              </tr>
            </thead>
            <tbody>
              {ESTIMACIONES.map((e) => (
                <tr key={e.norma + e.que}>
                  <td>{e.norma}</td>
                  <td>{e.que}</td>
                  <td>{e.excepcion}</td>
                  <td>
                    <span className={`ma-niif-estado ma-niif-estado-${e.estado}`}>{ETIQUETA_ESTADO[e.estado]}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section id="niif-revelaciones" aria-label="Revelaciones y cambios de política" className="ma-grid ma-niif-revelaciones">
        <div className="ma-tarjeta">
          <h3>Checklist de revelaciones</h3>
          <p>
            Revisa que las notas traigan lo que exige cada norma marcada en el manual; la salida es la lista de lo que
            falta revelar.
          </p>
          <div className="ma-niif-etiquetas">
            {REVELACIONES.map((r) => (
              <span className="ma-niif-etiqueta" key={r}>
                {r}
              </span>
            ))}
          </div>
        </div>
        <div className="ma-tarjeta">
          <h3>Cambios de política y errores · NIC 8</h3>
          <p>
            Compara el manual del año con el del anterior. Si una política cambió, verifica que exista la reexpresión o
            la nota que lo explique.
          </p>
          <span className="ma-niif-badge">Por construir</span>
        </div>
      </section>
    </section>
  );
}
