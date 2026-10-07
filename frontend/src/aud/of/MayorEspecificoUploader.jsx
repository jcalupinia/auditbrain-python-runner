import { useEffect, useRef, useState } from "react";
import * as api from "../../api.js";
import { STRINGS } from "../strings.js";

/*
 * Carga de Mayores específicos: varios archivos, cada uno mapeado a SU
 * categoría (un archivo = una categoría; un archivo puede traer varias
 * cuentas, todas de esa categoría). Reemplaza al chip con select que se
 * bloqueaba tras la primera subida.
 *
 * Flujo: eliges una categoría → agregas uno o varios archivos (se suben con
 * esa categoría) → aparecen listados con su categoría → cambias la categoría
 * y agregas más. Cada archivo se puede quitar por separado.
 *
 * Props:
 *   jobId     id del job activo
 *   estado    slotsEstado.mayor_especifico: { n_archivos, nombres,
 *             archivos: [{nombre, categoria}] }
 *   disabled  job ya no editable
 *   onChanged() se llama tras subir/quitar para refrescar el estado de slots
 */
export default function MayorEspecificoUploader({ jobId, estado, disabled, onChanged }) {
  const inputRef = useRef(null);
  const [categoria, setCategoria] = useState("");
  const [categorias, setCategorias] = useState([]);
  const [loadingCat, setLoadingCat] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const archivos = estado?.archivos || [];

  useEffect(() => {
    let cancelado = false;
    setLoadingCat(true);
    api
      .listarCategoriasOF()
      .then((lista) => { if (!cancelado) setCategorias(lista || []); })
      .catch(() => { /* el catálogo vacío no debe romper el bloque */ })
      .finally(() => { if (!cancelado) setLoadingCat(false); });
    return () => { cancelado = true; };
  }, []);

  const nombreCategoria = (codigo) =>
    categorias.find((c) => c.codigo === codigo)?.nombre || codigo || "—";

  function abrirSelector() {
    if (disabled || busy) return;
    setError("");
    if (!categoria) {
      setError(STRINGS.of_esp_elige_categoria);
      return;
    }
    inputRef.current?.click();
  }

  async function handleFile(e) {
    const lista = e.target.files;
    if (!lista || lista.length === 0) return;
    setBusy(true);
    setError("");
    try {
      await api.subirSlotOF(jobId, "mayor_especifico", Array.from(lista), categoria);
      onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function quitar(nombre) {
    if (disabled || busy) return;
    setBusy(true);
    setError("");
    try {
      await api.quitarSlotOF(jobId, "mayor_especifico", nombre);
      onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        border: "1px solid var(--line)", borderRadius: 10, padding: "10px 12px",
        background: "var(--panel-2)", marginTop: 8,
      }}
    >
      <div style={{ fontSize: 12, color: "var(--accent)", marginBottom: 8, fontWeight: 600 }}>
        {STRINGS.of_esp_titulo}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
        <select
          value={categoria}
          disabled={disabled || busy}
          onChange={(e) => setCategoria(e.target.value)}
          title={STRINGS.of_esp_categoria_title}
          style={{ padding: "6px 8px", fontSize: 12, minWidth: 180 }}
        >
          <option value="">
            {loadingCat ? STRINGS.of_slot_categoria_loading : STRINGS.of_esp_categoria_placeholder}
          </option>
          {categorias.map((c) => (
            <option key={c.codigo} value={c.codigo}>{c.nombre}</option>
          ))}
        </select>

        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          multiple
          style={{ display: "none" }}
          onChange={handleFile}
        />
        <button
          type="button"
          className="pc-chip accent"
          onClick={abrirSelector}
          disabled={disabled || busy}
          title={STRINGS.of_esp_agregar_title}
        >
          {busy ? STRINGS.of_slot_uploading : STRINGS.of_esp_agregar}
        </button>
        <span style={{ fontSize: 11, color: "var(--text-soft)" }}>
          {STRINGS.of_esp_hint}
        </span>
      </div>

      {archivos.length > 0 && (
        <ul style={{ listStyle: "none", margin: "10px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
          {archivos.map((a) => (
            <li
              key={a.nombre}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                gap: 10, fontSize: 12, padding: "6px 8px",
                background: "var(--panel)", border: "1px solid var(--line-soft)", borderRadius: 8,
              }}
            >
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                📄 {a.nombre}
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                <span className={a.categoria ? "pc-chip on" : "pc-chip warn"} style={{ cursor: "default", padding: "2px 8px" }}>
                  {a.categoria ? nombreCategoria(a.categoria) : STRINGS.of_esp_sin_categoria}
                </span>
                {!disabled && (
                  <button
                    type="button"
                    className="link danger"
                    onClick={() => quitar(a.nombre)}
                    title={STRINGS.of_esp_quitar_title}
                  >×</button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      {error && <div className="err" style={{ fontSize: 11, marginTop: 8 }}>{error}</div>}
    </div>
  );
}
