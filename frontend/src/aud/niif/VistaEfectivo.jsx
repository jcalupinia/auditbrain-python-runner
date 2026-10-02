import VistaProceso from "./VistaProceso";
import { CONFIG } from "./procesoConfig";

/*
 * Wrapper delgado: «Efectivo y Equivalentes de Efectivo» es la vista de 3 pasos
 * config-driven (VistaProceso) con la config de efectivo. El comportamiento no
 * cambia respecto de la versión previa; toda la lógica está en VistaProceso y en
 * procesoConfig.js. Se conserva este componente por compatibilidad de imports.
 */
export default function VistaEfectivo(props) {
  return <VistaProceso config={CONFIG.efectivo} {...props} />;
}
