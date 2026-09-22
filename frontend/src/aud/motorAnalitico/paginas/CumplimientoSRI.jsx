import { PAGINAS } from "../paginas.js";
import "./CumplimientoSRI.css";

const META = PAGINAS.find((p) => p.id === "sri");

// Contenido transcrito de CumplimientoSRI.dc.html (bloques `fuentes`, `cruces`,
// `declaraciones`, `anexos` del script). Estado: "listo" = En el motor,
// "existe" = En Command Center, "nuevo" = Por construir.
const NOMBRE_ESTADO = { listo: "En el motor", existe: "En Command Center", nuevo: "Por construir" };

const FUENTES = [
  { nombre: "Robot del SRI", texto: "Descarga los comprobantes electrónicos emitidos y recibidos, incluidas las retenciones.", formatos: ["XML", "TXT"] },
  { nombre: "Declaraciones", texto: "Formularios presentados en el período, originales y sustitutivas.", formatos: ["PDF", "XML"] },
  { nombre: "Anexos tributarios", texto: "ATS, RDEP, dividendos, accionistas, partes relacionadas y demás.", formatos: ["XML", "Excel"] },
  { nombre: "Contabilidad del cliente", texto: "Mayor o diario, auxiliares de ventas y compras, nómina y maestros.", formatos: ["Excel", "CSV"] },
];

const CRUCES = [
  { titulo: "Ventas SRI vs contabilidad", texto: "Cada factura emitida contra el mayor de ingresos: no registradas, registradas sin factura y suma total de ingresos (voucheo).", reglas: "VTA-008 · VTA-009", t: "listo" },
  { titulo: "Secuencia y duplicados en ventas", texto: "Saltos de numeración por establecimiento y punto de emisión, facturación retroactiva y facturas repetidas.", reglas: "VTA-001 · VTA-002 · duplicados en ventas por construir", t: "listo" },
  { titulo: "Retenciones que nos efectuaron", texto: "Cada comprobante de retención recibido unido a la factura que sustenta: retenciones sin factura, facturas sin retención y bases distintas.", reglas: "Regla nueva", t: "nuevo" },
  { titulo: "Compras SRI vs contabilidad", texto: "Facturas recibidas contra el mayor: gasto sin comprobante, comprobante no registrado, diferencias de importe y de corte.", reglas: "CON-001 · 002 · 003 · 004", t: "listo" },
  { titulo: "Retenciones que efectuamos", texto: "Retención aplicada contra la que corresponde por concepto y porcentaje, y cuadre con el F-103.", reglas: "TRB-002", t: "nuevo" },
  { titulo: "Empresas fantasmas", texto: "Proveedores cruzados contra el catastro del SRI de empresas inexistentes o fantasmas y personas con transacciones inexistentes.", reglas: "PRV-008", t: "nuevo" },
].map((c) => ({ ...c, estado: NOMBRE_ESTADO[c.t] }));

const DECLARACIONES = [
  { form: "F-104 IVA", prueba: "IVA de ventas y compras según XML y contabilidad, mes a mes; crédito tributario arrastrado", t: "existe" },
  { form: "F-103 Retenciones", prueba: "Retenciones de renta e IVA contra comprobantes emitidos y contabilidad", t: "existe" },
  { form: "F-101 Renta sociedades", prueba: "Casilleros contra estados financieros; conciliación tributaria y participación laboral", t: "nuevo" },
  { form: "Otros formularios", prueba: "ICE, pagos varios y salida de divisas, según aplique al cliente", t: "nuevo" },
  { form: "Todas", prueba: "Meses presentados, sustitutivas y fechas de presentación", t: "nuevo" },
].map((d) => ({ ...d, estado: NOMBRE_ESTADO[d.t] }));

const ANEXOS = [
  { form: "ATS", prueba: "Totales contra F-104 y F-103; comprobante por comprobante contra los XML del SRI", t: "existe" },
  { form: "RDEP", prueba: "Relación de dependencia contra nómina y retenciones en la fuente del personal", t: "nuevo" },
  { form: "Dividendos", prueba: "Dividendos distribuidos contra actas, patrimonio y retenciones", t: "nuevo" },
  { form: "Accionistas y beneficiarios", prueba: "Composición societaria contra registros y la Superintendencia de Compañías", t: "nuevo" },
  { form: "Partes relacionadas", prueba: "Operaciones con relacionadas contra contabilidad y umbrales de precios de transferencia", t: "nuevo" },
  { form: "Declaración patrimonial", prueba: "Activos y pasivos declarados contra los estados financieros", t: "nuevo" },
].map((d) => ({ ...d, estado: NOMBRE_ESTADO[d.t] }));

const SECCIONES = [
  { id: "fuentes", titulo: "Fuentes" },
  { id: "comprobantes", titulo: "Comprobantes SRI vs contabilidad" },
  { id: "declaraciones", titulo: "Declaraciones" },
  { id: "anexos", titulo: "Anexos" },
  { id: "organismos", titulo: "Otros organismos" },
];

export default function CumplimientoSRI({ ir, EnConstruccion }) {
  return (
    <section className="ma-pagina ma-sri-pagina">
      <div className="ma-sri-breadcrumb">
        <button type="button" className="ma-sri-link" onClick={() => ir("portada")}>
          Motor de Auditoría Analítica
        </button>
        <span className="ma-sri-sep">/</span>
        <span>Cumplimiento tributario · SRI</span>
      </div>

      <div className="ma-sri-encabezado">
        <h2>{META.titulo}</h2>
        <button type="button" className="ma-boton" onClick={() => ir("portada")}>
          ← Volver a la portada
        </button>
      </div>
      <p className="ma-sri-intro">
        Declaraciones, anexos tributarios y comprobantes electrónicos del SRI contra la contabilidad del
        cliente. El Informe de Cumplimiento Tributario (ICT) es una herramienta aparte.
      </p>
      <nav aria-label="Secciones" className="ma-sri-nav">
        {SECCIONES.map((s) => (
          <a key={s.id} href={`#ma-sri-${s.id}`}>
            {s.titulo}
          </a>
        ))}
      </nav>

      <EnConstruccion sp={META.sp} />

      <section id="ma-sri-fuentes" aria-label="Fuentes" className="ma-grid ma-sri-fuentes">
        {FUENTES.map((f) => (
          <div className="ma-tarjeta ma-sri-tarjeta-fuente" key={f.nombre}>
            <span className="ma-sri-fuente-nombre">{f.nombre}</span>
            <span className="ma-sri-fuente-texto">{f.texto}</span>
            <div className="ma-sri-formatos">
              {f.formatos.map((x) => (
                <span className="ma-sri-chip" key={x}>
                  {x}
                </span>
              ))}
            </div>
          </div>
        ))}
      </section>

      <section id="ma-sri-comprobantes" aria-label="Comprobantes del SRI contra la contabilidad" className="ma-tarjeta ma-sri-comprobantes">
        <div className="ma-sri-comprobantes-cab">
          <h3>Comprobantes del SRI contra la contabilidad</h3>
          <span>Con los XML que descarga el robot del SRI</span>
          <button type="button" className="ma-sri-boton-ejecutar" disabled title="Disponible cuando se active SP6">
            Ejecutar cruces
          </button>
        </div>
        <div className="ma-grid ma-sri-cruces">
          {CRUCES.map((c) => (
            <div className="ma-sri-tarjeta-cruce" key={c.titulo}>
              <div className="ma-sri-cruce-cab">
                <span className="ma-sri-cruce-titulo">{c.titulo}</span>
                <span className={`ma-sri-estado ma-sri-estado-${c.t}`}>{c.estado}</span>
              </div>
              <span className="ma-sri-cruce-texto">{c.texto}</span>
              <span className="ma-sri-cruce-reglas">{c.reglas}</span>
            </div>
          ))}
        </div>
      </section>

      <div className="ma-sri-dos-col">
        <section id="ma-sri-declaraciones" aria-label="Declaraciones" className="ma-tarjeta ma-sri-tabla-bloque">
          <h3>Declaraciones</h3>
          <span className="ma-sri-tabla-nota">
            Cada formulario contra la contabilidad, contra los demás formularios y contra los comprobantes del
            SRI.
          </span>
          <div className="ma-tabla-wrap">
            <table className="ma-tabla ma-sri-tabla">
              <thead>
                <tr>
                  <th scope="col">Formulario</th>
                  <th scope="col">Qué se prueba</th>
                  <th scope="col">Estado</th>
                </tr>
              </thead>
              <tbody>
                {DECLARACIONES.map((d) => (
                  <tr key={d.form}>
                    <td className="ma-sri-tabla-form">{d.form}</td>
                    <td>{d.prueba}</td>
                    <td>
                      <span className={`ma-sri-estado ma-sri-estado-${d.t}`}>{d.estado}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section id="ma-sri-anexos" aria-label="Anexos tributarios" className="ma-tarjeta ma-sri-tabla-bloque">
          <h3>Anexos tributarios</h3>
          <span className="ma-sri-tabla-nota">Cada anexo contra su fuente en la contabilidad y contra las declaraciones.</span>
          <div className="ma-tabla-wrap">
            <table className="ma-tabla ma-sri-tabla">
              <thead>
                <tr>
                  <th scope="col">Anexo</th>
                  <th scope="col">Qué se prueba</th>
                  <th scope="col">Estado</th>
                </tr>
              </thead>
              <tbody>
                {ANEXOS.map((d) => (
                  <tr key={d.form}>
                    <td className="ma-sri-tabla-form">{d.form}</td>
                    <td>{d.prueba}</td>
                    <td>
                      <span className={`ma-sri-estado ma-sri-estado-${d.t}`}>{d.estado}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section id="ma-sri-organismos" aria-label="Otros organismos de control" className="ma-tarjeta ma-sri-organismos">
        <div className="ma-sri-organismos-texto">
          <h3>Otros organismos de control</h3>
          <span>
            Formatos de la Superintendencia de Compañías y de la Superintendencia de Bancos (SBS): estados
            financieros, nómina de accionistas e informes, contra la contabilidad y las declaraciones del SRI.
          </span>
        </div>
        <span className="ma-sri-organismos-badge">Por definir alcance</span>
      </section>

      <div className="ma-sri-nota-pie">
        <span className="ma-sri-nota-pie-barra" aria-hidden="true" />
        <span>
          Catálogo de declaraciones y anexos a validar con el área tributaria de la firma. Las credenciales del
          SRI del cliente nunca pasan por el motor.
        </span>
      </div>
    </section>
  );
}
