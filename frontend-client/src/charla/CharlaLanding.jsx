import { useState } from "react";
import CharlaForm from "./CharlaForm.jsx";
import "./charla.css";

const EVENTO = {
  titulo: "Elaboración de Anexos Tributarios con Herramienta de Automatización",
  subtitulo: "Charla gratuita en Zoom",
  fecha: "Jueves 18 de junio",
  hora: "19h00",
  duracion: "2 horas",
  modalidad: "Zoom",
  beneficios: [
    "Automatiza tus anexos tributarios",
    "Descarga inteligente de información del SRI",
    "Validaciones automáticas y control de inconsistencias",
    "Reduce tiempos y minimiza errores",
    "Casos prácticos para empresas y profesionales",
  ],
};

function Exito({ evento }) {
  return (
    <div className="charla-card">
      <div className="charla-success">
        <div className="check">✓</div>
        <h3>¡Reserva confirmada!</h3>
        <p>Te enviamos los detalles a tu email y WhatsApp.</p>
        <div className="charla-meta" style={{ justifyContent: "center" }}>
          <div><span>Fecha</span><b>{evento.fecha}</b></div>
          <div><span>Hora</span><b>{evento.hora}</b></div>
          <div><span>Modalidad</span><b>{evento.modalidad}</b></div>
        </div>
      </div>
    </div>
  );
}

export default function CharlaLanding() {
  const [done, setDone] = useState(false);

  return (
    <div className="charla-page">
      <div className="charla-wrap">
        <div className="charla-hero">
          <div>
            <span className="charla-badge">{EVENTO.subtitulo}</span>
            <h1 className="charla-title">
              Elaboración de <b>Anexos Tributarios</b> con Herramienta de Automatización
            </h1>
            <p className="charla-sub">Más eficiencia, menos errores, cumplimiento asegurado.</p>
            <div className="charla-meta">
              <div><span>Fecha</span><b>{EVENTO.fecha}</b></div>
              <div><span>Hora</span><b>{EVENTO.hora}</b></div>
              <div><span>Duración</span><b>{EVENTO.duracion}</b></div>
              <div><span>Modalidad</span><b>{EVENTO.modalidad}</b></div>
            </div>
            <ul className="charla-benefits">
              {EVENTO.beneficios.map((b) => <li key={b}>{b}</li>)}
            </ul>
          </div>
          {done ? <Exito evento={EVENTO} /> : <CharlaForm evento={EVENTO} onSuccess={() => setDone(true)} />}
        </div>
        <div className="charla-foot">
          © {new Date().getFullYear()} Audit Consulting Group · Powered by Audit-IA
        </div>
      </div>
    </div>
  );
}
