import { useEffect, useMemo, useState } from "react";
import { crearCliente, disponibilidad } from "./clienteMotor.js";
import { PAGINAS } from "./paginas.js";
import Portada from "./paginas/Portada.jsx";
import Mayores from "./paginas/Mayores.jsx";
import EstadosFinancieros from "./paginas/EstadosFinancieros.jsx";
import BasesDatos from "./paginas/BasesDatos.jsx";
import CumplimientoSRI from "./paginas/CumplimientoSRI.jsx";
import PoliticasNIIF from "./paginas/PoliticasNIIF.jsx";
import Muestreo from "./paginas/Muestreo.jsx";
import Constructor from "./paginas/Constructor.jsx";
import RevisionAgentes from "./paginas/RevisionAgentes.jsx";
import HojaDeRuta from "./paginas/HojaDeRuta.jsx";
import "./motorAnalitico.css";

const COMPONENTES = {
  portada: Portada, mayores: Mayores, estados: EstadosFinancieros, bases: BasesDatos,
  sri: CumplimientoSRI, niif: PoliticasNIIF, muestras: Muestreo, reportes: Constructor,
  agentes: RevisionAgentes, ruta: HojaDeRuta,
};

export function EnConstruccion({ sp, children }) {
  return (
    <div className="ma-construccion" role="note">
      <strong>En construcción · {sp}</strong>
      <span>{children || "Estructura aprobada; sin datos hasta que se active su subproyecto."}</span>
    </div>
  );
}

const MENSAJES = {
  red_local: {
    titulo: "Chrome está reteniendo la conexión con el motor",
    texto: "Tu equipo está conectado a Tailscale y Chrome pide autorizar el «acceso a la red local». Acepta el aviso junto a la barra de direcciones, o entra a Configuración del sitio de auditbrain-frontend.onrender.com → «Acceso a la red local» → Permitir, y vuelve a intentar.",
  },
  caido: {
    titulo: "El motor no responde",
    texto: "El servidor de la firma no está disponible. Procedimiento de caída: avisa al socio responsable; la caída máxima tolerada es de 1 día hábil. Los datos no se envían a ningún otro servicio.",
  },
  sin_permiso: {
    titulo: "No se pudo obtener el permiso del portal",
    texto: "",
  },
};

export default function MotorAnaliticoTool({ projectId }) {
  const [pagina, setPagina] = useState("portada");
  const [disp, setDisp] = useState({ estado: "revisando" });
  const cliente = useMemo(
    () => crearCliente({ encargo: projectId ? `proyecto-${projectId}` : "sin-proyecto" }),
    [projectId]
  );

  const revisar = () => {
    setDisp({ estado: "revisando" });
    disponibilidad(cliente).then(setDisp);
  };
  useEffect(revisar, [cliente]);

  const Pagina = COMPONENTES[pagina];
  const aviso = MENSAJES[disp.estado];
  return (
    <div className="ma-root">
      <nav className="ma-nav" aria-label="Secciones del motor">
        {PAGINAS.map((p) => (
          <button key={p.id} className={p.id === pagina ? "ma-tab activa" : "ma-tab"}
                  aria-current={p.id === pagina ? "page" : undefined} onClick={() => setPagina(p.id)}>
            {p.titulo}
          </button>
        ))}
      </nav>
      <div className={`ma-estado ma-estado-${disp.estado}`} role="status">
        {disp.estado === "revisando" && "Revisando la conexión con el motor…"}
        {disp.estado === "disponible" && "Motor disponible · 38 pruebas"}
        {aviso && (
          <>
            <strong>{aviso.titulo}</strong>
            <span>{aviso.texto || disp.detalle}</span>
            <button className="ma-boton" onClick={revisar}>Reintentar</button>
          </>
        )}
      </div>
      <Pagina ir={setPagina} cliente={cliente} disponible={disp.estado === "disponible"} EnConstruccion={EnConstruccion} />
    </div>
  );
}
