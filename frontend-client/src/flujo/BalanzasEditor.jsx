import { useEffect, useMemo, useRef, useState } from "react";

/* ============================================================
   Editor de balanzas — Homologación editable de AMBOS años.
   Vista fusionada estilo Excel: una fila por cuenta con el saldo
   ANTERIOR y ACTUAL editables. Al cambiar cualquier saldo se
   recalcula TODA la herramienta en el servidor (motores validados)
   y se refrescan todas las secciones.

   props:
     ant  = { rows: [[cuenta, super_cias, sri, saldo], ...] }
     act  = { rows: [[cuenta, super_cias, sri, saldo], ...] }
     onRecalc(balAnt, balAct)  → dispara el recálculo (debounced afuera)
     recalculando  → bool (muestra el estado "actualizando…")
   ============================================================ */

const r2 = (n) => Math.round((Number(n) || 0) * 100) / 100;
const money = (n) => (Number(n) || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (v) => (v === "" || v === null || v === undefined ? 0 : Number(v) || 0);

// Une ambas balanzas por cuenta (código contable completo, único).
function fusionar(rowsAnt, rowsAct) {
  const idx = new Map();
  const push = (r, col) => {
    const cuenta = String(r[0] || "");
    const key = cuenta || `${r[1]}·${col}`;
    if (!idx.has(key)) idx.set(key, { cuenta, super_cias: r[1] || "", sri: r[2] || "", ant: "", act: "" });
    idx.get(key)[col] = r[3];
    // completa metadatos si faltaban
    const o = idx.get(key);
    if (!o.super_cias) o.super_cias = r[1] || "";
    if (!o.sri) o.sri = r[2] || "";
  };
  (rowsAnt || []).forEach((r) => push(r, "ant"));
  (rowsAct || []).forEach((r) => push(r, "act"));
  return Array.from(idx.values());
}

export default function BalanzasEditor({ ant, act, onRecalc, recalculando }) {
  const baseFusion = useMemo(() => fusionar(ant?.rows, act?.rows), [ant, act]);
  // estado editable: { [i]: {ant, act} }  (solo overrides)
  const [edits, setEdits] = useState({});
  const [filtro, setFiltro] = useState("");
  const primerRender = useRef(true);

  // cuando cambian los datos base (nuevo recálculo del server), limpiamos overrides
  useEffect(() => { setEdits({}); }, [ant, act]);

  const valAnt = (i) => (edits[i]?.ant !== undefined ? edits[i].ant : baseFusion[i].ant);
  const valAct = (i) => (edits[i]?.act !== undefined ? edits[i].act : baseFusion[i].act);

  const totAnt = useMemo(() => r2(baseFusion.reduce((a, _r, i) => a + num(valAnt(i)), 0)), [baseFusion, edits]);
  const totAct = useMemo(() => r2(baseFusion.reduce((a, _r, i) => a + num(valAct(i)), 0)), [baseFusion, edits]);

  const setCell = (i, col, v) =>
    setEdits((p) => ({ ...p, [i]: { ...p[i], [col]: v } }));

  // reconstruye ambas balanzas desde el estado editable
  const construir = () => {
    const balAnt = [];
    const balAct = [];
    baseFusion.forEach((row, i) => {
      const a = valAnt(i);
      const c = valAct(i);
      const meta = { cuenta: row.cuenta, super_cias: row.super_cias, sri: row.sri };
      if (a !== "" && a !== null && a !== undefined) balAnt.push({ ...meta, saldo: num(a) });
      if (c !== "" && c !== null && c !== undefined) balAct.push({ ...meta, saldo: num(c) });
    });
    return [balAnt, balAct];
  };

  // recálculo debounced ante cualquier edición
  useEffect(() => {
    if (primerRender.current) { primerRender.current = false; return; }
    if (!Object.keys(edits).length) return;
    const t = setTimeout(() => {
      const [balAnt, balAct] = construir();
      onRecalc(balAnt, balAct);
    }, 700);
    return () => clearTimeout(t);
  }, [edits]); // eslint-disable-line react-hooks/exhaustive-deps

  const filas = useMemo(() => {
    if (!filtro.trim()) return baseFusion.map((r, i) => [r, i]);
    const q = filtro.trim().toLowerCase();
    return baseFusion
      .map((r, i) => [r, i])
      .filter(([r]) => `${r.cuenta} ${r.super_cias} ${r.sri}`.toLowerCase().includes(q));
  }, [baseFusion, filtro]);

  return (
    <div className="fx-ht">
      <div className="fx-ht-bar">
        <span className={`fx-ht-af ${recalculando ? "" : "ok"}`}>
          <span className={`pc-dot ${recalculando ? "" : "ok"}`} />
          {recalculando ? "Recalculando toda la herramienta…" : "Editá cualquier saldo — todo se recalcula solo"}
        </span>
        <span className="fx-ht-hint">
          {baseFusion.length} cuentas · Anterior Σ {money(totAnt)} · Actual Σ {money(totAct)}
        </span>
      </div>
      <div style={{ padding: "6px 10px" }}>
        <input
          className="fx-ht-in"
          style={{ width: "min(320px, 100%)" }}
          placeholder="Filtrar por cuenta / código Super Cías / SRI…"
          value={filtro}
          onChange={(e) => setFiltro(e.target.value)}
        />
      </div>
      <div className="fx-ht-scroll">
        <table className="fx-ht-tbl">
          <thead>
            <tr>
              <th className="c0">Código Super Cías</th>
              <th className="c1">Cuenta contable</th>
              <th className="num">SRI</th>
              <th className="num edit">Saldo anterior</th>
              <th className="num edit">Saldo actual</th>
            </tr>
          </thead>
          <tbody>
            {filas.map(([r, i]) => (
              <tr key={i}>
                <td className="c0 cod">{r.super_cias}</td>
                <td className="c1">{r.cuenta}</td>
                <td className="num">{r.sri}</td>
                <td className="num edit">
                  <input
                    className="fx-ht-in"
                    value={valAnt(i)}
                    onChange={(e) => setCell(i, "ant", e.target.value)}
                    inputMode="decimal"
                  />
                </td>
                <td className="num edit">
                  <input
                    className="fx-ht-in"
                    value={valAct(i)}
                    onChange={(e) => setCell(i, "act", e.target.value)}
                    inputMode="decimal"
                  />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="tot">
              <td className="c0" />
              <td className="c1" style={{ textAlign: "right" }}>TOTALES →</td>
              <td className="num" />
              <td className="num act">{money(totAnt)}</td>
              <td className="num act">{money(totAct)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
