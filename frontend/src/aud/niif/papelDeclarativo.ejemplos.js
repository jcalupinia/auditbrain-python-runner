// Ejemplos del papel declarativo (datos ficticios) para las pruebas: una
// herramienta del catálogo aprobada (VNR) y una ficha con serie en borrador
// (NIIF 16). Salen de los mismos ejemplos que usa el sitio.
import { herramientaDeEstudio } from "./contraste.js";
import { EJEMPLO_NIIF16 } from "./estudioLogic.js";
import { cargaPapel } from "./papelDeclarativo.js";
import { calculate } from "./sitio/tools/domain.mjs";
import { presentationExample } from "./sitio/tools/example.mjs";

export function herramientasEjemplo() {
  const base = presentationExample();
  const vnr = {
    ...base, demo: false, state: "APROBADO", version: 2,
    engagement: { ...base.engagement, client: "Comercial Ejemplo S.A. · DATOS FICTICIOS", firm: "AuditConsulting Auditores Cía. Ltda." },
    reconciliation: { ledger: "480", tolerance: "5", difference: "-10", within: false, acceptance: "Diferencia en conciliación con el mayor." },
    analysis: "El deterioro recalculado partida por partida asciende a 82,00.",
    exceptionReview: "Las dos partidas con deterioro se revisaron con el precio de venta posterior al cierre.",
    conclusion: "El inventario se presenta al menor entre costo y VNR, salvo el ajuste de 82,00 propuesto.",
    conclusionReviewed: true, approvedBy: "revisor@auditconsulting.ec", approvedAt: "2026-09-25T10:00:00Z",
  };
  const { definicion, filas } = EJEMPLO_NIIF16;
  const niif16 = herramientaDeEstudio({ ficha: { nombre: "Arrendamientos" }, definicion, filas, run: calculate(definicion, filas, {}, []) });
  return { vnr, niif16 };
}

export const EJEMPLOS = () => Object.fromEntries(Object.entries(herramientasEjemplo()).map(([k, t]) => [k, cargaPapel(t)]));
