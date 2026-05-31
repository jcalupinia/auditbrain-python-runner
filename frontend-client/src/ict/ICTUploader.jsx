import { useRef, useState } from "react";
import { Button } from "@auditbrain/shared";
import { uploadAnexoSlot, resetSlot } from "./ictApi.js";

export default function ICTUploader({ sessionId, anexoCode, slotName, onUploaded, hasFile }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      await uploadAnexoSlot(sessionId, anexoCode, slotName, file);
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
      onUploaded();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "flex", gap: 8 }}>
      <input ref={inputRef} type="file" style={{ display: "none" }} onChange={handleFile} />
      <Button variant={hasFile ? "secondary" : "primary"} disabled={busy} onClick={() => inputRef.current?.click()}>
        {busy ? "..." : hasFile ? "Reemplazar" : "Subir"}
      </Button>
      {hasFile && (
        <Button variant="danger" disabled={busy} onClick={handleReset}>
          ×
        </Button>
      )}
    </div>
  );
}
