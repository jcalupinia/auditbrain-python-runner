import { useState } from "react";
import { PAGINAS } from "../paginas.js";
import "./RevisionAgentes.css";

// Transcripción de RevisionAgentes.dc.html (Task 4). Bloques del lienzo →
// bloques del JSX: 1) migas + cabecera (título, chip "Boceto · SPx", botón
// volver); 2) <EnConstruccion /> (regla #5, además del chip del lienzo);
// 3) nav de agentes; 4) columna de propuestas pendientes; 5) columna de
// detalle (lo que calculó el motor + propuesta del agente + borrador);
// 6) columna de decisión (comentario + 3 botones) + bitácora.
//
// Cifras de demostración (montos, conteos de pendientes) → «sin datos»
// (regla #4). Reglas, prioridades, normas (NIA) y roles se conservan.

const META = PAGINAS.find((p) => p.id === "agentes");

const AGENTES = [
  { id: "forense", nombre: "Forense de asientos", disponible: true },
  { id: "conciliador", nombre: "Conciliador y proveedores", disponible: true },
  { id: "tributario", nombre: "Tributario SRI", disponible: false, sp: "SP6" },
  { id: "financiero", nombre: "Analista financiero", disponible: false, sp: "SP10" },
  { id: "niif", nombre: "Revisor NIIF", disponible: false, sp: "SP12" },
  { id: "redactor", nombre: "Redactor de hallazgos", disponible: false, sp: "SP8" },
];

const DATOS = {
  forense: {
    nombre: "Forense de asientos",
    propuestas: [
      {
        prioridad: "P0",
        reglas: "AST-001 · 004 · VTA-009",
        accion: "Elevar",
        resumen: (
          <>
            Asiento manual de <span className="ma-sindatos">sin datos</span> a ingresos, glosa «ajuste», registrado
            después del cierre.
          </>
        ),
        titulo: "Asiento manual a ingresos registrado tras el cierre",
        confianza: "alta",
        evidencia: [
          { campo: "Monto expuesto", valor: "sin datos", sinDatos: true },
          { campo: "Origen", valor: "Manual" },
          { campo: "Glosa", valor: "«ajuste»" },
          { campo: "Reglas coincidentes", valor: "AST-001, AST-004, VTA-009" },
          { campo: "Norma", valor: "NIA 240 párr. 32(a)" },
          { campo: "Evidencia", valor: "SHA-256 · 64 caracteres" },
        ],
        justificacion:
          "Tres reglas distintas señalan el mismo asiento: es manual, afecta ingresos, se registró fuera del período de cierre y no tiene comprobante de venta que lo respalde. Propongo elevarlo y pedir al cliente el soporte y la autorización.",
        borrador: [
          { parte: "Condición", texto: "Se registró manualmente un ingreso sin comprobante de venta, con glosa genérica, después del cierre del ejercicio." },
          { parte: "Criterio", texto: "Los ingresos se reconocen con documento de soporte y dentro del período (NIIF 15 / Sec. 23); NIA 240 párr. 32(a)." },
          { parte: "Causa", texto: "[A confirmar con el cliente]" },
          { parte: "Efecto", texto: "Posible sobrestimación de ingresos por el monto calculado por el motor." },
        ],
        traza: "gpt-oss-20b (local) · plantilla forense v1 · entrada seudonimizada",
      },
      {
        prioridad: "P2",
        reglas: "AST-002",
        accion: "Descartar",
        resumen: "Asientos de fin de semana del mismo usuario en la semana de cierre mensual.",
        titulo: "Asientos en fin de semana durante el cierre mensual",
        confianza: "media",
        evidencia: [
          { campo: "Regla", valor: "AST-002" },
          { campo: "Patrón", valor: "Semana de cierre mensual" },
          { campo: "Norma", valor: "NIA 240" },
          { campo: "Evidencia", valor: "SHA-256 · 64 caracteres" },
        ],
        justificacion:
          "El patrón coincide con el calendario de cierre mensual y no concurre con otras reglas sobre las mismas entidades. Propongo descartarlos como agrupación, dejando fundamento.",
        borrador: [{ parte: "Condición", texto: "No aplica: propuesta de descarte." }],
        traza: "gpt-oss-20b (local) · plantilla forense v1 · entrada seudonimizada",
      },
    ],
  },
  conciliador: {
    nombre: "Conciliador y proveedores",
    propuestas: [
      {
        prioridad: "P0",
        reglas: "PRV-002 · PRV-003",
        accion: "Elevar",
        resumen: "Proveedor cuyo RUC y cuenta bancaria coinciden con los de un empleado.",
        titulo: "Proveedor vinculado a un empleado",
        confianza: "alta",
        evidencia: [
          { campo: "Reglas coincidentes", valor: "PRV-002, PRV-003" },
          { campo: "Norma", valor: "NIA 240; NIA 550 si es personal clave" },
          { campo: "Evidencia", valor: "SHA-256 · 64 caracteres" },
        ],
        justificacion:
          "Dos reglas distintas vinculan al proveedor con un empleado por identificación y cuenta bancaria. Propongo elevarlo y revisar los pagos y su sustento.",
        borrador: [
          { parte: "Condición", texto: "Un proveedor comparte identificación y cuenta bancaria con un empleado." },
          { parte: "Criterio", texto: "Segregación de funciones y control de proveedores (NIA 240, NIA 315)." },
          { parte: "Causa", texto: "[A confirmar con el cliente]" },
          { parte: "Efecto", texto: "Riesgo de pagos sin operación real." },
        ],
        traza: "gpt-oss-20b (local) · plantilla conciliador v1 · entrada seudonimizada",
      },
    ],
  },
};

export default function RevisionAgentes({ ir, EnConstruccion }) {
  const [agenteId, setAgenteId] = useState("forense");
  const [propuestaIdx, setPropuestaIdx] = useState(0);

  const actual = DATOS[agenteId] || DATOS.forense;
  const propuestas = actual.propuestas;
  const sel = propuestas[propuestaIdx] || propuestas[0];
  const accionSel = sel.accion === "Elevar" ? "elevar a hallazgo" : "descartar";
  const bitacora = [
    "El motor generó la excepción y su evidencia",
    `El agente propuso ${sel.accion === "Elevar" ? "elevar" : "descartar"} con la plantilla v1`,
    "Pendiente: decisión del gerente",
  ];

  function elegirAgente(id, disponible) {
    if (!disponible) return;
    setAgenteId(id);
    setPropuestaIdx(0);
  }

  return (
    <section className="ma-pagina ma-agentes">
      <div className="ma-agentes-migas">
        <button type="button" className="link" onClick={() => ir("portada")}>
          Motor de Auditoría Analítica
        </button>
        <span>/</span> <b>Revisión con agentes</b>
      </div>

      <div className="ma-agentes-cab">
        <div className="ma-agentes-titulo">
          <h1>Revisión con agentes</h1>
          <p>
            Los agentes proponen y explican; el motor aporta las cifras y la evidencia; el gerente decide. Ninguna
            propuesta cambia el estado sin tu aprobación.
          </p>
        </div>
        <span className="ma-agentes-chip">Boceto · SP8</span>
        <button type="button" className="ma-boton" onClick={() => ir("portada")}>
          ← Volver a la portada
        </button>
      </div>

      <EnConstruccion sp={META.sp} />

      <nav aria-label="Agentes" className="ma-agentes-nav">
        {AGENTES.map((a) => {
          const datosAgente = DATOS[a.id];
          const pendientes = datosAgente ? "sin datos" : a.sp;
          return (
            <button
              key={a.id}
              type="button"
              aria-pressed={a.id === agenteId}
              className={a.id === agenteId ? "ma-agentes-agente activo" : "ma-agentes-agente"}
              disabled={!a.disponible}
              onClick={() => elegirAgente(a.id, a.disponible)}
            >
              <span>{a.nombre}</span>
              <span className={a.disponible ? "ma-agentes-contador disponible" : "ma-agentes-contador"}>
                {a.disponible ? <span className="ma-sindatos">{pendientes}</span> : pendientes}
              </span>
            </button>
          );
        })}
      </nav>

      <div className="ma-agentes-grid">
        <section aria-label="Propuestas pendientes" className="ma-tarjeta ma-agentes-lista">
          <div className="ma-agentes-lista-cab">
            <h2>Propuestas del agente</h2>
            <span>{actual.nombre}</span>
          </div>
          {propuestas.map((p, i) => (
            <button
              key={i}
              type="button"
              className={i === propuestaIdx ? "ma-agentes-propuesta activa" : "ma-agentes-propuesta"}
              onClick={() => setPropuestaIdx(i)}
            >
              <div className="ma-agentes-propuesta-cab">
                <span className={`ma-sev-${p.prioridad}`}>{p.prioridad}</span>
                <span className="ma-agentes-propuesta-reglas">{p.reglas}</span>
                <span className={p.accion === "Elevar" ? "ma-agentes-accion elevar" : "ma-agentes-accion descartar"}>
                  {p.accion}
                </span>
              </div>
              <span className="ma-agentes-propuesta-resumen">{p.resumen}</span>
            </button>
          ))}
        </section>

        <section aria-label="Detalle de la propuesta" className="ma-tarjeta ma-agentes-detalle">
          <div className="ma-agentes-detalle-cab">
            <span className={`ma-sev-${sel.prioridad}`}>{sel.prioridad}</span>
            <h2>{sel.titulo}</h2>
          </div>

          <div className="ma-agentes-bloque motor">
            <h3>Lo que calculó el motor</h3>
            <div className="ma-agentes-evidencia">
              {sel.evidencia.map((e) => (
                <div key={e.campo}>
                  <span>{e.campo}</span>
                  <span className={e.sinDatos ? "ma-sindatos" : undefined}>{e.valor}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="ma-agentes-bloque propuesta">
            <div className="ma-agentes-bloque-cab">
              <h3>Propuesta del agente: {accionSel}</h3>
              <span>Confianza: {sel.confianza}</span>
            </div>
            <p>{sel.justificacion}</p>
            <div className="ma-agentes-borrador">
              <span>Borrador de observación (Condición · Criterio · Causa · Efecto)</span>
              {sel.borrador.map((b) => (
                <div key={b.parte}>
                  <strong>{b.parte}</strong>
                  <span>{b.texto}</span>
                </div>
              ))}
            </div>
            <span className="ma-agentes-traza">{sel.traza}</span>
          </div>
        </section>

        <aside aria-label="Decisión" className="ma-agentes-decision">
          <section className="ma-tarjeta">
            <h2>Tu decisión</h2>
            <label htmlFor="ma-agentes-comentario">Comentario (obligatorio para descartar)</label>
            <textarea id="ma-agentes-comentario" rows={5} placeholder="Fundamento de la decisión" />
            <button type="button" className="ma-boton ma-agentes-elevar" disabled title="Disponible en SP8">
              Elevar a hallazgo
            </button>
            <button type="button" className="ma-boton" disabled title="Disponible en SP8">
              Descartar con fundamento
            </button>
            <button type="button" className="ma-boton" disabled title="Disponible en SP8">
              Pedir más evidencia
            </button>
          </section>
          <section className="ma-tarjeta">
            <h2>Bitácora</h2>
            {bitacora.map((b, i) => (
              <div className="ma-agentes-bitacora-linea" key={i}>
                <span aria-hidden="true" />
                <span>{b}</span>
              </div>
            ))}
          </section>
        </aside>
      </div>
    </section>
  );
}
