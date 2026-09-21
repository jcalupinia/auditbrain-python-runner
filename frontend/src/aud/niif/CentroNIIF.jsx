import { Suspense, lazy, useState } from "react";

import GeneradorHerramientasNIIF from "./GeneradorHerramientasNIIF.jsx";

// Réplica, dentro de la pestaña NIIF del Command Center, del menú del sitio
// AuditBrain. Cada sección se incorpora cuando está probada; las que usan el
// exportador del sitio se cargan al abrirlas, no con el portal.
const RecorridoVNR = lazy(() => import("./RecorridoVNR.jsx"));
const ConsolaArchivos = lazy(() => import("./ConsolaArchivos.jsx"));

const SECCIONES = [
  { id: "fichas", label: "Diseñar fichas", Vista: GeneradorHerramientasNIIF },
  { id: "recorrido", label: "Recorrido VNR", Vista: RecorridoVNR },
  { id: "consola", label: "Consola de archivos", Vista: ConsolaArchivos },
];

export default function CentroNIIF() {
  const [seccion, setSeccion] = useState("fichas");
  const { Vista } = SECCIONES.find((s) => s.id === seccion);
  return (
    <div className="nf-centro">
      <nav className="nf-subtabs" aria-label="Secciones de herramientas NIIF">
        {SECCIONES.map((s) => (
          <button
            key={s.id}
            type="button"
            className={s.id === seccion ? "on" : ""}
            aria-current={s.id === seccion ? "page" : undefined}
            onClick={() => setSeccion(s.id)}
          >
            {s.label}
          </button>
        ))}
      </nav>
      <Suspense fallback={<p className="muted">Cargando…</p>}>
        <Vista />
      </Suspense>
    </div>
  );
}
