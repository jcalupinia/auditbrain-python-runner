import "./HojaDeRuta.css";

// Transcripción de HojaDeRuta.dc.html (Task 4). Bloques del lienzo → bloques
// del JSX: 1) cabecera (folio + título + leyenda); 2) grid de 17 tarjetas SP;
// 3) nota de punto de corte. HojaDeRuta no lleva <EnConstruccion /> (regla
// #5: es informativa, no una página del motor en sí).
//
// Estado corregido a hoy (regla de conversión #5 de la Task 4, sobre el
// estado real del proyecto): SP1-A y SP1-B pasan a "Terminado" (el lienzo
// tenía SP1-B como "curso") y SP2 pasa a "En curso" (el lienzo lo tenía como
// "pend"). El resto del contenido (títulos, textos, salidas, roadmap) es el
// del lienzo, sin resumir.

const SPS = [
  { id: "SP1-A", t: "hecho", estado: "Terminado", titulo: "Correcciones del motor", texto: "Evidencia SHA-256, P0 solo por agregación, NIA corregidas, materialidad obligatoria, MUS con límite superior.", salida: "250 pruebas · en main" },
  { id: "SP1-B", t: "hecho", estado: "Terminado", titulo: "Servicio en el servidor", texto: "API con permiso firmado, publicada por Funnel en /motor, revisión de seguridad aprobada.", salida: "Pendiente: 2 variables en Render" },
  { id: "SP2", t: "curso", estado: "En curso", titulo: "Portada en el Command Center", texto: "Portada y subpáginas, subida directa navegador → motor, bandeja de excepciones.", salida: "La tarjeta corre el motor" },
  { id: "SP3", t: "pend", estado: "Fase 1", titulo: "Ingesta y suficiencia", texto: "Mayor, XML emitidos y recibidos, proveedores y nómina; parámetros NIA 320; AST-008 como barrera.", salida: "38 pruebas sobre un mayor real anonimizado" },
  { id: "SP0", t: "pend", estado: "En paralelo", titulo: "Condiciones previas", texto: "Cláusula LOPDP, cifrado del disco, respaldo externo, purga a 8 horas.", salida: "Firmado y restauración ensayada" },
  { id: "SP11", t: "pend", estado: "En paralelo", titulo: "Biblioteca NIIF", texto: "Fichas .md propias con referencia al párrafo: piloto NIC 16, NIC 19 y NIIF 16; luego 29 + 29.", salida: "Manual de ejemplo aprobado" },
  { id: "SP4", t: "pend", estado: "Fase 2", titulo: "Gobierno", texto: "Excepciones en PostgreSQL, bitácora inalterable, aprobación del gerente y firma del socio.", salida: "Primer encargo real" },
  { id: "SP5", t: "pend", estado: "Fase 2", titulo: "Papel de trabajo", texto: "Excel y PDF con el formato de la firma.", salida: "Cédula sin formateo manual" },
  { id: "SP13", t: "pend", estado: "Fase 2", titulo: "Selección de muestras", texto: "Partidas clave, atípicos, dirigida y MUS combinables; cédula; documentos a pedir; evaluación.", salida: "Muestra evaluada sobre un mayor real" },
  { id: "SP6", t: "pend", estado: "Fase 3", titulo: "SRI · comprobantes", texto: "Duplicados en ventas, retención ↔ factura, retención aplicable, empresas fantasmas, robot del SRI.", salida: "Cruces SRI vs contabilidad" },
  { id: "SP14", t: "pend", estado: "Fase 3", titulo: "Importaciones", texto: "Declaración aduanera contra contabilidad, costo de importación, ISD y pagos al exterior, corte.", salida: "Importaciones conciliadas" },
  { id: "SP6-B", t: "pend", estado: "Fase 3", titulo: "SRI · declaraciones y anexos", texto: "F-101 y conciliación del IR, ATS por comprobante, IVA vs F-104, RDEP, dividendos, accionistas, patrimonial.", salida: "Anexos probados" },
  { id: "SP7", t: "pend", estado: "Fase 4", titulo: "Explorador y constructor", texto: "Cubos, búsqueda de conceptos, constructor de reportes, recetas y matriz de asientos manuales.", salida: "Recetas reproducibles" },
  { id: "SP10", t: "pend", estado: "Fase 4", titulo: "Estados financieros", texto: "Horizontal y vertical, ratios y expectativa vs real, sobre el Motor de balances.", salida: "Variaciones de un cliente real" },
  { id: "SP12", t: "pend", estado: "Fase 5", titulo: "Pruebas NIIF y manuales", texto: "Política vs registro, NIC 19, NIIF 16, NIC 12, NIC 36, NIC 37, revelaciones, NIC 8; generador de manuales.", salida: "Manual y excepciones NIIF" },
  { id: "SP8", t: "pend", estado: "Fase 6", titulo: "IA de triaje y redacción", texto: "IA local que propone y redacta, nunca calcula; ICT pasa al gateway local.", salida: "Falsos positivos ≤ 20 %" },
  { id: "SP9+", t: "pend", estado: "Fase 7", titulo: "Expansión", texto: "Dashboards, ML, conectores ERP, bases de datos e ITGC, Supercias y SBS.", salida: "Fases 3 a 5 de v2.0" },
];

export default function HojaDeRuta() {
  return (
    <section className="ma-pagina ma-ruta">
      <div className="ma-ruta-cab">
        <div className="ma-ruta-titulo">
          <span className="ma-ruta-folio">AUT-2026-001 · FORMULARIO v2.5 · BLOQUE Z</span>
          <h2>Hoja de ruta del Motor de Auditoría Analítica</h2>
          <p>Estado al 21 de septiembre de 2026. Los datos reales de clientes entran solo después de SP4.</p>
        </div>
        <div className="ma-ruta-leyenda">
          <span>
            <i className="ma-ruta-punto hecho" />
            Terminado
          </span>
          <span>
            <i className="ma-ruta-punto curso" />
            En curso
          </span>
          <span>
            <i className="ma-ruta-punto pend" />
            Pendiente
          </span>
        </div>
      </div>

      <div className="ma-ruta-grid">
        {SPS.map((s) => (
          <article key={s.id} className={`ma-ruta-tarjeta ${s.t}`}>
            <div className="ma-ruta-tarjeta-cab">
              <span className="ma-ruta-id">{s.id}</span>
              <span className={`ma-ruta-etiqueta ${s.t}`}>{s.estado}</span>
            </div>
            <span className="ma-ruta-titulo-tarjeta">{s.titulo}</span>
            <span className="ma-ruta-texto">{s.texto}</span>
            <span className="ma-ruta-salida">{s.salida}</span>
          </article>
        ))}
      </div>

      <div className="ma-ruta-corte">
        <span className="ma-ruta-barra" aria-hidden="true" />
        <span>
          <strong>Punto de corte:</strong> primer encargo real al cerrar SP4 (registro, aprobaciones y bitácora), con
          cifrado del disco, cláusula LOPDP firmada y falsos positivos ≤ 20&nbsp;% por regla en el piloto anonimizado.
        </span>
      </div>
    </section>
  );
}
