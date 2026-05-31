import { useEffect, useState } from "react";
import { Button, Input, Modal } from "@auditbrain/shared";
import { updateSession } from "./ictApi.js";

export default function ICTEditContribuyenteModal({ open, onClose, session, onSaved }) {
  const [ruc, setRuc] = useState(session?.ruc || "");
  const [razon, setRazon] = useState(session?.razon_social || "");
  const [adhesivo, setAdhesivo] = useState(session?.numero_adhesivo || "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (session) {
      setRuc(session.ruc || "");
      setRazon(session.razon_social || "");
      setAdhesivo(session.numero_adhesivo || "");
    }
  }, [session]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await updateSession(session.id, {
        ruc: ruc || null,
        razon_social: razon || null,
        numero_adhesivo: adhesivo || null,
      });
      onSaved();
      onClose();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Editar datos del contribuyente">
      <form onSubmit={submit}>
        <Input label="RUC" value={ruc} onChange={(e) => setRuc(e.target.value)} />
        <Input label="Razón Social" value={razon} onChange={(e) => setRazon(e.target.value)} />
        <Input label="Número de Adhesivo" value={adhesivo} onChange={(e) => setAdhesivo(e.target.value)} />
        {err && <div style={{ color: "#c0392b", marginBottom: 12 }}>{err}</div>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={busy}>{busy ? "Guardando..." : "Guardar"}</Button>
        </div>
      </form>
    </Modal>
  );
}
