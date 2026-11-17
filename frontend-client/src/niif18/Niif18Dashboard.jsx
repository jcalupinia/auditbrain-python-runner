import { useEffect, useRef, useState } from "react";
import PortalShell from "../shell/PortalShell.jsx";
import { API_BASE, API_UNRESOLVED } from "../api.js";

// NIIF 18 Studio — dashboard propio del portal cliente.
//
// El Studio es una sola página autónoma (`/niif18/studio.html`, generada en el
// repositorio herramienta-niif-18). Se embebe en un marco del MISMO ORIGEN, de
// modo que lee por sí misma el token de sesión del portal
// (localStorage `ab_client_token`) y llama a /api/v1/client/niif18/* con
// `Authorization: Bearer`. No tiene login propio.
//
// La base de la API viaja por querystring (es una URL, no un secreto); el token
// NUNCA va en la URL, para que no quede en el historial ni en los logs.

const RUTA_STUDIO = "/niif18/studio.html";

export default function Niif18Dashboard() {
  const marco = useRef(null);
  const [alto, setAlto] = useState(900);

  // El Studio es largo: se le da toda la altura disponible de la ventana.
  useEffect(() => {
    const ajustar = () => setAlto(Math.max(640, window.innerHeight - 180));
    ajustar();
    window.addEventListener("resize", ajustar);
    return () => window.removeEventListener("resize", ajustar);
  }, []);

  if (API_UNRESOLVED) {
    return (
      <PortalShell title="NIIF 18 Studio" activeCategory="NIIF" activeNodeCode="NIIF_18_STUDIO">
        <div style={{ padding: 24 }}>
          <h2>Entorno no reconocido</h2>
          <p>
            Por seguridad no se contactará ningún backend. Verifique la URL del
            entorno o la variable <code>VITE_API_BASE</code>.
          </p>
        </div>
      </PortalShell>
    );
  }

  const src = `${RUTA_STUDIO}?api=${encodeURIComponent(API_BASE || "")}`;

  return (
    <PortalShell title="NIIF 18 Studio" activeCategory="NIIF" activeNodeCode="NIIF_18_STUDIO">
      <iframe
        ref={marco}
        src={src}
        title="NIIF 18 Studio"
        style={{
          width: "100%",
          height: alto,
          border: 0,
          borderRadius: 12,
          background: "#eef3ef",
          display: "block",
        }}
      />
    </PortalShell>
  );
}
