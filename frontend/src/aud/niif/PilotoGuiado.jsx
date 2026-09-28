import { useEffect, useMemo, useState } from "react";

import {
  pilotoPruebas,
  pilotoRequisitos,
  pilotoPlantilla,
  pilotoEjecutar,
  pilotoDescargarPapel,
} from "../../api.js";
import {
  agruparPorRubro,
  filtrarPruebas,
  filaVacia,
  filasDesdeMolde,
  gridInicial,
  cuerpoEjecucion,
  faltantesParaEjecutar,
  FORMATOS_PAPEL,
} from "./pilotoLogic.js";
import "./fichaNiif.css";

// Agente guía «NIIF Piloto»: elige una prueba, pide los datos que esa prueba
// necesita y arma el papel en Excel/HTML/Word/PowerPoint/PDF. Un solo flujo para
// TODAS las pruebas (consume /aud/niif/piloto). El cálculo lo hace el backend.
export default function PilotoGuiado({ cliente }) {
  const [pruebas, setPruebas] = useState(null);
  const [error, setError] = useState("");
  const [filtro, setFiltro] = useState("");

  const [sel, setSel] = useState(null); // id de la prueba
  const [req, setReq] = useState(null); // requisitos de la prueba
  const [corte, setCorte] = useState("");
  const [encargo, setEncargo] = useState({ client: "", ruc: "" });
  const [parametros, setParametros] = useState({});
  const [grid, setGrid] = useState({});
  const [cargandoReq, setCargandoReq] = useState(false);

  const [ejecutando, setEjecutando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [descargando, setDescargando] = useState("");

  useEffect(() => {
    pilotoPruebas()
      .then((d) => setPruebas(d.pruebas || []))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (cliente?.name) setEncargo((e) => ({ ...e, client: e.client || cliente.name }));
  }, [cliente]);

  const grupos = useMemo(
    () => agruparPorRubro(filtrarPruebas(pruebas || [], filtro)),
    [pruebas, filtro]
  );

  async function elegir(prueba) {
    setError("");
    setResultado(null);
    setSel(prueba.id);
    setCargandoReq(true);
    try {
      const r = await pilotoRequisitos(prueba.id);
      setReq(r);
      setCorte(r.corte_ejemplo || "");
      setParametros({ ...(r.parametros_por_defecto || {}) });
      setGrid(gridInicial(r));
    } catch (e) {
      setError(e.message);
      setSel(null);
    } finally {
      setCargandoReq(false);
    }
  }

  async function cargarEjemplo() {
    if (!sel) return;
    try {
      const molde = await pilotoPlantilla(sel);
      setGrid(filasDesdeMolde(req, molde));
      if (molde.parametros) setParametros((p) => ({ ...p, ...molde.parametros }));
      if (molde.corte) setCorte(molde.corte);
    } catch (e) {
      setError(e.message);
    }
  }

  function setCelda(ds, i, key, valor) {
    setGrid((g) => {
      const filas = g[ds].slice();
      filas[i] = { ...filas[i], [key]: valor };
      return { ...g, [ds]: filas };
    });
  }
  function agregarFila(ds, dsSpec) {
    setGrid((g) => ({ ...g, [ds]: [...g[ds], filaVacia(dsSpec)] }));
  }
  function quitarFila(ds, i, dsSpec) {
    setGrid((g) => {
      const filas = g[ds].filter((_, k) => k !== i);
      return { ...g, [ds]: filas.length ? filas : [filaVacia(dsSpec)] };
    });
  }

  async function ejecutar() {
    setError("");
    const cuerpo = cuerpoEjecucion({ corte, grid, parametros, encargo });
    const faltan = faltantesParaEjecutar(cuerpo);
    if (faltan.length) {
      setError(`Falta ${faltan.join(" y ")}.`);
      return;
    }
    setEjecutando(true);
    setResultado(null);
    try {
      const r = await pilotoEjecutar(sel, cuerpo);
      setResultado(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setEjecutando(false);
    }
  }

  async function descargar(fmt) {
    const cuerpo = cuerpoEjecucion({ corte, grid, parametros, encargo });
    setDescargando(fmt);
    setError("");
    try {
      await pilotoDescargarPapel(sel, cuerpo, fmt, `${sel}.${fmt === "zip" ? "zip" : fmt}`);
    } catch (e) {
      setError(e.message);
    } finally {
      setDescargando("");
    }
  }

  if (error && !pruebas) return <p className="nf-error">{error}</p>;
  if (!pruebas) return <p className="muted">Cargando pruebas…</p>;

  // Paso 1 — elegir la prueba.
  if (!sel) {
    return (
      <section className="nf-piloto">
        <p className="nf-eyebrow">PILOTO GUIADO · UN SOLO AGENTE PARA TODAS LAS PRUEBAS</p>
        <p className="muted">
          Elegí una prueba: te pediré exactamente los datos que necesita y armaré el papel de
          trabajo (Excel con fórmulas, HTML, Word, PowerPoint y PDF). El cálculo es determinista y
          verificable; la interpretación queda como borrador para el auditor.
        </p>
        <input
          type="search"
          className="nf-piloto-buscar"
          placeholder="Buscar prueba (arrendamientos, cartera, inventarios…)"
          value={filtro}
          onChange={(e) => setFiltro(e.target.value)}
        />
        {error && <p className="nf-error">{error}</p>}
        {grupos.map((g) => (
          <div key={g.rubro} className="nf-piloto-grupo">
            <h4>{g.rubro}</h4>
            <div className="nf-piloto-cards">
              {g.pruebas.map((p) => (
                <button key={p.id} type="button" className="nf-piloto-card" onClick={() => elegir(p)}>
                  <strong>{p.nombre}</strong>
                  <span className="muted">{(p.marcos || []).join(" · ")}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </section>
    );
  }

  const prueba = pruebas.find((p) => p.id === sel);

  // Pasos 2–3 — requisitos + datos + ejecutar.
  return (
    <section className="nf-piloto">
      <div className="nf-piloto-barra">
        <button type="button" className="btn sm" onClick={() => { setSel(null); setReq(null); setResultado(null); }}>
          ← Elegir otra prueba
        </button>
        <h3>{prueba?.nombre || sel}</h3>
      </div>

      {cargandoReq && <p className="muted">Cargando requisitos…</p>}
      {error && <p className="nf-error">{error}</p>}

      {req && (
        <>
          <p className="muted">{req.resumen}</p>

          <div className="nf-piloto-encargo">
            <label>
              Fecha de corte
              <input type="date" value={corte} onChange={(e) => setCorte(e.target.value)} />
            </label>
            <label>
              Cliente
              <input value={encargo.client} onChange={(e) => setEncargo({ ...encargo, client: e.target.value })} />
            </label>
            <label>
              RUC
              <input value={encargo.ruc} onChange={(e) => setEncargo({ ...encargo, ruc: e.target.value })} />
            </label>
            <button type="button" className="btn sm" onClick={cargarEjemplo} title="Precarga los datos del ejemplo del manifiesto">
              Cargar datos de ejemplo
            </button>
          </div>

          {req.requerimientos_al_cliente?.length > 0 && (
            <details className="nf-piloto-reqs">
              <summary>Requerimientos al cliente (NIA 500)</summary>
              <ul>
                {req.requerimientos_al_cliente.map((r) => (
                  <li key={r.id}>
                    <strong>{r.id}</strong> {r.documento} {!r.requerido && <em className="muted">(opcional)</em>}
                  </li>
                ))}
              </ul>
            </details>
          )}

          {req.datasets.map((ds) => (
            <div key={ds.dataset} className="nf-piloto-ds">
              <h4>
                Anexo «{ds.dataset}»{ds.es_principal && <span className="nf-badge">principal</span>}
              </h4>
              <div className="nf-piloto-tabla-wrap">
                <table className="nf-estudio-tabla nf-piloto-tabla">
                  <thead>
                    <tr>
                      {ds.campos.map((c) => (
                        <th key={c.key} title={c.tipo}>
                          {c.label}
                          {!c.requerido && <span className="muted"> ·opc</span>}
                        </th>
                      ))}
                      <th aria-label="acciones" />
                    </tr>
                  </thead>
                  <tbody>
                    {(grid[ds.dataset] || []).map((fila, i) => (
                      <tr key={i}>
                        {ds.campos.map((c) => (
                          <td key={c.key}>
                            <input
                              value={fila[c.key] ?? ""}
                              placeholder={c.ejemplo != null ? String(c.ejemplo) : ""}
                              onChange={(e) => setCelda(ds.dataset, i, c.key, e.target.value)}
                            />
                          </td>
                        ))}
                        <td>
                          <button type="button" className="nf-del" title="Quitar fila" onClick={() => quitarFila(ds.dataset, i, ds)}>
                            ✕
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button type="button" className="btn sm" onClick={() => agregarFila(ds.dataset, ds)}>
                + Agregar fila
              </button>
            </div>
          ))}

          {Object.keys(parametros).length > 0 && (
            <details className="nf-piloto-params">
              <summary>Parámetros del auditor (con valor por defecto)</summary>
              <div className="nf-piloto-params-grid">
                {Object.entries(parametros).map(([k, v]) => (
                  <label key={k}>
                    {k}
                    <input
                      value={v ?? ""}
                      onChange={(e) => setParametros({ ...parametros, [k]: e.target.value })}
                    />
                  </label>
                ))}
              </div>
            </details>
          )}

          <div className="nf-estudio-botones">
            <button type="button" className="btn" onClick={ejecutar} disabled={ejecutando}>
              {ejecutando ? "Ejecutando…" : "Ejecutar prueba"}
            </button>
          </div>
        </>
      )}

      {resultado && (
        <div className="nf-piloto-resultado">
          <h4>Resultado</h4>
          <p>
            <strong>{resultado.resultado?.etiqueta_principal}:</strong>{" "}
            {resultado.resultado?.valor_principal ?? "—"} · Problemas detectados:{" "}
            {resultado.resultado?.n_problemas ?? 0}
          </p>
          <p className="muted">
            Excel: {resultado.verificacion_excel?.reabre ? "reabre sin reparaciones" : "no verificado"} ·{" "}
            {resultado.verificacion_excel?.n_hojas ?? 0} hojas ·{" "}
            {(resultado.verificacion_excel?.celdas_texto_riesgosas?.length ?? 0)} celdas de texto riesgosas
          </p>
          {resultado.resultado?.n_problemas > 0 && (
            <details className="nf-piloto-problemas">
              <summary>Ver problemas ({resultado.resultado.n_problemas})</summary>
              <ul>
                {(resultado.resultado.problemas || []).slice(0, 30).map((pb, i) => (
                  <li key={i}>{pb.detail || pb.message || pb.codigo || JSON.stringify(pb)}</li>
                ))}
              </ul>
            </details>
          )}
          <div className="nf-em-descargas">
            <span className="muted">Descargar papel:</span>
            {FORMATOS_PAPEL.map((f) => (
              <button
                key={f.ext}
                type="button"
                className="btn sm"
                disabled={!!descargando}
                onClick={() => descargar(f.ext)}
              >
                {descargando === f.ext ? "…" : f.etiqueta}
              </button>
            ))}
          </div>
          <p className="muted nf-piloto-disclaimer">
            Análisis y papel generados por el sistema. Deben ser validados por el auditor responsable
            antes de cualquier decisión.
          </p>
        </div>
      )}
    </section>
  );
}
