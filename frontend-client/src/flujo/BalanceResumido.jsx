/* ============================================================
   Balance resumido — Estado de Resultados + ESF condensados.
   Dos bloques con columnas Año actual / Año anterior; filas de
   total resaltadas.
   `data` = { er: [{concepto,act,ant,es_total}], esf: [...] }
   ============================================================ */

const money = (n) =>
  n === null || n === undefined || n === "" || Number(n) === 0
    ? "–"
    : (Number(n) || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function Bloque({ titulo, filas }) {
  return (
    <table className="fx-ht-tbl fx-nt" style={{ marginBottom: 14 }}>
      <thead>
        <tr>
          <th className="c1">{titulo}</th>
          <th className="num">Año actual</th>
          <th className="num">Año anterior</th>
        </tr>
      </thead>
      <tbody>
        {(filas || []).map((f, i) => (
          <tr key={i} className={f.es_total ? "fx-nt-tot" : ""}>
            <td className={f.es_total ? "" : "det"}>{f.concepto}</td>
            <td className="num">{money(f.act)}</td>
            <td className="num">{money(f.ant)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function BalanceResumido({ data }) {
  return (
    <div className="fx-ht">
      <div className="fx-ht-bar">
        <span className="fx-ht-af ok">
          <span className="pc-dot ok" /> Estado de Resultados + Situación Financiera condensados
        </span>
        <span className="fx-ht-hint">Versión resumida (año actual y anterior). El detalle completo está en las secciones ESF, ERI y Notas.</span>
      </div>
      <div className="fx-ht-scroll">
        <Bloque titulo="Estado de Resultados" filas={data?.er} />
        <Bloque titulo="Estado de Situación Financiera" filas={data?.esf} />
      </div>
    </div>
  );
}
