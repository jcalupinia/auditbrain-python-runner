import { useRef, useState } from "react";
import { Button } from "@auditbrain/shared";
import { uploadAnexoSlot, resetSlot } from "./ictApi.js";

export default function ICTUploader({ sessionId, anexoCode, slotName, onUploaded, hasFile, multi = false }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [uploadedCount, setUploadedCount] = useState(null); // solo para multi

  async function handleFile(e) {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    setBusy(true);
    try {
      const result = await uploadAnexoSlot(sessionId, anexoCode, slotName, Array.from(fileList));
      if (multi && result?.files_processed != null) {
        setUploadedCount(result.files_processed);
      }
      onUploaded();
    } catch (err) {
      alert(`Error subiendo: ${err.message}`);
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function handleReset() {
    if (!confirm("¿Eliminar este archivo? El estado del anexo se recalculará.")) return;
    setBusy(true);
    try {
      await resetSlot(sessionId, anexoCode, slotName);
      setUploadedCount(null);
      onUploaded();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  function getLabel() {
    if (busy) return multi ? "Subiendo..." : "...";
    if (hasFile) {
      if (multi && uploadedCount != null) return `${uploadedCount} mes(es) cargados — agregar más`;
      return "Reemplazar";
    }
    return multi ? "Seleccionar PDFs" : "Subir";
  }

  return (
    <div style={{ display: "flex", gap: 8 }}>
      <input
        ref={inputRef}
        type="file"
        multiple={multi}
        style={{ display: "none" }}
        onChange={handleFile}
      />
      <Button variant={hasFile ? "secondary" : "primary"} disabled={busy} onClick={() => inputRef.current?.click()}>
        {getLabel()}
      </Button>
      {hasFile && (
        <Button variant="danger" disabled={busy} onClick={handleReset}>
          ×
        </Button>
      )}
    </div>
  );
}
