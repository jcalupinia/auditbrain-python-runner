import { PAGINAS } from "../paginas.js";
const META = PAGINAS.find((p) => p.id === "reportes");
export default function Constructor({ EnConstruccion }) {
  return (<section className="ma-pagina"><h2>{META.titulo}</h2><EnConstruccion sp={META.sp} /></section>);
}
