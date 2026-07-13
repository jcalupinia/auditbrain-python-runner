import { useMemo, useRef, useState } from "react";
import { motorBalancesHomologar, motorBalancesRecalcular } from "../api.js";
import "./motorBalances.css";

/* ============================================================
   Motor de balances · homologación SRI-Super (AUD, staff)
   Ingesta multiarchivo → homologa contra el plan → tablas ESF/ERI
   con Super Cías/SRI editables, huérfanas resaltadas y cuadre por
   período (reportado, nunca forzado). Reutiliza el endpoint
   /api/v1/aud/motor-balances/{homologar,recalcular}.
   ============================================================ */

const money = (n) =>
  (Number(n) || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function MotorBalancesTool() {
  const [files, setFiles] = useState([]);
  const [data, setData] = useState(null); // { esf, eri, errores }
  const [tab, setTab] = useState("esf");
  const [busy, setBusy] = useState(false);
  const [recalc, setRecalc] = useState(false);
  const [err, setErr] = useState(null);
  const [filtro, setFiltro] = useState("");
  const inputRef = useRef(null);
  const timer = useRef(null);
  const dataRef = useRef(null);
  dataRef.current = data;

  const estado = data ? data[tab] : null;

  function elegirArchivos(e) {
    const nuevos = Array.from(e.target.files || []);
    setFiles((prev) => {
      const map = new Map(prev.map((f) => [f.name + f.size, f]));
      nuevos.forEach((f) => map.set(f.name + f.size, f));
      return Array.from(map.values());
    });
    e.target.value = "";
  }

  async function homologar() {
    if (!files.length) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await motorBalancesHomologar(files);
      setData(res);
      setTab(res.esf?.periodos?.length ? "esf" : "eri");
    } catch (e) {
      setErr(e.message || "No se pudo homologar.");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setFiles([]);
    setData(null);
    setErr(null);
    setFiltro("");
  }

  function editarCodigo(idxReal, campo, valor) {
    setData((prev) => {
      const copia = structuredClone(prev);
      copia[tab].filas[idxReal][campo] = valor;
      return copia;
    });
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      const d = dataRef.current;
      if (!d) return;
      setRecalc(true);
      try {
        const res = await motorBalancesRecalcular(d.esf, d.eri);
        setData((prev) => ({
          ...prev,
          esf: { ...prev.esf, cuadre: res.esf.cuadre, huerfanas: res.esf.huerfanas },
          eri: { ...prev.eri, huerfanas: res.eri.huerfanas },
        }));
      } catch (e) {
        setErr(e.message || "No se pudo recalcular.");
      } finally {
        setRecalc(false);
      }
    }, 700);
  }

  const huerfanasSet = useMemo(
    () => new Set(estado?.huerfanas || []),
    [estado]
  );

  const filas = useMemo(() => {
    if (!estado) return [];
    const conIdx = estado.filas.map((f, i) => [f, i]);
    if (!filtro.trim()) return conIdx;
    const q = filtro.trim().toLowerCase();
    return conIdx.filter(([f]) =>
      `${f.cuenta} ${f.nombre} ${f.super_cias} ${f.sri}`.toLowerCase().includes(q)
    );
  }, [estado, filtro]);

  return (
    <div className="mb-tool">
      <div className="mb-head">
        <div>
          <span className="mb-code">MOTOR</span>
          <span className="mb-title">Motor de balances · homologación SRI-Super</span>
        </div>
        {data && (
          <span className="mb-meta">
            {(data.esf?.periodos?.length || 0) + (data.eri?.periodos?.length || 0)} columnas de período
          </span>
        )}
      </div>

      {/* Ingesta */}
      <div className="mb-bar">
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls,.xlsm"
          multiple
          style={{ display: "none" }}
          onChange={elegirArchivos}
        />
        <button className="mb-chip" onClick={() => inputRef.current?.click()} disabled={busy}>
          📂 Subir balances / resultados / mapeado
        </button>
        <button className="mb-chip accent" onClick={homologar} disabled={!files.length || busy}>
          {busy ? "⏳ Homologando…" : "▶ Homologar"}
        </button>
        {data && (
          <button className="mb-chip danger" onClick={reset}>🔄 Nuevo</button>
        )}
        <span className="mb-hint">{files.length} archivo(s) seleccionado(s)</span>
      </div>

      {files.length > 0 && (
        <div className="mb-files">
          {files.map((f) => (
            <span key={f.name + f.size} className="mb-file">📄 {f.name}</span>
          ))}
        </div>
      )}

      {err && <div className="mb-error">{err}</div>}
      {data?.errores?.length > 0 && (
        <div className="mb-warn">
          ⚠ Archivos no procesados:{" "}
          {data.errores.map((e) => `${e.archivo}`).join(", ")}
        </div>
      )}

      {data && (
        <>
          {/* Tabs ESF / ERI */}
          <div className="mb-tabs">
            <button className={`mb-tab ${tab === "esf" ? "on" : ""}`} onClick={() => setTab("esf")}>
              Balances homologados (ESF)
            </button>
            <button className={`mb-tab ${tab === "eri" ? "on" : ""}`} onClick={() => setTab("eri")}>
              Resultados homologado (ERI)
            </button>
            <span className="mb-recalc">{recalc ? "recalculando…" : ""}</span>
          </div>

          {/* Banner de cuadre (solo ESF) */}
          {tab === "esf" && estado?.cuadre && (
            <div className="mb-cuadre">
              {estado.periodos.map((p) => {
                const c = estado.cuadre[p];
                const ok = c?.cuadra;
                return (
                  <span key={p} className={`mb-cua ${ok ? "ok" : "bad"}`}>
                    {ok ? "✓" : "⚠"} {p}: {ok ? "cuadra" : money(c?.diferencia)}
                  </span>
                );
              })}
            </div>
          )}

          <div className="mb-status">
            <span className="mb-dot" />
            {estado.filas.length} cuentas · {huerfanasSet.size} por homologar (ámbar)
          </div>

          <input
            className="mb-search"
            placeholder="Filtrar por cuenta / nombre / Super Cías / SRI…"
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
          />

          {/* Tabla editable N-períodos */}
          <div className="mb-scroll">
            <table className="mb-tbl">
              <thead>
                <tr>
                  <th className="c1">Cuenta contable (cliente)</th>
                  <th className="edit sup">Codifo Super Cías</th>
                  <th className="edit sri">Códigos SRI</th>
                  {estado.periodos.map((p) => (
                    <th key={p} className="num">{p}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filas.map(([f, i]) => {
                  const orphan = !f.super_cias;
                  return (
                    <tr key={f.cuenta + i} className={orphan ? "orphan" : ""}>
                      <td className="c1">
                        <span className="cod">{f.cuenta}</span>
                        <span className="nom">{f.nombre}</span>
                      </td>
                      <td className="edit">
                        <input
                          className="in cod"
                          value={f.super_cias || ""}
                          placeholder={orphan ? "homologar…" : ""}
                          onChange={(e) => editarCodigo(i, "super_cias", e.target.value)}
                        />
                      </td>
                      <td className="edit">
                        <input
                          className="in cod"
                          value={f.sri || ""}
                          onChange={(e) => editarCodigo(i, "sri", e.target.value)}
                        />
                      </td>
                      {estado.periodos.map((p) => (
                        <td key={p} className="num">{money(f.saldos[p])}</td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
