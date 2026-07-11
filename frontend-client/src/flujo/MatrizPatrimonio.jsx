/* ============================================================
   Matriz oficial del Estado de Cambios en el Patrimonio (99xx).
   16 filas de movimiento × 18 columnas de componente + TOTAL,
   con encabezados agrupados (Reservas / ORI / Resultados acum.).
   Scroll horizontal. Presentación oficial (los saldos se editan en
   el ESF; esta matriz los refleja).
   `data` = { columnas:[{codigo,nombre}], grupos:[{nombre,cols}], filas:[{codigo,nombre,celdas:{comp:val,total}}] }
   ============================================================ */

const money = (n) =>
  n === null || n === undefined || n === "" || Number(n) === 0
    ? "–"
    : (Number(n) || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const SECCIONES = new Set(["99", "9901", "9902"]);

export default function MatrizPatrimonio({ data }) {
  const cols = data.columnas || [];
  const grupos = data.grupos || [];
  const filas = data.filas || [];
  const total99 = filas.find((f) => f.codigo === "99");

  return (
    <div className="fx-ht">
      <div className="fx-ht-bar">
        <span className="fx-ht-af ok">
          <span className="pc-dot ok" /> Total patrimonio: {total99 ? money(total99.celdas.total) : "–"}
        </span>
        <span className="fx-ht-hint">Matriz oficial 99xx · {filas.length} movimientos × {cols.length} componentes. Desplazá → para ver todas las columnas.</span>
      </div>
      <div className="fx-ht-scroll">
        <table className="fx-ht-tbl fx-mx">
          <thead>
            <tr>
              <th className="c0" rowSpan={2}>Cód.</th>
              <th className="c1" rowSpan={2}>Movimiento</th>
              {grupos.map((g, i) => (
                <th key={i} className="grp" colSpan={g.cols.length}>{g.nombre || " "}</th>
              ))}
              <th className="num tot" rowSpan={2}>TOTAL PATRIMONIO</th>
            </tr>
            <tr>
              {cols.map((c) => (
                <th key={c.codigo} className="num comp" title={c.nombre}>
                  <span className="cc">{c.codigo}</span>
                  <span className="cn">{c.nombre}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => (
              <tr key={f.codigo} className={SECCIONES.has(f.codigo) ? "sec" : ""}>
                <td className="c0 cod">{f.codigo}</td>
                <td className="c1">{f.nombre}</td>
                {cols.map((c) => (
                  <td key={c.codigo} className="num">{money(f.celdas[c.codigo])}</td>
                ))}
                <td className="num tot">{money(f.celdas.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
