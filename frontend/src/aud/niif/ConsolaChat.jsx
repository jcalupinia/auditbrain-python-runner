import { useCallback, useEffect, useState } from "react";

import * as api from "../../api";
import { ChipDocumento } from "./CicloVista";
import { ConsolaRevision } from "./ConsolaRevision";
import { accionInline, claseMensaje, nombreDe, puedeSubirInline, requerimientosPendientes } from "./consolaChatVista";

/*
 * Consola-chat del piloto de planificación (dos modos en la misma consola).
 *
 * Es la puerta principal de la planificación: un hilo de mensajes tipo chat donde
 * un agente determinista (servidor) guía el proceso. El «Preparador» sube los
 * documentos que el agente pide y produce la planificación; el «Auditor» ve el
 * veredicto del recálculo independiente y aprueba. Los pasos de cómputo pesado
 * (producir/enviar) y la aprobación formal se hacen en la vista de trabajo, que
 * esta consola despliega cuando toca. Las respuestas de gobierno del encargo
 * (independencia, enfoque por ciclo) se resuelven automáticamente por política de
 * la firma y no se preguntan aquí.
 */

export function ConsolaChat({ prueba, onRecargar, onAbrirDetalle }) {
  const [rol, setRol] = useState("preparador");
  const [guion, setGuion] = useState(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(async () => {
    setError("");
    try {
      setGuion(await api.cicloConsolaChat(prueba.id, rol));
    } catch (e) {
      setError(e.message || String(e));
    }
  }, [prueba.id, rol]);

  useEffect(() => { cargar(); }, [cargar]);

  async function accionCiclo(nombre, datos = {}) {
    setOcupado(true);
    setError("");
    try {
      await api.cicloAccion(prueba.id, nombre, prueba.revision, datos);
      await onRecargar?.();
      await cargar();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setOcupado(false);
    }
  }

  const cobertura = prueba.cobertura || [];
  const pendientes = requerimientosPendientes(prueba, cobertura);
  const cobIdx = Object.fromEntries(cobertura.map((c) => [c.id, c]));
  const sig = guion?.siguiente || {};

  return (
    <section className="nf-chat">
      <div className="nf-chat-cab">
        <p className="nf-eyebrow" style={{ margin: 0 }}>CONSOLA DE PLANIFICACIÓN · PILOTO</p>
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
      </div>

      {/* Acción del paso actual */}
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
                {pendientes.length === 0 && <span className="nf-ok">Documentos completos. Ya puedes producir la planificación.</span>}
              </div>
            ) : (
              <button type="button" className="btn primary" disabled={ocupado} onClick={() => onAbrirDetalle?.()}>
                Preparar el requerimiento en la vista de trabajo
              </button>
            )
          )}

          {/* Preparador · producir / enviar → vista de trabajo (cómputo y envío) */}
          {(sig.accion === "procesar" || sig.accion === "enviar") && (
            <button type="button" className="btn primary" disabled={ocupado} onClick={() => onAbrirDetalle?.()}>
              {sig.etiqueta} →
            </button>
          )}

          {/* Auditor · revisar (veredicto inline) */}
          {sig.accion === "revisar" && <ConsolaRevision prueba={prueba} />}

          {/* Auditor · aprobar / devolver */}
          {sig.accion === "aprobar" && (
            <>
              <ConsolaRevision prueba={prueba} />
              <button type="button" className="btn primary" disabled={ocupado} onClick={() => onAbrirDetalle?.()}>
                Ir a aprobar la planificación →
              </button>
            </>
          )}
          {sig.accion === "devolver" && (
            <button type="button" className="btn" disabled={ocupado} onClick={() => onAbrirDetalle?.()}>
              Devolver al preparador en la vista de trabajo →
            </button>
          )}

          {sig.accion === "descargar" && (
            <button type="button" className="btn" disabled={ocupado} onClick={() => onAbrirDetalle?.()}>
              Descargar el papel en la vista de trabajo →
            </button>
          )}

          {sig.accion === "esperar" && (
            <p className="muted">La planificación está con el auditor. Cambia al lado «Auditor» para ver el veredicto.</p>
          )}
        </div>
      )}

      {!accionInline(sig.accion) && sig.accion && (
        <p className="muted">Este paso se completa en la vista de trabajo detallada (abajo).</p>
      )}
    </section>
  );
}
