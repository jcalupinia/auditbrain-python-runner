import { useMemo, useState } from "react";

/* ============================================================
   Hoja de trabajo del ESF estilo Excel: todas las columnas del
   working paper (balances, variación, saldos, usos, fuentes,
   actividades del flujo, y la fila de totales con el cuadre AF).
   Scroll horizontal + saldos editables con recálculo EN VIVO.
   `data` = { prefijo_efectivo, rows: [[cod, etiqueta, ant, act, actividad, esSeccion], ...] }
   ============================================================ */

const r2 = (n) => Math.round((Number(n) || 0) * 100) / 100;
const money = (n) =>
  n === null || n === undefined || n === ""
    ? ""
    : (Number(n) || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function HojaTrabajo({ data }) {
  const efe = data.prefijo_efectivo || "10101";
  const base = data.rows || [];
  const [edits, setEdits] = useState({});

  const { rows, tot } = useMemo(() => {
    const rows = base.map((r) => {
      const cod = r[0], etiqueta = r[1], ant = r2(r[2]);
      const act = r2(edits[cod] !== undefined ? edits[cod] : r[3]);
      const actividad = r[4] || "", esSec = !!r[5];
      const variacion = r2(act - ant);
      const usos = variacion > 0 ? -variacion : 0;      // aumento de saldo = uso
      const fuentes = variacion < 0 ? -variacion : 0;   // disminución = fuente
      const impacto = r2(usos + fuentes);
      const esEfectivo = String(cod).startsWith(efe);
      const clasifica = !!actividad && !esEfectivo && !esSec;
      return {
        cod, etiqueta, ant, act, actividad, esSec,
        variacion, saldos: variacion, usos, fuentes,
        op: clasifica && actividad === "OPERACION" ? impacto : null,
        inv: clasifica && actividad === "INVERSION" ? impacto : null,
        fin: clasifica && actividad === "FINANCIAMIENTO" ? impacto : null,
      };
    });
    const sum = (f) => r2(rows.reduce((a, x) => a + (f(x) || 0), 0));
    const op = sum((x) => x.op), inv = sum((x) => x.inv), fin = sum((x) => x.fin);
    const neto = r2(op + inv + fin);
    const efeRow = rows.find((x) => x.cod === efe) || base.find && rows.find((x) => String(x.cod).startsWith(efe));
    const efIni = efeRow ? efeRow.ant : 0;
    const efReal = efeRow ? efeRow.act : 0;
    const efFin = r2(efIni + neto);
    const cuadre = r2(efFin - efReal);
    return { rows, tot: { op, inv, fin, neto, efIni, efFin, efReal, cuadre } };
  }, [base, edits, efe]);

  const cuadra = Math.abs(tot.cuadre) <= 1;

  return (
    <div className="fx-ht">
      <div className="fx-ht-bar">
        <span className={`fx-ht-af ${cuadra ? "ok" : "bad"}`}>
          <span className={`pc-dot ${cuadra ? "ok" : "bad"}`} /> Cuadre AF: {money(tot.cuadre)}
        </span>
        <span className="fx-ht-hint">Editá la columna <b>Balance actual</b> (verde) — recalcula en vivo. Desplazá → para ver todas las columnas.</span>
      </div>
      <div className="fx-ht-scroll">
        <table className="fx-ht-tbl">
          <thead>
            <tr>
              <th className="c0">Código</th>
              <th className="c1">Nombre de la cuenta</th>
              <th className="num">Balance ant.</th>
              <th className="num edit">Balance actual</th>
              <th className="num">Variación</th>
              <th className="num">Saldos</th>
              <th className="num">Usos</th>
              <th className="num">Fuentes</th>
              <th className="num act">Operación</th>
              <th className="num act">Inversión</th>
              <th className="num act">Financiamiento</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((x) => (
              <tr key={x.cod} className={x.esSec ? "sec" : ""}>
                <td className="c0 cod">{x.cod}</td>
                <td className="c1">{x.etiqueta}</td>
                <td className="num">{money(x.ant)}</td>
                <td className="num edit">
                  <input
                    className="fx-ht-in"
                    value={edits[x.cod] !== undefined ? edits[x.cod] : x.act}
                    onChange={(e) => setEdits((p) => ({ ...p, [x.cod]: e.target.value }))}
                    inputMode="decimal"
                  />
                </td>
                <td className="num">{money(x.variacion)}</td>
                <td className="num">{money(x.saldos)}</td>
                <td className="num">{money(x.usos)}</td>
                <td className="num">{money(x.fuentes)}</td>
                <td className="num act">{x.op != null ? money(x.op) : ""}</td>
                <td className="num act">{x.inv != null ? money(x.inv) : ""}</td>
                <td className="num act">{x.fin != null ? money(x.fin) : ""}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="tot">
              <td className="c0" colSpan={8} style={{ textAlign: "right" }}>TOTAL ACTIVIDADES →</td>
              <td className="num act">{money(tot.op)}</td>
              <td className="num act">{money(tot.inv)}</td>
              <td className="num act">{money(tot.fin)}</td>
            </tr>
            <tr className="tot2">
              <td className="c0" colSpan={2}>Incremento neto {money(tot.neto)}</td>
              <td className="num" colSpan={3}>Efectivo inicial {money(tot.efIni)}</td>
              <td className="num" colSpan={3}>Efectivo final {money(tot.efFin)}</td>
              <td className="num" colSpan={3}>AF {money(tot.cuadre)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
