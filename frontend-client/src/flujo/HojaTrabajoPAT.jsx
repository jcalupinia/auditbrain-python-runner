import { useMemo, useState } from "react";

/* ============================================================
   Estado de Evolución del Patrimonio · editable por componente.
   Cada componente (Capital, Reservas, Resultados…) con su saldo
   inicial y saldo final EDITABLE; la variación por componente y el
   TOTAL PATRIMONIO se recalculan en vivo.
   `data` = { rows: [[etiqueta, codigo, saldo_inicial, saldo_final], ...] }
   ============================================================ */

const r2 = (n) => Math.round((Number(n) || 0) * 100) / 100;
const money = (n) =>
  n === null || n === undefined || n === ""
    ? ""
    : (Number(n) || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function HojaTrabajoPAT({ data }) {
  const base = data.rows || [];
  const [edits, setEdits] = useState({});

  const { rows, tot } = useMemo(() => {
    const rows = base.map((r) => {
      const label = r[0], cod = r[1], ini = r2(r[2]);
      const fin = r2(edits[cod] !== undefined ? edits[cod] : r[3]);
      return { label, cod, ini, fin, variacion: r2(fin - ini), raw: edits[cod] !== undefined ? edits[cod] : r[3] };
    });
    const ini = r2(rows.reduce((a, x) => a + x.ini, 0));
    const fin = r2(rows.reduce((a, x) => a + x.fin, 0));
    return { rows, tot: { ini, fin, variacion: r2(fin - ini) } };
  }, [base, edits]);

  return (
    <div className="fx-ht">
      <div className="fx-ht-bar">
        <span className="fx-ht-af ok"><span className="pc-dot ok" /> Total patrimonio: {money(tot.fin)}</span>
        <span className="fx-ht-hint">Editá el <b>Saldo final</b> (verde) de cada componente y presioná Enter — el total recalcula en vivo.</span>
      </div>
      <div className="fx-ht-scroll">
        <table className="fx-ht-tbl">
          <thead>
            <tr>
              <th className="c1">Componente</th>
              <th className="num">Saldo inicial</th>
              <th className="num">Variación</th>
              <th className="num edit">Saldo final</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((x) => (
              <tr key={x.cod}>
                <td className="c1">{x.label}</td>
                <td className="num">{money(x.ini)}</td>
                <td className="num">{money(x.variacion)}</td>
                <td className="num edit">
                  <input
                    className="fx-ht-in"
                    value={edits[x.cod] !== undefined ? edits[x.cod] : x.raw}
                    onChange={(e) => setEdits((p) => ({ ...p, [x.cod]: e.target.value }))}
                    inputMode="decimal"
                  />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="tot">
              <td className="c1">TOTAL PATRIMONIO</td>
              <td className="num">{money(tot.ini)}</td>
              <td className="num">{money(tot.variacion)}</td>
              <td className="num act">{money(tot.fin)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
