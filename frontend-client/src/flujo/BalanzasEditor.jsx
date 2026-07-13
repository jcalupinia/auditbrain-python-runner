import { useEffect, useMemo, useRef, useState } from "react";

/* ============================================================
   Editor de balanzas — Homologación editable de AMBOS años.
   Vista fusionada estilo Excel: una fila por cuenta con el
   Código Super Cías y Código SRI SELECCIONABLES desde el plan de
   cuentas oficial (datalist con búsqueda) y los saldos ANTERIOR y
   ACTUAL editables. Cualquier cambio (código o saldo) recalcula
   TODA la herramienta en el servidor (motores validados) y refresca
   todas las secciones.

   props:
     ant  = { rows: [[cuenta, super_cias, sri, saldo], ...] }
     act  = { rows: [[cuenta, super_cias, sri, saldo], ...] }
     catalogos = { super: [{codigo,nombre}], sri: [{codigo,nombre}] } | null
     onRecalc(balAnt, balAct)  → dispara el recálculo (debounced)
     recalculando  → bool
   ============================================================ */

const r2 = (n) => Math.round((Number(n) || 0) * 100) / 100;
const money = (n) => (Number(n) || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (v) => (v === "" || v === null || v === undefined ? 0 : Number(v) || 0);

// Une ambas balanzas por cuenta (código contable completo, único).
// Fila de entrada: [cuenta, nombre, super_cias, sri, saldo].
function fusionar(rowsAnt, rowsAct) {
  const idx = new Map();
  const push = (r, col) => {
    const cuenta = String(r[0] || "");
    const nombre = String(r[1] || "");
    const key = cuenta || `${r[2]}·${col}`;
    if (!idx.has(key)) idx.set(key, { cuenta, nombre, super_cias: r[2] || "", sri: r[3] || "", ant: "", act: "" });
    const o = idx.get(key);
    o[col] = r[4];
    if (!o.super_cias) o.super_cias = r[2] || "";
    if (!o.sri) o.sri = r[3] || "";
    if (!o.nombre) o.nombre = nombre;
  };
  (rowsAnt || []).forEach((r) => push(r, "ant"));
  (rowsAct || []).forEach((r) => push(r, "act"));
  return Array.from(idx.values());
}

const SUPER_LIST_ID = "fx-plan-super";
const SRI_LIST_ID = "fx-plan-sri";

export default function BalanzasEditor({ ant, act, catalogos, onRecalc, recalculando }) {
  const baseFusion = useMemo(() => fusionar(ant?.rows, act?.rows), [ant, act]);
  // estado editable: { [i]: {ant?, act?, super_cias?, sri?} } (solo overrides)
  const [edits, setEdits] = useState({});
  const [filtro, setFiltro] = useState("");
  const primerRender = useRef(true);

  // al llegar un nuevo recálculo del server, los datos base cambian → limpiamos overrides
  useEffect(() => { setEdits({}); }, [ant, act]);

  // mapas código → nombre para mostrar el nombre de la cuenta seleccionada
  const nombreSuper = useMemo(() => {
    const m = new Map();
    (catalogos?.super || []).forEach((c) => m.set(c.codigo, c.nombre));
    return m;
  }, [catalogos]);
  const nombreSri = useMemo(() => {
    const m = new Map();
    (catalogos?.sri || []).forEach((c) => m.set(c.codigo, c.nombre));
    return m;
  }, [catalogos]);

  const val = (i, col, base) => (edits[i]?.[col] !== undefined ? edits[i][col] : base);
  const valAnt = (i) => val(i, "ant", baseFusion[i].ant);
  const valAct = (i) => val(i, "act", baseFusion[i].act);
  const valSuper = (i) => val(i, "super_cias", baseFusion[i].super_cias);
  const valSri = (i) => val(i, "sri", baseFusion[i].sri);

  const totAnt = useMemo(() => r2(baseFusion.reduce((a, _r, i) => a + num(valAnt(i)), 0)), [baseFusion, edits]);
  const totAct = useMemo(() => r2(baseFusion.reduce((a, _r, i) => a + num(valAct(i)), 0)), [baseFusion, edits]);

  const setCell = (i, col, v) => setEdits((p) => ({ ...p, [i]: { ...p[i], [col]: v } }));

  // reconstruye ambas balanzas desde el estado editable (código + saldo)
  const construir = () => {
    const balAnt = [];
    const balAct = [];
    baseFusion.forEach((row, i) => {
      const meta = { cuenta: row.cuenta, nombre: row.nombre, super_cias: String(valSuper(i) || ""), sri: String(valSri(i) || "") };
      const a = valAnt(i);
      const c = valAct(i);
      if (a !== "" && a !== null && a !== undefined) balAnt.push({ ...meta, saldo: num(a) });
      if (c !== "" && c !== null && c !== undefined) balAct.push({ ...meta, saldo: num(c) });
    });
    return [balAnt, balAct];
  };

  // recálculo debounced ante cualquier edición (código o saldo)
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
      .filter(([r]) => `${r.cuenta} ${r.nombre} ${r.super_cias} ${r.sri}`.toLowerCase().includes(q));
  }, [baseFusion, filtro]);

  const tieneCatalogo = !!(catalogos?.super?.length);

  return (
    <div className="fx-ht">
      {/* datalists del plan de cuentas (se comparten entre todas las filas) */}
      {tieneCatalogo && (
        <>
          <datalist id={SUPER_LIST_ID}>
            {catalogos.super.map((c) => (
              <option key={c.codigo + c.nombre} value={c.codigo}>{c.nombre}</option>
            ))}
          </datalist>
          <datalist id={SRI_LIST_ID}>
            {catalogos.sri.map((c) => (
              <option key={c.codigo} value={c.codigo}>{c.nombre}</option>
            ))}
          </datalist>
        </>
      )}

      <div className="fx-ht-bar">
        <span className={`fx-ht-af ${recalculando ? "" : "ok"}`}>
          <span className={`pc-dot ${recalculando ? "" : "ok"}`} />
          {recalculando ? "Recalculando toda la herramienta…" : "Editá saldos o corregí códigos — todo se recalcula solo"}
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
              <th className="c1">Cuenta contable</th>
              <th className="edit" style={{ minWidth: 190 }}>Código Super Cías</th>
              <th className="edit" style={{ minWidth: 150 }}>Código SRI</th>
              <th className="num edit">Saldo anterior</th>
              <th className="num edit">Saldo actual</th>
            </tr>
          </thead>
          <tbody>
            {filas.map(([r, i]) => {
              const sc = String(valSuper(i) || "");
              const sr = String(valSri(i) || "");
              return (
                <tr key={i}>
                  <td className="c1" title={`${r.cuenta} · ${r.nombre}`}>
                    <span className="fx-ht-cod-cli">{r.cuenta}</span>
                    <span className="fx-ht-nom">{r.nombre}</span>
                  </td>
                  <td className="edit">
                    <input
                      className="fx-ht-in cod"
                      list={tieneCatalogo ? SUPER_LIST_ID : undefined}
                      value={sc}
                      title={nombreSuper.get(sc) || ""}
                      onChange={(e) => setCell(i, "super_cias", e.target.value)}
                    />
                    <span className="fx-ht-nom">{nombreSuper.get(sc) || ""}</span>
                  </td>
                  <td className="edit">
                    <input
                      className="fx-ht-in cod"
                      list={tieneCatalogo ? SRI_LIST_ID : undefined}
                      value={sr}
                      title={nombreSri.get(sr) || ""}
                      onChange={(e) => setCell(i, "sri", e.target.value)}
                    />
                    <span className="fx-ht-nom">{nombreSri.get(sr) || ""}</span>
                  </td>
                  <td className="num edit">
                    <input className="fx-ht-in" value={valAnt(i)} onChange={(e) => setCell(i, "ant", e.target.value)} inputMode="decimal" />
                  </td>
                  <td className="num edit">
                    <input className="fx-ht-in" value={valAct(i)} onChange={(e) => setCell(i, "act", e.target.value)} inputMode="decimal" />
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="tot">
              <td className="c1" style={{ textAlign: "right" }}>TOTALES →</td>
              <td />
              <td />
              <td className="num act">{money(totAnt)}</td>
              <td className="num act">{money(totAct)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
