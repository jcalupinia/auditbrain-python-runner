import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/* ---------------------------------------------------------------------
   Markdown — render de las respuestas del LLM en el Workspace cognitivo.

   Antes el hilo pintaba `{m.content}` como texto plano dentro de un
   contenedor con `white-space: pre-wrap`, así que el usuario veía los
   `##`, los `**` y las tablas en pipes tal cual los emite el modelo.

   remark-gfm es obligatorio, no decorativo: las respuestas técnicas
   (NIIF, casilleros SRI) vienen con TABLAS y esas no son markdown
   estándar — sin el plugin se seguirían viendo como `| a | b |`.

   SEGURIDAD: a propósito NO se usa `rehype-raw`. Sin él, cualquier HTML
   incrustado en la respuesta se muestra como texto y nunca se ejecuta.
   La salida del modelo se trata como dato, no como plantilla.
   --------------------------------------------------------------------- */

const COMPONENTS = {
  // Las tablas de casilleros son anchas. Scrollean dentro de su propia
  // caja para no estirar el ancho del hilo ni desbordar el panel.
  table: (props) => (
    <div className="md-table-wrap">
      <table {...props} />
    </div>
  ),
  // Los links del modelo apuntan a normativa externa: nueva pestaña, y
  // `noopener` para que la página destino no acceda a `window.opener`.
  a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" />,
};

export default function Markdown({ children, className = "" }) {
  return (
    <div className={`md ${className}`.trim()}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {children || ""}
      </ReactMarkdown>
    </div>
  );
}
