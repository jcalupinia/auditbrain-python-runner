// Metadatos de las 10 páginas del lienzo (sin JSX, para poder probarlos).
// `sp` de `mayores` es la de sus partes no operativas: cubos y constructor.
export const PAGINAS = [
  { id: "portada", titulo: "Portada", sp: null, operativa: false },
  { id: "mayores", titulo: "Mayores y diarios", sp: "SP7", operativa: true },
  { id: "estados", titulo: "Estados financieros", sp: "SP10", operativa: false },
  { id: "bases", titulo: "Bases de datos", sp: "SP3", operativa: false },
  { id: "sri", titulo: "Cumplimiento tributario · SRI", sp: "SP6", operativa: false },
  { id: "niif", titulo: "Políticas contables NIIF", sp: "SP11 · SP12", operativa: false },
  { id: "muestras", titulo: "Selección de muestras", sp: "SP13", operativa: false },
  { id: "reportes", titulo: "Reportes", sp: "SP5 · SP7", operativa: false },
  { id: "agentes", titulo: "Revisión con agentes", sp: "SP8", operativa: false },
  { id: "ruta", titulo: "Hoja de ruta", sp: null, operativa: false },
];
