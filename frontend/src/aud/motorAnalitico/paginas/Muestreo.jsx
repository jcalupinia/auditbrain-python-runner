import { PAGINAS } from "../paginas.js";
import "./Muestreo.css";

const META = PAGINAS.find((p) => p.id === "muestras");

const FUENTES = [
  { clave: "gastos", nombre: "Mayor de gastos", detalle: "Cuentas 5",
    documentos: ["Factura electrónica autorizada", "Comprobante de pago", "Orden de compra y recepción", "Contrato cuando aplique"] },
  { clave: "eri", nombre: "Estado de resultados", detalle: "Detallado por cuenta",
    documentos: ["Mayor de la cuenta", "Soporte del asiento", "Conciliación con el auxiliar"] },
  { clave: "ventas", nombre: "Ventas", detalle: "XML emitidos",
    documentos: ["Factura y guía de remisión", "Cobro o estado de cuenta del cliente", "Contrato u orden del cliente"] },
  { clave: "compras", nombre: "Compras", detalle: "XML recibidos",
    documentos: ["Factura autorizada", "Comprobante de retención", "Recepción en bodega"] },
  { clave: "importaciones", nombre: "Importaciones", detalle: "Declaraciones aduaneras",
    documentos: ["Declaración aduanera (SENAE)", "Factura del exterior", "Liquidación del agente de aduanas", "Pago y retención o ISD"] },
  { clave: "otra", nombre: "Otra base", detalle: "Excel o CSV",
    documentos: ["Soporte según la naturaleza de la partida"] },
];

const METODOS = [
  { n: "A", titulo: "Partidas clave", texto: "Todo lo que supera el umbral entra al 100 %, fuera del muestreo.",
    criterio: "Importe ≥ materialidad de ejecución", estado: "Por construir", listo: false },
  { n: "B", titulo: "Valores atípicos", texto: "Partidas fuera del patrón de su cuenta, tercero o mes.",
    criterio: "GAS-006 · desvío frente a la cuenta", estado: "En el motor", listo: true },
  { n: "C", titulo: "Selección dirigida",
    texto: "Partes relacionadas, fin de período, glosas genéricas, asientos manuales, cuentas sensibles.",
    criterio: "Criterios del auditor", estado: "Por construir", listo: false },
  { n: "D", titulo: "Muestreo estadístico", texto: "Sobre el resto de la población: MUS o aleatorio estratificado.",
    criterio: "MUS · NIA 530", estado: "En el motor", listo: true },
];

const DEMO_CAMPOS = [
  "Valor de la población", "Confianza", "Intervalo de muestreo", "Semilla",
  "Selección cierta", "Selección sistemática", "Tamaño de la muestra", "Cobertura del valor",
];

const FUENTE_DEFECTO = FUENTES[0];

export default function Muestreo({ ir, EnConstruccion }) {
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
            Combina partidas clave, valores atípicos, selección dirigida y muestreo estadístico sobre cualquier base.
            Todo queda documentado con semilla y cobertura (NIA 530).
          </p>
        </div>
        <button type="button" className="ma-boton" onClick={() => ir("portada")}>
          ← Volver a la portada
        </button>
      </div>

      <EnConstruccion sp={META.sp} />

      <div className="ma-grid ma-muestras-cols2">
        <section aria-label="Fuente" className="ma-tarjeta ma-muestras-seccion">
          <h3>1 · Qué quieres muestrear</h3>
          <div className="ma-muestras-fuentes">
            {FUENTES.map((f) => (
              <button
                type="button"
                key={f.clave}
                disabled
                aria-pressed={f.clave === FUENTE_DEFECTO.clave}
                className={f.clave === FUENTE_DEFECTO.clave ? "ma-muestras-fuente activa" : "ma-muestras-fuente"}
                title={`Disponible en ${META.sp}`}
              >
                <span className="ma-muestras-fuente-nombre">{f.nombre}</span>
                <span className="ma-muestras-fuente-detalle">{f.detalle}</span>
              </button>
            ))}
          </div>
        </section>

        <section aria-label="Parámetros" className="ma-tarjeta ma-muestras-seccion">
          <h3>2 · Parámetros del encargo</h3>
          <div className="ma-muestras-parametros">
            <label>
              Materialidad de ejecución (USD)
              <input type="text" inputMode="decimal" placeholder="[DEL ENCARGO]" disabled />
            </label>
            <label>
              Error tolerable (USD)
              <input type="text" inputMode="decimal" placeholder="≤ materialidad de ejecución" disabled />
            </label>
            <label>
              Nivel de confianza
              <select disabled defaultValue="95">
                <option value="95">95 %</option>
                <option value="90">90 %</option>
                <option value="80">80 %</option>
                <option value="99">99 %</option>
              </select>
            </label>
            <label>
              Semilla (obligatoria)
              <input type="text" inputMode="numeric" placeholder="p. ej. fecha del encargo" disabled />
            </label>
          </div>
        </section>
      </div>

      <section aria-label="Métodos" className="ma-tarjeta ma-muestras-seccion">
        <div className="ma-muestras-titulo-fila">
          <h3>3 · Métodos (se combinan en este orden)</h3>
          <span className="ma-muestras-nota">Una partida elegida por un método no se repite en los siguientes</span>
        </div>
        <div className="ma-grid ma-muestras-metodos">
          {METODOS.map((m) => (
            <label key={m.n} className="ma-tarjeta ma-muestras-metodo">
              <div className="ma-muestras-metodo-fila">
                <input type="checkbox" disabled />
                <span className="ma-muestras-metodo-n">{m.n}</span>
                <span className={m.listo ? "ma-muestras-metodo-estado listo" : "ma-muestras-metodo-estado nuevo"}>
                  {m.estado}
                </span>
              </div>
              <span className="ma-muestras-metodo-titulo">{m.titulo}</span>
              <span className="ma-muestras-metodo-texto">{m.texto}</span>
              <span className="ma-muestras-metodo-criterio">{m.criterio}</span>
            </label>
          ))}
        </div>
        <div className="ma-muestras-titulo-fila">
          <span className="ma-muestras-resumen">
            Métodos activos: <span className="ma-sindatos">sin datos</span>
          </span>
          <button type="button" className="ma-boton ma-muestras-cta" disabled title={`Disponible en ${META.sp}`}>
            Seleccionar muestra
          </button>
        </div>
      </section>

      <div className="ma-grid ma-muestras-cols-1-6-1">
        <section aria-label="Cédula de selección" className="ma-tarjeta ma-muestras-seccion ma-muestras-cedula">
          <div className="ma-muestras-titulo-fila">
            <h3>4 · Cédula de selección</h3>
            <span className="ma-muestras-nota">Estructura; las partidas aparecen al seleccionar sobre el encargo</span>
            <button type="button" className="ma-boton" disabled title={`Disponible en ${META.sp}`}>
              Exportar a Excel
            </button>
          </div>
          <div className="ma-tabla-wrap">
            <table className="ma-tabla">
              <thead>
                <tr>
                  <th scope="col">N.º</th>
                  <th scope="col">Método</th>
                  <th scope="col">Cuenta</th>
                  <th scope="col">Tercero</th>
                  <th scope="col">Fecha</th>
                  <th scope="col">Importe</th>
                  <th scope="col">Motivo</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colSpan={7} className="ma-sindatos">
                    sin datos
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <div className="ma-muestras-col">
          <section aria-label="Documentos a solicitar" className="ma-tarjeta ma-muestras-seccion">
            <h3>5 · Documentos a pedir al cliente</h3>
            <span className="ma-muestras-nota">Se generan por partida según la base elegida</span>
            <ul className="ma-muestras-lista">
              {FUENTE_DEFECTO.documentos.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
            <button type="button" className="ma-boton" disabled title={`Disponible en ${META.sp}`}>
              Generar solicitud
            </button>
          </section>

          <section aria-label="Ejemplo real del demo" className="ma-tarjeta ma-muestras-seccion">
            <div className="ma-muestras-titulo-fila">
              <h3>MUS · ejercicio de demostración</h3>
            </div>
            <div className="ma-muestras-demo">
              {DEMO_CAMPOS.map((campo) => (
                <div className="ma-muestras-demo-campo" key={campo}>
                  <span className="ma-muestras-nota">{campo}</span>
                  <span className="ma-sindatos">sin datos</span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>

      <section aria-label="Evaluación" className="ma-tarjeta ma-muestras-seccion ma-muestras-evaluacion">
        <div>
          <h3>6 · Evaluación de la muestra</h3>
          <p>
            Registras los errores encontrados en cada partida y el motor calcula el límite superior de error contra el
            tolerable (precisión básica + error proyectado + margen incremental). Las subvaloraciones se informan
            aparte. La conclusión es del auditor.
          </p>
        </div>
        <button type="button" className="ma-boton" disabled title={`Disponible en ${META.sp}`}>
          Registrar resultados
        </button>
      </section>
    </section>
  );
}
