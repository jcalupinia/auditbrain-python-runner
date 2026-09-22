import { Suspense, lazy, useEffect, useState } from "react";
import * as api from "../api";
import { CATEGORIES } from "./catalog.js";
import { STRINGS } from "./strings.js";
import ObligacionesFiscalesTool from "./ObligacionesFiscalesTool.jsx";
import InformeCumplimientoTributarioTool from "./InformeCumplimientoTributarioTool.jsx";
import MotorBalancesTool from "./MotorBalancesTool.jsx";
import VnrTool from "./vnr/VnrTool.jsx";

const PruebasEncargo = lazy(() => import("./niif/PruebasEncargo.jsx"));

// Fichas NIIF («ficha:») y herramientas del catálogo («proc:») se trabajan en Pruebas del encargo.
export const abrePruebasEncargo = (id) => /^(ficha|proc):/.test(id || "");

export default function ToolCatalog({ projectId }) {
  const [activeTool, setActiveTool] = useState(null);
  const [sharedContext, setSharedContext] = useState(null);
  // Fichas NIIF de «Generación de herramientas NIIF»: las enviadas son el catálogo;
  // las probadas se muestran como pendientes de aprobación para poder encontrarlas.
  const [fichas, setFichas] = useState([]);
  const [carga, setCarga] = useState("cargando");  // cargando · lista · error
  const cargarFichas = () => {
    setCarga("cargando");
    api.cicloHerramientas()
      .then((l) => { setFichas(l.filter((h) => h.tipo === "ficha NIIF" || h.tipo === "herramienta NIIF")); setCarga("lista"); })
      .catch(() => { setFichas([]); setCarga("error"); });
  };
  useEffect(cargarFichas, []);

  if (abrePruebasEncargo(activeTool)) {
    return (
      <div className="aud-tool-wrap">
        <button className="link aud-back" onClick={() => setActiveTool(null)}>{STRINGS.back_to_catalog}</button>
        <Suspense fallback={<p className="muted">Cargando…</p>}>
          <PruebasEncargo proyecto={projectId ? { id: projectId } : null} herramienta={activeTool} />
        </Suspense>
      </div>
    );
  }

  if (activeTool === "AUD.INVENTARIOS.VNR") {
    return <div className="aud-tool-wrap"><button className="link aud-back" onClick={() => { if (window.confirm("Descargue sus resultados antes de salir. ¿Volver al catálogo?")) setActiveTool(null); }}>{STRINGS.back_to_catalog}</button><VnrTool key={projectId} projectId={projectId} sharedContext={sharedContext?.projectId === projectId ? sharedContext.context : null} onShareContext={context => setSharedContext({projectId, context})}/></div>;
  }

  if (activeTool === "AUD.MOTOR_BALANCES") {
    return (
      <div className="aud-tool-wrap">
        <button className="link aud-back" onClick={() => setActiveTool(null)}>
          {STRINGS.back_to_catalog}
        </button>
        <MotorBalancesTool />
      </div>
    );
  }

  if (activeTool === "AUD.IMPUESTOS.OBLIGACIONES_FISCALES") {
    return (
      <div className="aud-tool-wrap">
        <button
          className="link aud-back"
          onClick={() => setActiveTool(null)}
        >
          {STRINGS.back_to_catalog}
        </button>
        <ObligacionesFiscalesTool projectId={projectId} />
      </div>
    );
  }

  if (activeTool === "AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO") {
    return (
      <div className="aud-tool-wrap">
        <button className="link aud-back" onClick={() => setActiveTool(null)}>
          {STRINGS.back_to_catalog}
        </button>
        <InformeCumplimientoTributarioTool projectId={projectId} />
      </div>
    );
  }

  return (
    <div className="aud-catalog">
      <h2>{STRINGS.catalog_title}</h2>
      {carga === "cargando" && <p className="muted">Cargando las herramientas del catálogo…</p>}
      {carga === "error" && (
        <p className="nf-error" role="alert">
          No se pudieron cargar las herramientas NIIF (el servidor puede estar despertando).{" "}
          <button type="button" className="link" onClick={cargarFichas}>Reintentar</button>
        </p>
      )}
      <div className="aud-cat-grid">
        {CATEGORIES.map((cat) => {
          const suyas = fichas.filter((f) => f.area === cat.id || String(f.area || "").toUpperCase() === cat.label.toUpperCase());
          const hasTools = (cat.tools && cat.tools.length > 0) || suyas.length > 0;
          return (
            <div
              key={cat.id}
              className={`aud-cat-card ${hasTools ? "active" : "soon"}`}
            >
              <div className="aud-cat-h">
                <span className="aud-cat-type">{cat.type}</span>
                <h3>{cat.label}</h3>
              </div>
              {hasTools ? (
                <div className="aud-cat-tools">
                  {suyas.map((f) => (
                    <button key={f.origen} className="aud-tool-item" onClick={() => setActiveTool(f.origen)}>
                      <b>{f.nombre}</b>
                      <span>
                        {(f.marcos || []).join(" · ") || "Ficha NIIF"}
                        {f.estado === "enviada" ? " · en el catálogo" : " · probada, pendiente de aprobación para el catálogo"}
                      </span>
                    </button>
                  ))}
                  {(cat.tools || []).map((t) => (
                    <button
                      key={t.id}
                      className="aud-tool-item"
                      onClick={() => setActiveTool(t.id)}
                    >
                      <b>{t.label}</b>
                      <span>{t.description}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="aud-cat-soon">{carga === "error" ? "Sin cargar" : STRINGS.coming_soon}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
