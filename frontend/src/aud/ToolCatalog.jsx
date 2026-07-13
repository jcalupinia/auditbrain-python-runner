import { useState } from "react";
import { CATEGORIES } from "./catalog.js";
import { STRINGS } from "./strings.js";
import ObligacionesFiscalesTool from "./ObligacionesFiscalesTool.jsx";
import InformeCumplimientoTributarioTool from "./InformeCumplimientoTributarioTool.jsx";
import MotorBalancesTool from "./MotorBalancesTool.jsx";

export default function ToolCatalog({ projectId }) {
  const [activeTool, setActiveTool] = useState(null);

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
      <div className="aud-cat-grid">
        {CATEGORIES.map((cat) => {
          const hasTools = cat.tools && cat.tools.length > 0;
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
                  {cat.tools.map((t) => (
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
                <div className="aud-cat-soon">{STRINGS.coming_soon}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
