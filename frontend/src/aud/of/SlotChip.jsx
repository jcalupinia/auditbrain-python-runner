import { useEffect, useRef, useState } from "react";
import * as api from "../../api.js";
import { STRINGS } from "../strings.js";

/*
 * Chip de documento para un slot del workspace de Obligaciones Fiscales.
 *
 * - Sin archivos: "Etiqueta" (pc-chip, o pc-chip warn si es requerido).
 * - Con archivos: "✓ Etiqueta (n)" (pc-chip on) + una "×" que borra el slot.
 * - mayor_especifico exige elegir la categoría (select poblado desde
 *   listarCategoriasOF) ANTES de poder subir: el backend responde 400
 *   si falta.
 *
 * Props:
 *   slot     { key, label, accept, multiple, required }
 *   jobId    id del job activo
 *   estado   { n_archivos, nombres } — estado actual del slot (lo trae el
 *            padre desde estadoSlotsOF; este componente no hace polling)
 *   disabled deshabilita el chip entero (ej. job ya no editable)
 *   onChanged() se llama tras subir o quitar archivos, para que el padre
 *            refresque el estado de slots
 */
export default function SlotChip({ slot, jobId, estado, disabled, onChanged }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [categoria, setCategoria] = useState("");
  const [categorias, setCategorias] = useState([]);
  const [loadingCategorias, setLoadingCategorias] = useState(false);

  const esMayorEspecifico = slot.key === "mayor_especifico";
  const nArchivos = estado?.n_archivos || 0;
  const tieneArchivos = nArchivos > 0;

  useEffect(() => {
    if (!esMayorEspecifico) return;
    let cancelado = false;
    setLoadingCategorias(true);
    api
      .listarCategoriasOF()
      .then((lista) => {
        if (!cancelado) setCategorias(lista || []);
      })
      .catch(() => {
        /* la falla del catálogo no debe romper el chip: el select queda vacío */
      })
      .finally(() => {
        if (!cancelado) setLoadingCategorias(false);
      });
    return () => {
      cancelado = true;
    };
  }, [esMayorEspecifico]);

  function abrirSelectorArchivos() {
    if (disabled || busy) return;
    setError("");
    if (esMayorEspecifico && !categoria) {
      setError(STRINGS.of_slot_categoria_hint);
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
      await api.subirSlotOF(
        jobId,
        slot.key,
        Array.from(lista),
        esMayorEspecifico ? categoria : undefined
      );
      onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function handleQuitar(e) {
    e.stopPropagation();
    if (disabled || busy) return;
    if (!window.confirm(STRINGS.of_slot_remove_confirm)) return;
    setBusy(true);
    setError("");
    try {
      await api.quitarSlotOF(jobId, slot.key);
      onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  let cls = "pc-chip";
  if (tieneArchivos) cls = "pc-chip on";
  else if (slot.required) cls = "pc-chip warn";

  const texto = busy
    ? STRINGS.of_slot_uploading
    : tieneArchivos
      ? `✓ ${slot.label} (${nArchivos})`
      : slot.label;

  // El chip muestra la etiqueta corta; el tooltip lleva la descripción
  // completa (o los nombres de archivo cuando ya hay algo subido).
  const descripcion = slot.descripcion || slot.label;
  const title = tieneArchivos
    ? (estado.nombres || []).join(", ")
    : esMayorEspecifico
      ? `${descripcion} · ${STRINGS.of_slot_categoria_hint}`
      : descripcion;

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      {esMayorEspecifico && (
        <select
          value={categoria}
          disabled={disabled || busy || tieneArchivos}
          onChange={(e) => setCategoria(e.target.value)}
          title={STRINGS.of_mayor_especifico_categoria}
          style={{ width: "auto", padding: "6px 8px", fontSize: 12 }}
        >
          <option value="">
            {loadingCategorias
              ? STRINGS.of_slot_categoria_loading
              : STRINGS.of_slot_categoria_placeholder}
          </option>
          {categorias.map((c) => (
            <option key={c.codigo} value={c.codigo}>
              {c.nombre}
            </option>
          ))}
        </select>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={slot.accept}
        multiple={slot.multiple}
        style={{ display: "none" }}
        onChange={handleFile}
      />

      <button
        type="button"
        className={cls}
        onClick={abrirSelectorArchivos}
        disabled={disabled || busy}
        title={title}
      >
        <span>{texto}</span>
        {tieneArchivos && (
          <span
            role="button"
            onClick={handleQuitar}
            title={STRINGS.of_slot_remove_title}
            style={{
              marginLeft: 4, padding: "0 4px",
              borderLeft: "1px solid rgba(0,0,0,0.2)",
              fontSize: 11, fontWeight: 700,
            }}
          >
            ×
          </span>
        )}
      </button>

      {error && (
        <span className="err" style={{ fontSize: 11, marginTop: 0 }}>
          {error}
        </span>
      )}
    </span>
  );
}
