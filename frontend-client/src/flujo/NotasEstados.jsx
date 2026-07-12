/* ============================================================
   Notas a los Estados Financieros — desglose por rubro.
   Por cada rubro: encabezado (código + nombre + años), cuentas
   de detalle con saldo anterior/actual, y subtotal del rubro.
   `data` = { esf: [nota...], eri: [nota...] }
   nota = { codigo, nombre, filas:[{codigo,nombre,ant,act}], total_ant, total_act }
   ============================================================ */

const money = (n) =>
  n === null || n === undefined || n === "" || Number(n) === 0
    ? "–"
    : (Number(n) || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function Bloque({ titulo, notas }) {
  if (!notas || !notas.length) return null;
  return (
    <>
      <tr className="fx-nt-blk">
        <td colSpan={4}>{titulo}</td>
      </tr>
      {notas.map((nt) => (
        <NotaRubro key={nt.codigo} nt={nt} />
      ))}
    </>
  );
}

function NotaRubro({ nt }) {
  return (
    <>
      <tr className="fx-nt-hd">
        <td className="cod">{nt.codigo}</td>
        <td>{nt.nombre}</td>
        <td className="num">Anterior</td>
        <td className="num">Actual</td>
      </tr>
      {nt.filas.map((f, i) => (
        <tr key={i}>
          <td className="cod det">{f.codigo}</td>
          <td className="det">{f.nombre}</td>
          <td className="num">{money(f.ant)}</td>
          <td className="num">{money(f.act)}</td>
        </tr>
      ))}
      <tr className="fx-nt-tot">
        <td />
        <td>Subtotal {nt.nombre}</td>
        <td className="num">{money(nt.total_ant)}</td>
        <td className="num">{money(nt.total_act)}</td>
      </tr>
    </>
  );
}

export default function NotasEstados({ data }) {
  const esf = data?.esf || [];
  const eri = data?.eri || [];
  const nNotas = esf.length + eri.length;

  return (
    <div className="fx-ht">
      <div className="fx-ht-bar">
        <span className="fx-ht-af ok">
          <span className="pc-dot ok" /> {nNotas} notas · desglose por rubro
        </span>
        <span className="fx-ht-hint">
          Cada rubro con su detalle de cuentas (año anterior y actual) y subtotal. El archivo va en el Excel.
        </span>
      </div>
      <div className="fx-ht-scroll">
        <table className="fx-ht-tbl fx-nt">
          <thead>
            <tr>
              <th className="c0">Código</th>
              <th className="c1">Cuenta</th>
              <th className="num">Saldo anterior</th>
              <th className="num">Saldo actual</th>
            </tr>
          </thead>
          <tbody>
            <Bloque titulo="Estado de Situación Financiera" notas={esf} />
            <Bloque titulo="Estado de Resultados Integral" notas={eri} />
          </tbody>
        </table>
      </div>
    </div>
  );
}
