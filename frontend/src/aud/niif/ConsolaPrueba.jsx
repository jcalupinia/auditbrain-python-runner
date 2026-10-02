import { useCallback, useEffect, useRef, useState } from "react";

import { cicloComentarios, cicloComentar } from "../../api.js";
import { lineasDeConversacion, cuentaComentarios, puedePreguntar } from "./consolaLogic.js";

// Consola de comunicación por prueba (chat auditable). Cada comentario es un evento
// de la bitácora (queda en el papel, cédula 12; NIA 230). El asistente responde en el
// mismo hilo con el servidor de IA local, como borrador para el auditor.
export default function ConsolaPrueba({ pruebaId }) {
  const [conversacion, setConversacion] = useState([]);
  const [asistenteDisponible, setAsistenteDisponible] = useState(false);
  const [texto, setTexto] = useState("");
  const [asistente, setAsistente] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const finRef = useRef(null);

  const cargar = useCallback(async () => {
    try {
      const d = await cicloComentarios(pruebaId);
      setConversacion(d.conversacion || []);
      setAsistenteDisponible(Boolean(d.asistente_disponible));
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setCargando(false);
    }
  }, [pruebaId]);

  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { finRef.current?.scrollIntoView({ block: "nearest" }); }, [conversacion]);

  async function enviar(e) {
    e?.preventDefault();
    const pedirIA = asistente && puedePreguntar(asistenteDisponible, texto);
    setEnviando(true);
    setError("");
    setAviso("");
    try {
      const r = await cicloComentar(pruebaId, texto, pedirIA);
      setConversacion(r.conversacion || []);
      setTexto("");
      if (r.asistente_error) setAviso(r.asistente_error);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setEnviando(false);
    }
  }

  const lineas = lineasDeConversacion(conversacion);

  return (
    <details className="nf-chat" open>
      <summary>
        Consola de comunicación <span className="muted">· {cuentaComentarios(conversacion)} mensaje(s)</span>
      </summary>

      {error && <p className="nf-error">{error}</p>}
      {cargando ? (
        <p className="muted">Cargando conversación…</p>
      ) : (
        <div className="nf-chat-lista" role="log" aria-label="Conversación de la prueba">
          {lineas.length === 0 && <p className="muted">Sin mensajes todavía. Escribí el primero abajo.</p>}
          {lineas.map((l) =>
            l.tipo === "sistema" ? (
              <p key={l.id} className="nf-chat-sistema">
                {l.texto} {l.actor && <span className="muted">· {l.actor}</span>}
              </p>
            ) : (
              <div key={l.id} className={`nf-chat-msg${l.esAsistente ? " ia" : ""}`}>
                <span className="nf-chat-actor">{l.esAsistente ? "🤖 " : ""}{l.actor}</span>
                <span className="nf-chat-texto">{l.texto}</span>
              </div>
            )
          )}
          <div ref={finRef} />
        </div>
      )}

      {aviso && <p className="nf-chat-aviso muted">{aviso}</p>}

      <form className="nf-chat-form" onSubmit={enviar}>
        <textarea
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Escribí un comentario para el equipo o una pregunta al asistente…"
          rows={2}
          maxLength={8000}
        />
        <div className="nf-chat-acciones">
          <label className={asistenteDisponible ? "" : "muted"} title={asistenteDisponible ? "" : "No hay proveedor de IA configurado en el servidor"}>
            <input
              type="checkbox"
              checked={asistente}
              disabled={!asistenteDisponible}
              onChange={(e) => setAsistente(e.target.checked)}
            />
            Preguntar al asistente (IA local)
          </label>
          <button type="submit" className="btn sm primary" disabled={enviando || !texto.trim()}>
            {enviando ? "Enviando…" : "Enviar"}
          </button>
        </div>
      </form>
      <p className="muted nf-chat-nota">
        Los comentarios quedan en la bitácora del papel de trabajo (NIA 230). Las respuestas del
        asistente son un borrador que el auditor responsable debe validar.
      </p>
    </details>
  );
}
