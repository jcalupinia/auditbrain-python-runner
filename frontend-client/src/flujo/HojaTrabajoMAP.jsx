import { useMemo, useState } from "react";

/* ============================================================
   Homologación (Mapeo) · balanza editable estilo Excel.
   Cuenta · Código Super Cías · Código SRI · Saldo (editable).
   El total de control (≈ 0) se recalcula en vivo.
   `data` = { rows: [[cuenta, super_cias, sri, saldo], ...] }
   ============================================================ */

const r2 = (n) => Math.round((Number(n) || 0) * 100) / 100;
const money = (n) => (Number(n) || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function HojaTrabajoMAP({ data }) {
  const base = data.rows || [];
  const [edits, setEdits] = useState({});

  const total = useMemo(
    () => r2(base.reduce((a, r, i) => a + (edits[i] !== undefined ? Number(edits[i]) || 0 : r[3]), 0)),
    [base, edits]
  );
  const cuadra = Math.abs(total) <= 1;

  return (
    <div className="fx-ht">
      <div className="fx-ht-bar">
        <span className={`fx-ht-af ${cuadra ? "ok" : "bad"}`}>
          <span className={`pc-dot ${cuadra ? "ok" : "bad"}`} /> Control (≈ 0): {money(total)}
        </span>
        <span className="fx-ht-hint">Editá el <b>Saldo</b> (verde) de cualquier cuenta — el control recalcula en vivo. {base.length} cuentas.</span>
      </div>
      <div className="fx-ht-scroll">
        <table className="fx-ht-tbl">
          <thead>
            <tr>
              <th className="c0">Código Super Cías</th>
              <th className="c1">Cuenta contable</th>
              <th className="num">Código SRI</th>
              <th className="num edit">Saldo</th>
            </tr>
          </thead>
          <tbody>
            {base.map((r, i) => (
              <tr key={i}>
                <td className="c0 cod">{r[1]}</td>
                <td className="c1">{r[0]}</td>
                <td className="num">{r[2]}</td>
                <td className="num edit">
                  <input
                    className="fx-ht-in"
                    value={edits[i] !== undefined ? edits[i] : r[3]}
                    onChange={(e) => setEdits((p) => ({ ...p, [i]: e.target.value }))}
                    inputMode="decimal"
                  />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="tot">
              <td className="c0" />
              <td className="c1" style={{ textAlign: "right" }}>TOTAL (control ≈ 0) →</td>
              <td className="num" />
              <td className="num act">{money(total)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
