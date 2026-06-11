import { useState } from "react";
import { registrarCharla } from "../api.js";
import { DATA_PROTECTION_TEXT } from "./legal.js";

const SLUG = "charla-anexos-2026-06";

const EMPTY = {
  nombre: "",
  email: "",
  telefono_pais: "+593",
  telefono: "",
  documento: "",
  empresa: "",
};

export default function CharlaForm({ evento, onSuccess }) {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function validateClient() {
    if (form.nombre.trim().length < 3) return "Ingresa tu nombre y apellido.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) return "Ingresa un email válido.";
    const tel = form.telefono.replace(/\D/g, "");
    if (tel.length < 7) return "Ingresa un número de celular válido.";
    const doc = form.documento.replace(/\D/g, "");
    if (doc.length !== 10 && doc.length !== 13) return "La cédula debe tener 10 dígitos o el RUC 13.";
    if (form.empresa.trim().length < 1) return "Ingresa el nombre de tu empresa.";
    return "";
  }

  async function submit(e) {
    e.preventDefault();
    const v = validateClient();
    if (v) { setErr(v); return; }
    setErr("");
    setBusy(true);
    try {
      const res = await registrarCharla(SLUG, {
        nombre: form.nombre.trim(),
        email: form.email.trim(),
        telefono: form.telefono.trim(),
        telefono_pais: form.telefono_pais.trim(),
        documento: form.documento.trim(),
        empresa: form.empresa.trim(),
      });
      onSuccess(res);
    } catch (e2) {
      setErr(e2.message || "No se pudo completar la inscripción.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="charla-card">
      <h3>Reserva tu cupo gratis</h3>
      <p className="lead">Cupos limitados · {evento.modalidad}</p>
      {err && <div className="charla-err">{err}</div>}
      <form onSubmit={submit}>
        <div className="charla-field">
          <label>Nombre y apellido</label>
          <input value={form.nombre} onChange={(e) => set("nombre", e.target.value)} required />
        </div>
        <div className="charla-field">
          <label>Email</label>
          <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required />
        </div>
        <div className="charla-field">
          <label>Celular (WhatsApp)</label>
          <div className="charla-phone">
            <input value={form.telefono_pais} onChange={(e) => set("telefono_pais", e.target.value)} aria-label="Código de país" />
            <input value={form.telefono} onChange={(e) => set("telefono", e.target.value)} placeholder="0987654321" required />
          </div>
        </div>
        <div className="charla-field">
          <label>Cédula o RUC</label>
          <input value={form.documento} onChange={(e) => set("documento", e.target.value)} required />
        </div>
        <div className="charla-field">
          <label>Empresa</label>
          <input value={form.empresa} onChange={(e) => set("empresa", e.target.value)} required />
        </div>
        <button className="charla-btn" disabled={busy}>
          {busy ? "Enviando…" : "¡Registrarme gratis!"}
        </button>
        <p className="charla-legal">{DATA_PROTECTION_TEXT}</p>
      </form>
    </div>
  );
}
