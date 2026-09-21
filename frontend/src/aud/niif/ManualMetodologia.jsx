import manualHtml from "./sitio/documentos/Manual_Arquitectura_AuditBrain.html?url";
import manualMd from "./sitio/documentos/Manual_Arquitectura_AuditBrain.md?url";
import memoriaJson from "./sitio/documentos/Memoria_Metodologica_AuditBrain.json?url";
import memoriaMd from "./sitio/documentos/Memoria_Metodologica_AuditBrain.md?url";
import { METHODOLOGY_DATE, METHODOLOGY_VERSION, manualSections, methodologyRules } from "./sitio/methodology.mjs";

/*
 * Manual y memoria — puerto de auditbrain-site/app/metodologia/page.tsx.
 *
 * El contenido sale entero de sitio/methodology.mjs (copia intacta) y los
 * descargables son los documentos que genera el sitio, copiados tal cual. Si
 * el sitio sube de versión, se vuelven a copiar los dos.
 *
 * Adaptaciones al portal: el índice desplaza la vista en lugar de cambiar la
 * URL, «Crear herramienta» lleva a «Diseñar fichas», y la memoria se pega «en su
 * asistente de IA» en vez de «en ChatGPT».
 */

const ir = (id) => document.getElementById("nf-manual-" + id)?.scrollIntoView({ block: "start" });

function Parrafo({ text }) {
  return (
    <p>
      {text.split(/(https:\/\/[^\s]+)/g).map((part, i) =>
        part.startsWith("https://") ? (
          <a key={i} href={part} target="_blank" rel="noreferrer">{part}</a>
        ) : (
          part
        )
      )}
    </p>
  );
}

export default function ManualMetodologia({ onCrear }) {
  return (
    <div className="nf-manual" id="nf-manual-inicio">
      <header className="nf-rec-panel">
        <p className="nf-eyebrow">BIBLIOTECA METODOLÓGICA · V{METHODOLOGY_VERSION}</p>
        <h3>
          Una arquitectura.
          <br />
          <em>Cada prueba, con su criterio.</em>
        </h3>
        <p>El manual y la memoria que guían la construcción de herramientas de auditoría en AuditBrain.</p>
        <small className="muted">Registrado el {METHODOLOGY_DATE} · Referencia: Obligaciones Fiscales</small>
        <div className="nf-estudio-botones">
          <a className="btn sm primary" href={manualHtml} target="_blank" rel="noreferrer">Abrir manual para imprimir ↗</a>
          <a className="btn sm" download="Manual_Arquitectura_AuditBrain.md" href={manualMd}>Descargar manual ↓</a>
          <a className="btn sm" download="Memoria_Metodologica_AuditBrain.md" href={memoriaMd}>Descargar memoria ↓</a>
        </div>
      </header>

      <section className="nf-nota">
        <strong>Primero: ¿NIIF para las PYMES o NIIF completas?</strong>
        <p>
          El marco, su edición y la vigencia determinan la metodología. Si están pendientes, el constructor debe
          aclararlos antes de calcular. No se resuelve cambiando únicamente el título del archivo.
        </p>
        {onCrear && (
          <button type="button" className="link" onClick={onCrear}>Crear herramienta con esta metodología →</button>
        )}
      </section>

      <div className="nf-manual-flujo" aria-label="Distribución de responsabilidades">
        <div><span>01 · DISEÑAR</span><h4>AuditBrain</h4><p>Conversación, investigación, requerimientos y cédulas.</p></div>
        <div><span>02 · IMPLEMENTAR</span><h4>GitHub / Python</h4><p>Código versionado, fórmulas, validaciones y pruebas.</p></div>
        <div><span>03 · EJECUTAR</span><h4>AUDIT-IA</h4><p>Carga, procesamiento, revisión, descarga y encerado.</p></div>
      </div>
      <p className="muted">
        Este manual define la arquitectura objetivo. Las funciones pendientes están identificadas en «Estado»;
        registrar la memoria no las implementa automáticamente.
      </p>

      <nav className="nf-rec-panel nf-manual-indice" aria-label="Índice del manual">
        <h4>Consultar el manual</h4>
        <div>
          {manualSections.map((s) => (
            <button key={s.id} type="button" className="link" onClick={() => ir(s.id)}>{s.title}</button>
          ))}
          <button type="button" className="link" onClick={() => ir("reglas")}>
            20 · Memoria {methodologyRules[0][0]}–{methodologyRules[methodologyRules.length-1][0]}
          </button>
        </div>
      </nav>

      <article>
        {manualSections.map((s) => (
          <section className="nf-rec-panel nf-manual-seccion" id={"nf-manual-" + s.id} key={s.id}>
            <h4>{s.title}</h4>
            {s.paragraphs.map((p, i) => <Parrafo key={i} text={p} />)}
            {s.headers.length > 0 && (
              <div className="nf-estudio-scroll nf-estudio-tabla" tabIndex={0} role="region" aria-label={"Tabla: " + s.title}>
                <table>
                  <thead><tr>{s.headers.map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
                  <tbody>
                    {s.rows.map((r, i) => (
                      <tr key={i}>
                        {r.map((c, j) => (j === 0 ? <th scope="row" key={j}>{c}</th> : <td key={j}>{c}</td>))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {s.items.length > 0 && <ul>{s.items.map((item, i) => <li key={i}>{item}</li>)}</ul>}
            <button type="button" className="link" onClick={() => ir("inicio")}>Volver al inicio ↑</button>
          </section>
        ))}
      </article>

      <section className="nf-rec-panel nf-manual-seccion" id="nf-manual-reglas">
        <h4>20 · Memoria que acompaña al constructor</h4>
        <p>
          Estas reglas se incluyen en la ficha descargable y en la consulta que copia para el agente. Debe pegar esa
          consulta en su asistente de IA para transmitirlas; esta página no cambia por sí sola la configuración del
          agente.
        </p>
        <div className="nf-manual-reglas">
          {methodologyRules.map(([id, title, body]) => (
            <div key={id}><span>{id}</span><h5>{title}</h5><p>{body}</p></div>
          ))}
        </div>
        <a className="btn sm" download="Memoria_Metodologica_AuditBrain.json" href={memoriaJson}>Descargar memoria estructurada JSON ↓</a>
      </section>
    </div>
  );
}
