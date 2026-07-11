import { useMemo, useState } from "react";

/* ============================================================
   Hoja de trabajo del ERI editable: cuentas + los subtotales de
   la cascada (ganancia bruta → utilidad operativa → antes de IR →
   operaciones → utilidad neta → resultado integral). Al editar un
   saldo se re-rollea por prefijo y se recalcula la cascada EN VIVO.
   `data` = { ori, rows: [[cod, etiqueta, ant, act, esSeccion, esHoja], ...] }
   ============================================================ */

const r2 = (n) => Math.round((Number(n) || 0) * 100) / 100;
const money = (n) =>
  n === null || n === undefined || n === ""
    ? ""
    : (Number(n) || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const SUBTOT = { "402": "gb", "600": "uo", "602": "uai", "604": "uop", "607": "un", "707": "un" };
const ORI_CODES = new Set(["800", "80005"]);

export default function HojaTrabajoERI({ data }) {
  const base = data.rows || [];
  const ori = r2(data.ori);
  const [edits, setEdits] = useState({});

  const { rows, casc } = useMemo(() => {
    const leaves = base.filter((r) => r[5]);
    const rollAct = (p) => r2(leaves.reduce((a, r) =>
      a + (String(r[0]).startsWith(p) ? (edits[r[0]] !== undefined ? Number(edits[r[0]]) || 0 : r[3]) : 0), 0));
    const rollAnt = (p) => r2(leaves.reduce((a, r) => a + (String(r[0]).startsWith(p) ? r[2] : 0), 0));
    const cascada = (roll) => {
      const i401 = roll("401"), i403 = roll("403"), c501 = roll("501"), g502 = roll("502");
      const p601 = roll("601"), ir603 = roll("603"), gd605 = roll("605"), id606 = roll("606");
      const gb = r2(i401 - c501);
      const uo = r2(i401 + i403 - c501 - g502);
      const uai = r2(uo - p601);
      const uop = r2(uai - ir603);
      const un = r2(uop - gd605 + id606);
      return { gb, uo, uai, uop, un };
    };
    const cAct = cascada(rollAct), cAnt = cascada(rollAnt);
    const riAct = r2(cAct.un + ori);

    const valFor = (cod, cascada2, roll, isAnt) => {
      if (SUBTOT[cod]) return cascada2[SUBTOT[cod]];
      if (ORI_CODES.has(cod)) return isAnt ? 0 : ori;
      if (cod === "801") return isAnt ? cascada2.un : riAct;
      return roll(cod);
    };

    const rows = base.map((r) => {
      const cod = r[0], etiqueta = r[1], esSec = !!r[4];
      const editable = !SUBTOT[cod] && !ORI_CODES.has(cod) && cod !== "801";
      const act = valFor(cod, cAct, rollAct, false);
      const ant = valFor(cod, cAnt, rollAnt, true);
      return { cod, etiqueta, esSec, editable, ant, act, variacion: r2(act - ant),
        rawAct: edits[cod] !== undefined ? edits[cod] : r[3] };
    });
    return { rows, casc: { un: cAct.un, ri: riAct } };
  }, [base, edits, ori]);

  return (
    <div className="fx-ht">
      <div className="fx-ht-bar">
        <span className="fx-ht-af ok"><span className="pc-dot ok" /> Utilidad neta: {money(casc.un)}</span>
        <span className="fx-ht-af ok"><span className="pc-dot ok" /> Resultado integral: {money(casc.ri)}</span>
        <span className="fx-ht-hint">Editá <b>Saldo actual</b> (verde) y presioná Enter — la cascada recalcula en vivo.</span>
      </div>
      <div className="fx-ht-scroll">
        <table className="fx-ht-tbl">
          <thead>
            <tr>
              <th className="c0">Código</th>
              <th className="c1">Cuenta</th>
              <th className="num">Saldo ant.</th>
              <th className="num edit">Saldo actual</th>
              <th className="num">Variación</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((x) => {
              const esSub = !!SUBTOT[x.cod] || ORI_CODES.has(x.cod) || x.cod === "801";
              return (
                <tr key={x.cod} className={x.esSec || esSub ? "sec" : ""}>
                  <td className="c0 cod">{x.cod}</td>
                  <td className="c1">{x.etiqueta}</td>
                  <td className="num">{money(x.ant)}</td>
                  <td className="num edit">
                    {x.editable ? (
                      <input
                        className="fx-ht-in"
                        value={edits[x.cod] !== undefined ? edits[x.cod] : x.rawAct}
                        onChange={(e) => setEdits((p) => ({ ...p, [x.cod]: e.target.value }))}
                        inputMode="decimal"
                      />
                    ) : (
                      money(x.act)
                    )}
                  </td>
                  <td className="num">{money(x.variacion)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
