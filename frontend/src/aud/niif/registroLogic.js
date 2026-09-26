// Registros del encargo con un clic (decisión del dueño, 2026-09-26). El servidor aplica las reglas
// (ciclo/servicio.py::registrar); aquí solo se arma el resumen que pinta el panel.

// Los mismos roles de planificacion_encargo.ROLES.
export const ROLES = ["Socio", "Gerente", "Senior", "Asistente", "Revisor de calidad", "Experto", "Otro"];

export const DOCUMENTOS = [
  ["carta_encargo", "Carta de encargo (NIA 210)"],
  ["acta_discusion", "Acta de la discusión del equipo (NIA 315 y 240)"],
  ["carta_planificacion", "Carta de planificación al gobierno (NIA 260)"],
];

export const NOMBRE_ARCHIVO = {
  carta_encargo: "Carta_de_encargo.docx",
  acta_discusion: "Acta_discusion_equipo.docx",
  carta_planificacion: "Carta_de_planificacion.docx",
};

const vacio = { registros: { equipo: [], asistencia: [] } };

// Estado de cada registro que la planificación espera (hojas 00_Registros, 24, 25, 26 y 32).
export function resumenRegistros(encargo) {
  const r = (encargo || vacio).registros || vacio.registros;
  const equipo = r.equipo || [];
  const asist = r.asistencia || [];
  const conAmenaza = equipo.filter((x) => x.amenazas && !x.salvaguardas);
  const uno = (k) => r[k] || null;
  return [
    {
      clave: "independencia",
      etiqueta: "Independencia del equipo",
      hecho: equipo.length > 0 && conAmenaza.length === 0,
      detalle: equipo.length
        ? `${equipo.length} integrante(s)` + (conAmenaza.length ? ` · ${conAmenaza.length} con amenaza sin salvaguarda` : "")
        : "Nadie ha confirmado todavía",
    },
    {
      clave: "aceptacion",
      etiqueta: "Aceptación del socio",
      hecho: !!uno("aceptacion"),
      detalle: uno("aceptacion") ? `${uno("aceptacion").actor} · ${uno("aceptacion").fecha}` : "Pendiente",
    },
    {
      clave: "carta",
      etiqueta: "Carta de encargo firmada",
      hecho: !!uno("carta"),
      detalle: uno("carta") ? `Firmada el ${uno("carta").fecha}` + (uno("carta").detalle ? " · con limitaciones" : "") : "Pendiente",
    },
    {
      clave: "asistencia",
      etiqueta: "Discusión del equipo",
      hecho: asist.some((x) => x.rol === "Socio"),
      detalle: asist.length
        ? `${asist.length} asistente(s)` + (asist.some((x) => x.rol === "Socio") ? "" : " · falta el socio")
        : "Pendiente",
    },
    {
      clave: "comunicacion",
      etiqueta: "Comunicación al gobierno",
      hecho: !!uno("comunicacion"),
      detalle: uno("comunicacion") ? `${uno("comunicacion").detalle} · ${uno("comunicacion").fecha}` : "Pendiente",
    },
  ];
}

// Mi confirmación de independencia vigente (el rol se reutiliza para la asistencia).
export const miIndependencia = (registros, usuario) =>
  (registros || []).filter((x) => x.tipo === "independencia" && x.actor === usuario).at(-1) || null;

export const NOMBRE_TIPO = {
  independencia: "Independencia",
  asistencia: "Asistencia a la discusión",
  aceptacion: "Aceptación del socio",
  carta: "Carta de encargo firmada",
  comunicacion: "Comunicación al gobierno",
};
