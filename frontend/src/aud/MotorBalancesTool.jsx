import { useMemo, useRef, useState } from "react";
import {
  motorBalancesHomologar,
  motorBalancesRecalcular,
  motorBalancesPlan,
  motorBalancesEstados,
} from "../api.js";
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

// Roadmap de secciones que produce la herramienta (visible siempre, como el
// portal Flujo de Efectivo). `view` = tabs de workspace; `sup` = estados
// Superintendencia; `action` = botón que genera el traslado.
const SECCIONES = [
  { id: "esf", n: "1", name: "Balances homologados", desc: "ESF · multiarchivo + cuadre por período", tipo: "view" },
  { id: "eri", n: "2", name: "Resultados homologado", desc: "ERI · cascada de resultados", tipo: "view" },
  { id: "traslado", n: "3", name: "Traslado Superintendencia", desc: "Genera el formato oficial (N períodos)", tipo: "action" },
  { id: "sf_sup", n: "4", name: "Situación Financiera", desc: "Formato Superintendencia · un período por columna", tipo: "sup" },
  { id: "ri_sup", n: "5", name: "Resultado Integral", desc: "Formato Superintendencia · un período por columna", tipo: "sup" },
];

export default function MotorBalancesTool() {
  const [files, setFiles] = useState([]);
  const [data, setData] = useState(null); // { esf, eri, errores }
  const [plan, setPlan] = useState(null); // { super_a_sri, sri_a_super, nombre_super, nombre_sri }
  const [estados, setEstados] = useState(null); // { esf:{periodos,lineas}, eri:{...} }
  const [genBusy, setGenBusy] = useState(false);
  const [tab, setTab] = useState("esf"); // esf | eri | sf_sup | ri_sup
  const [busy, setBusy] = useState(false);
  const [recalc, setRecalc] = useState(false);
  const [err, setErr] = useState(null);
  const [filtro, setFiltro] = useState("");
  const inputRef = useRef(null);
  const timer = useRef(null);
  const dataRef = useRef(null);
  dataRef.current = data;

  const esWorkspace = tab === "esf" || tab === "eri";
  const estado = data && esWorkspace ? data[tab] : null;

  const superOpts = useMemo(
    () => (plan ? Object.entries(plan.nombre_super).map(([codigo, nombre]) => ({ codigo, nombre })) : []),
    [plan]
  );
  const sriOpts = useMemo(
    () => (plan ? Object.entries(plan.nombre_sri).map(([codigo, nombre]) => ({ codigo, nombre })) : []),
    [plan]
  );

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
      setEstados(null);
      setTab(res.esf?.periodos?.length ? "esf" : "eri");
      motorBalancesPlan().then(setPlan).catch(() => {});
    } catch (e) {
      setErr(e.message || "No se pudo homologar.");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setFiles([]);
    setData(null);
    setEstados(null);
    setErr(null);
    setFiltro("");
    setTab("esf");
  }

  function generarSuperintendencia() {
    if (!data) return;
    setGenBusy(true);
    setErr(null);
    motorBalancesEstados(data.esf, data.eri)
      .then((e) => {
        setEstados(e);
        setTab("sf_sup");
      })
      .catch((e) => setErr(e.message || "No se pudo generar el formato Superintendencia."))
      .finally(() => setGenBusy(false));
  }

  // --- Estado del roadmap de secciones ---
  function estadoSeccion(s) {
    if (s.tipo === "view") return data ? "listo" : "pend";
    if (s.tipo === "sup") return estados ? "listo" : "pend";
    if (genBusy) return "busy";
    if (estados) return "listo";
    if (data) return "accion";
    return "pend";
  }
  function labelSeccion(s) {
    const e = estadoSeccion(s);
    return e === "busy" ? "GENERANDO…" : e === "listo" ? "LISTO" : e === "accion" ? "GENERAR ▶" : "PENDIENTE";
  }
  function seccionDisabled(s) {
    if (s.tipo === "view") return !data;
    if (s.tipo === "sup") return !estados;
    return !data || genBusy;
  }
  function clickSeccion(s) {
    if (seccionDisabled(s)) return;
    if (s.tipo === "action") return generarSuperintendencia();
    setTab(s.id);
  }

  function editarCodigo(idxReal, campo, valor) {
    setData((prev) => {
      const copia = structuredClone(prev);
      const fila = copia[tab].filas[idxReal];
      fila[campo] = valor;
      // Enlace bidireccional Super↔SRI cuando el plan tiene mapeo 1:1.
      if (campo === "super_cias" && plan?.super_a_sri?.[valor]?.length === 1) {
        fila.sri = plan.super_a_sri[valor][0];
      } else if (campo === "sri" && plan?.sri_a_super?.[valor]?.length === 1) {
        fila.super_cias = plan.sri_a_super[valor][0];
      }
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
      {plan && (
        <>
          <datalist id="mb-plan-super">
            {superOpts.map((o) => (
              <option key={o.codigo} value={o.codigo}>{o.nombre}</option>
            ))}
          </datalist>
          <datalist id="mb-plan-sri">
            {sriOpts.map((o) => (
              <option key={o.codigo} value={o.codigo}>{o.nombre}</option>
            ))}
          </datalist>
        </>
      )}
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

      {/* Roadmap de secciones — siempre visible (línea gráfica del Flujo de Efectivo) */}
      <div className="mb-road-h">
        <span>{data ? "Secciones · elegí una para verla:" : "Secciones que se generarán:"}</span>
        <span className="mb-recalc">{recalc ? "recalculando…" : ""}</span>
      </div>
      <div className="mb-tiles">
        {SECCIONES.map((s) => {
          const est = estadoSeccion(s);
          const done = est === "listo" || est === "accion";
          const active =
            (s.tipo !== "action" && tab === s.id && data) ||
            (s.tipo === "action" && genBusy);
          return (
            <button
              key={s.id}
              className={`mb-tile${done ? " done" : ""}${active ? " on" : ""}`}
              onClick={() => clickSeccion(s)}
              disabled={seccionDisabled(s)}
            >
              <span className={`mb-tile-n${est === "pend" ? " dim" : ""}`}>{s.n}</span>
              <span className="mb-tile-txt">
                <span className="mb-tile-t">{s.name}</span>
                <span className="mb-tile-d">{s.desc}</span>
              </span>
              <span className="mb-tile-st">{labelSeccion(s)}</span>
            </button>
          );
        })}
      </div>

      {data && (
        <>
          {/* ---- Workspace editable (secciones 1,2): solo tabs esf/eri ---- */}
          {esWorkspace && estado && (
            <>
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
                      const grupo = f.es_hoja === false;
                      const orphan = !grupo && !f.super_cias;
                      return (
                        <tr key={f.cuenta + i} className={grupo ? "grupo" : orphan ? "orphan" : ""}>
                          <td className="c1">
                            <span className="cod">{f.cuenta}</span>
                            <span className="nom">{f.nombre}</span>
                          </td>
                          {grupo ? (
                            <td className="edit grp" colSpan={2}>subtotal</td>
                          ) : (
                            <>
                              <td className="edit">
                                <input
                                  className="in cod"
                                  value={f.super_cias || ""}
                                  list="mb-plan-super"
                                  placeholder={orphan ? "homologar…" : ""}
                                  onChange={(e) => editarCodigo(i, "super_cias", e.target.value)}
                                />
                                <span className="mb-nom">{plan?.nombre_super?.[f.super_cias] || ""}</span>
                              </td>
                              <td className="edit">
                                <input
                                  className="in cod"
                                  value={f.sri || ""}
                                  list="mb-plan-sri"
                                  onChange={(e) => editarCodigo(i, "sri", e.target.value)}
                                />
                                <span className="mb-nom">{plan?.nombre_sri?.[f.sri] || ""}</span>
                              </td>
                            </>
                          )}
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

          {/* ---- Vistas Superintendencia (secciones 4,5): tabs sf_sup/ri_sup ---- */}
          {!esWorkspace && (
            estados ? (
              (() => {
                const est = tab === "sf_sup" ? estados.esf : estados.eri;
                if (!est) return <div className="mb-warn">Sin datos para esta vista.</div>;
                return (
                  <div className="mb-scroll">
                    <table className="mb-tbl">
                      <thead>
                        <tr>
                          <th className="c1">Código Super Cías</th>
                          <th>Cuenta</th>
                          {(est.periodos || []).map((p) => (
                            <th key={p} className="num">{p}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(est.lineas || []).map((linea, i) => {
                          const grp = linea.es_hoja === false;
                          return (
                            <tr key={linea.codigo + i} className={grp ? "mb-grp-row" : ""}>
                              <td className="c1">
                                <span className="cod">{linea.codigo}</span>
                              </td>
                              <td>{linea.etiqueta}</td>
                              {(linea.valores || []).map((v, j) => (
                                <td key={j} className="num">{money(v)}</td>
                              ))}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                );
              })()
            ) : (
              <div className="mb-status">
                <span className="mb-dot" />
                Pulsá ▶ Generar formato Superintendencia
              </div>
            )
          )}
        </>
      )}
    </div>
  );
}
