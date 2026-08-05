import ObligacionesFiscalesWorkspace from "./of/ObligacionesFiscalesWorkspace.jsx";

// Envoltorio delgado: el catálogo de herramientas (ToolCatalog.jsx) importa
// este archivo por su nombre/ruta históricos. Toda la lógica vive en
// ./of/ObligacionesFiscalesWorkspace.jsx (workspace estilo ICT, ciclo de
// dos fases: subir por slot → procesar → revisar → aprobar → descargar).
export default function ObligacionesFiscalesTool({ projectId }) {
  return <ObligacionesFiscalesWorkspace projectId={projectId} />;
}
