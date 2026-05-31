import { useState } from "react";
import { TAX_CATEGORIES } from "./catalog.js";
import AnalisisTributarioTool from "./AnalisisTributarioTool.jsx";

export default function TaxCatalog({ projectId }) {
  const [activeTool, setActiveTool] = useState(null);

  if (activeTool === "TAX.PLANIFICACION.UTILIDADES_RETENIDAS") {
    return (
      <div className="aud-tool-wrap">
        <button className="link aud-back" onClick={() => setActiveTool(null)}>
          ← Volver al catálogo
        </button>
        <AnalisisTributarioTool projectId={projectId} />
      </div>
    );
  }

  return (
    <div className="aud-catalog">
      <h2>Tax › Análisis — Catálogo de herramientas</h2>
      <div className="aud-cat-grid">
        {TAX_CATEGORIES.map((cat) => {
          const hasTools = cat.tools && cat.tools.length > 0;
          return (
            <div key={cat.id} className={`aud-cat-card ${hasTools ? "active" : "soon"}`}>
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
                <div className="aud-cat-soon">Próximamente</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
