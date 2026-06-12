import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import CharlaForm from "./CharlaForm.jsx";
import { DATA_PROTECTION_TEXT } from "./legal.js";
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

function Exito({ evento, resultado }) {
  const grupo = resultado?.whatsapp_group_url || "";
  const zoom = resultado?.zoom_url || "";
  return (
    <div className="charla-card">
      <div className="charla-success">
        <div className="check">✓</div>
        <h3>¡Inscripción confirmada!</h3>
        {grupo ? (
          <>
            <p>Escaneá este código para unirte al grupo de WhatsApp con novedades y recordatorios de la charla.</p>
            <div className="charla-qr">
              <QRCodeSVG value={grupo} size={200} level="M" includeMargin />
            </div>
            <a
              className="charla-btn"
              href={grupo}
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: "inline-block", textDecoration: "none", marginTop: 8 }}
            >
              Unirme al grupo
            </a>
          </>
        ) : (
          <p>Pronto te enviaremos el link del grupo de WhatsApp por email.</p>
        )}
        {zoom && (
          <a
            className="charla-btn charla-btn-zoom"
            href={zoom}
            target="_blank"
            rel="noopener noreferrer"
            style={{ display: "inline-block", textDecoration: "none", marginTop: 10 }}
          >
            Unirme por Zoom
          </a>
        )}
        <div className="charla-meta" style={{ justifyContent: "center", marginTop: 16 }}>
          <div><span>Fecha</span><b>{evento.fecha}</b></div>
          <div><span>Hora</span><b>{evento.hora}</b></div>
          <div><span>Modalidad</span><b>{evento.modalidad}</b></div>
        </div>
        <p className="charla-legal">{DATA_PROTECTION_TEXT}</p>
      </div>
    </div>
  );
}

export default function CharlaLanding() {
  const [resultado, setResultado] = useState(null);

  return (
    <div className="charla-page">
      <div className="charla-wrap">
        <div className="charla-hero">
          <div className="charla-hero-text">
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
            <div className="charla-hero-img">
              <img
                src="/assets/charla-hero.jpg"
                alt="Charla de Anexos Tributarios — Audit Consulting Group"
                onError={(e) => { e.currentTarget.style.display = "none"; }}
              />
            </div>
          </div>
          {resultado
            ? <Exito evento={EVENTO} resultado={resultado} />
            : <CharlaForm evento={EVENTO} onSuccess={(res) => setResultado(res)} />}
        </div>
        <div className="charla-foot">
          © {new Date().getFullYear()} Audit Consulting Group · Powered by Audit-IA
        </div>
      </div>
    </div>
  );
}
