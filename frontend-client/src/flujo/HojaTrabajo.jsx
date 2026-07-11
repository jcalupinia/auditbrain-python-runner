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
      const actividad = r[4] || "", esSec = !!r[5], esHoja = !!r[6];
      const variacion = r2(act - ant);
      const usos = variacion > 0 ? variacion : 0;       // uso (positivo, como el Excel)
      const fuentes = variacion < 0 ? -variacion : 0;   // fuente (positivo)
      const impacto = r2(fuentes - usos);               // = −variación (impacto al efectivo)
      const esEfectivo = String(cod).startsWith(efe);
      const clasifica = !!actividad && !esEfectivo && !esSec;
      return {
        cod, etiqueta, ant, act, actividad, esSec, esHoja,
        variacion, saldos: variacion, usos, fuentes,
        op: clasifica && actividad === "OPERACION" ? impacto : null,
        inv: clasifica && actividad === "INVERSION" ? impacto : null,
        fin: clasifica && actividad === "FINANCIAMIENTO" ? impacto : null,
      };
    });
    const sum = (f) => r2(rows.reduce((a, x) => a + (f(x) || 0), 0));
    const op = sum((x) => x.op), inv = sum((x) => x.inv), fin = sum((x) => x.fin);
    const neto = r2(op + inv + fin);
    // Totales por columna de la fila CUADRADO — como el Excel: se suman sobre
    // las cuentas HOJA (variación total = 0; usos = fuentes = balance del papel).
    const hojas = rows.filter((x) => x.esHoja);
    const varTot = r2(hojas.reduce((a, x) => a + x.variacion, 0));
    const usosTot = r2(hojas.reduce((a, x) => a + x.usos, 0));
    const fuentesTot = r2(hojas.reduce((a, x) => a + x.fuentes, 0));
    const efeRow = rows.find((x) => x.cod === efe) || base.find && rows.find((x) => String(x.cod).startsWith(efe));
    const efIni = efeRow ? efeRow.ant : 0;
    const efReal = efeRow ? efeRow.act : 0;
    const efFin = r2(efIni + neto);
    const cuadre = r2(efFin - efReal);
    // Cuadre ESF (A = P + Pat) por rollup en vivo de las cuentas hoja.
    const sumLeaf = (p) => r2(rows.reduce((a, x) => a + (x.esHoja && String(x.cod).startsWith(p) ? x.act : 0), 0));
    const activo = sumLeaf("1"), pasivo = sumLeaf("2"), patrimonio = sumLeaf("3");
    const totalPP = r2(-(pasivo + patrimonio));
    const cuadreEsf = r2(activo + pasivo + patrimonio);
    return { rows, tot: { op, inv, fin, neto, efIni, efFin, efReal, cuadre, activo, totalPP, cuadreEsf, varTot, usosTot, fuentesTot } };
  }, [base, edits, efe]);

  const cuadra = Math.abs(tot.cuadre) <= 1;
  const cuadraEsf = Math.abs(tot.cuadreEsf) <= 1;
  const extra = data.extracontable || [];

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
              <td className="c0" />
              <td className="c1" style={{ textAlign: "right" }}>CUADRADO · TOTALES →</td>
              <td className="num" />
              <td className="num" />
              <td className="num">{money(tot.varTot)}</td>
              <td className="num">{money(tot.varTot)}</td>
              <td className="num">{money(tot.usosTot)}</td>
              <td className="num">{money(tot.fuentesTot)}</td>
              <td className="num act">{money(tot.op)}</td>
              <td className="num act">{money(tot.inv)}</td>
              <td className="num act">{money(tot.fin)}</td>
            </tr>
            <tr className="tot2">
              <td className="c0" />
              <td className="c1">Incremento neto {money(tot.neto)}</td>
              <td className="num" colSpan={3}>Efectivo inicial {money(tot.efIni)}</td>
              <td className="num" colSpan={2}>Efectivo final {money(tot.efFin)}</td>
              <td className="num act" colSpan={3}>AF {money(tot.cuadre)}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Cuadre del balance A = P + Pat */}
      <div className="fx-ht-sum">
        <div className="fx-ht-sc">
          <span className="fx-ht-sl">Total activo</span>
          <span className="fx-ht-sv">{money(tot.activo)}</span>
        </div>
        <div className="fx-ht-sc">
          <span className="fx-ht-sl">Total pasivo + patrimonio</span>
          <span className="fx-ht-sv">{money(tot.totalPP)}</span>
        </div>
        <div className={`fx-ht-sc ${cuadraEsf ? "ok" : "bad"}`}>
          <span className="fx-ht-sl">Cuadrado (A = P + Pat)</span>
          <span className="fx-ht-sv"><span className={`pc-dot ${cuadraEsf ? "ok" : "bad"}`} /> {money(tot.cuadreEsf)}</span>
        </div>
      </div>

      {/* Información extracontable ORI */}
      {extra.length > 0 && (
        <div className="fx-ht-extra">
          <div className="fx-ht-extra-h">Información extracontable · Otro Resultado Integral (ORI)</div>
          <div className="fx-ht-scroll" style={{ maxHeight: "none" }}>
            <table className="fx-ht-tbl">
              <thead>
                <tr>
                  <th className="c0">Código</th>
                  <th className="c1">Cuenta</th>
                  <th className="num">Balance ant.</th>
                  <th className="num">Balance actual</th>
                  <th className="num">Variación (ORI)</th>
                </tr>
              </thead>
              <tbody>
                {extra.map((e) => (
                  <tr key={e[0]}>
                    <td className="c0 cod">{e[0]}</td>
                    <td className="c1">{e[1]}</td>
                    <td className="num">{money(e[2])}</td>
                    <td className="num">{money(e[3])}</td>
                    <td className="num" style={{ color: "var(--accent)" }}>{money(e[4])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
