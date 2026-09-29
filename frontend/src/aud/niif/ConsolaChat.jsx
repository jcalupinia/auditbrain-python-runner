import { useCallback, useEffect, useState } from "react";

import * as api from "../../api";
import { ChipDocumento } from "./CicloVista";
import { ConsolaRevision } from "./ConsolaRevision";
import { aprobar, devolver, enviar, prepararBaseTecnica, producir } from "./cicloOrquestacion";
import { claseMensaje, nombreDe, puedeSubirInline, requerimientosPendientes } from "./consolaChatVista";

/*
 * Consola-chat del piloto de planificación (100% conversacional, dos modos en la
 * misma consola). Un agente determinista (servidor) guía el proceso en un hilo de
 * mensajes tipo chat:
 *  - «Preparador»: sube los documentos que el agente pide, produce la planificación
 *    (preparar base técnica → mapear → validar → configurar → aprobar metodología →
 *    ejecutar → analizar) y la envía a revisión, todo desde aquí.
 *  - «Auditor»: ve el veredicto del recálculo independiente y aprueba o devuelve.
 * Las respuestas de gobierno del encargo (independencia, enfoque por ciclo) se
 * resuelven automáticamente por política de la firma y no se preguntan aquí.
 */

const paramDe = (prueba) => ({ ...(prueba.definicion.parametros || {}), ...(prueba.registro.parameters || {}) });

export function ConsolaChat({ prueba, onRecargar }) {
  const esPlan = prueba.definicion.processor === "planificacion_nia";
  const cosa = esPlan ? "la planificación" : "la prueba";
  const Cosa = esPlan ? "La planificación" : "La prueba";
  const [rol, setRol] = useState("preparador");
  const [guion, setGuion] = useState(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState("");
  const [conclusion, setConclusion] = useState("");
  const [confirmo, setConfirmo] = useState(false);
  const [motivo, setMotivo] = useState("");

  const cargar = useCallback(async () => {
    setError("");
    try {
      setGuion(await api.cicloConsolaChat(prueba.id, rol));
    } catch (e) {
      setError(e.message || String(e));
    }
  }, [prueba.id, rol]);

  useEffect(() => { cargar(); }, [cargar]);

  async function correr(fn, textoAviso) {
    setOcupado(true);
    setError("");
    setAviso(textoAviso || "");
    try {
      await fn();
      await onRecargar?.();
      await cargar();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setOcupado(false);
      setAviso("");
    }
  }

  const cobertura = prueba.cobertura || [];
  const pendientes = requerimientosPendientes(prueba, cobertura);
  const cobIdx = Object.fromEntries(cobertura.map((c) => [c.id, c]));
  const sig = guion?.siguiente || {};

  return (
    <section className="nf-chat">
      <div className="nf-chat-cab">
        <p className="nf-eyebrow" style={{ margin: 0 }}>
          {esPlan ? "CONSOLA DE PLANIFICACIÓN · PILOTO" : `CONSOLA DE LA PRUEBA · ${prueba.definicion.name?.toUpperCase() || ""}`}
        </p>
        <div className="nf-chat-roles" role="tablist" aria-label="Lado de la consola">
          {[["preparador", "Preparador"], ["auditor", "Auditor"]].map(([v, l]) => (
            <button key={v} type="button" role="tab" aria-selected={rol === v}
              className={rol === v ? "btn sm primary" : "btn sm"} onClick={() => setRol(v)}>
              {l}
            </button>
          ))}
        </div>
      </div>

      {error && <p role="alert" className="nf-error">{error}</p>}

      <div className="nf-chat-hilo">
        {(guion?.mensajes || []).map((m, i) => (
          <div key={i} className={`nf-chat-msg ${claseMensaje(m.de)}`}>
            <span className="nf-chat-de">{nombreDe(m.de)}</span>
            <p>{m.texto}</p>
          </div>
        ))}
        {aviso && <div className="nf-chat-msg nf-chat-sys"><p>{aviso}</p></div>}
      </div>

      {sig.accion && (
        <div className="nf-chat-accion">
          {/* Preparador · subir documentos inline */}
          {sig.accion === "subir" && (
            puedeSubirInline(prueba) ? (
              <div className="pc-scenarios">
                <span className="pc-scenarios-l" style={{ color: "var(--accent)" }}>SUBIR DOCUMENTOS</span>
                {pendientes.map((r) => (
                  <ChipDocumento key={r.id} prueba={prueba} req={r} cobertura={cobIdx[r.id]}
                    onSubido={async () => { await onRecargar?.(); await cargar(); }} habilitado={!ocupado}
                    processor={prueba.definicion.processor} />
                ))}
                {pendientes.length === 0 && (
                  <button type="button" className="btn primary" disabled={ocupado}
                    onClick={() => correr(() => producir(prueba, { param: paramDe(prueba) }), `Produciendo ${cosa}…`)}>
                    {esPlan ? "Producir la planificación" : "Producir la prueba"}
                  </button>
                )}
              </div>
            ) : (
              <button type="button" className="btn primary" disabled={ocupado}
                onClick={() => correr(() => prepararBaseTecnica(prueba), "Preparando el requerimiento de documentos…")}>
                Preparar el requerimiento de documentos
              </button>
            )
          )}

          {/* Preparador · producir */}
          {sig.accion === "procesar" && (
            <button type="button" className="btn primary" disabled={ocupado}
              onClick={() => correr(() => producir(prueba, { param: paramDe(prueba) }), `Produciendo ${cosa}…`)}>
              {sig.etiqueta}
            </button>
          )}

          {/* Preparador · enviar a revisión (con conclusión) */}
          {sig.accion === "enviar" && (
            <div>
              <label className="nf-ctx-field">
                Conclusión preliminar para el auditor
                <textarea rows={3} value={conclusion} onChange={(e) => setConclusion(e.target.value)}
                  placeholder={esPlan ? "Resumen de la planificación: enfoque, riesgos altos y materialidad."
                    : "Resumen del trabajo: saldo auditado, ajuste propuesto y hallazgos principales."} />
              </label>
              <button type="button" className="btn primary" disabled={ocupado || conclusion.trim().length < 10}
                onClick={() => correr(() => enviar(prueba, { conclusion }), "Enviando a revisión del auditor…")}>
                Enviar a revisión del auditor
              </button>
            </div>
          )}

          {/* Auditor · revisar (veredicto inline) */}
          {sig.accion === "revisar" && <ConsolaRevision prueba={prueba} />}

          {/* Auditor · aprobar (con veredicto y confirmación) */}
          {sig.accion === "aprobar" && (
            <>
              <ConsolaRevision prueba={prueba} />
              <label className="nf-ctx-check">
                <input type="checkbox" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} /> Revisé el
                veredicto y la conclusión, y las confirmo (compuerta del socio).
              </label>
              <button type="button" className="btn primary" disabled={ocupado || !confirmo}
                onClick={() => correr(() => aprobar(prueba, { conclusion: prueba.registro.conclusion || "", conclusionReviewed: true }),
                  `Aprobando ${cosa}…`)}>
                {esPlan ? "Aprobar la planificación" : "Aprobar la prueba"}
              </button>
            </>
          )}

          {/* Auditor · devolver al preparador */}
          {sig.accion === "devolver" && (
            <>
              <ConsolaRevision prueba={prueba} />
              <label className="nf-ctx-field">
                Motivo de la devolución (mínimo 10 caracteres)
                <input value={motivo} onChange={(e) => setMotivo(e.target.value)} />
              </label>
              <button type="button" className="btn" disabled={ocupado || motivo.trim().length < 10}
                onClick={() => correr(() => devolver(prueba, { comment: motivo }), "Devolviendo al preparador…")}>
                Devolver al preparador
              </button>
            </>
          )}

          {sig.accion === "esperar" && (
            <p className="muted">{Cosa} está con el auditor. Cambia al lado «Auditor» para ver el veredicto.</p>
          )}

          {sig.accion === "descargar" && (
            <p className="nf-ok">{Cosa} está aprobada. Descarga el papel (Excel, Word, PowerPoint, HTML/PDF) desde la
              vista de trabajo detallada.</p>
          )}
        </div>
      )}
    </section>
  );
}
