import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@auditbrain/shared";
import { getActiveSession, deleteSession, downloadExcel } from "./ictApi.js";
import ICTAnexoCard from "./ICTAnexoCard.jsx";
import ICTEditContribuyenteModal from "./ICTEditContribuyenteModal.jsx";
import ICTLanding from "./ICTLanding.jsx";

const ANEXOS_INFO = [
  {
    code: "INDICE",
    name: "ÍNDICE",
    desc: "Identificación + Aplica SI/NO por anexo",
    autoFill: true,
  },
  {
    code: "A1",
    name: "A1 · Mapeo de la Declaración",
    desc: "Cruce casilleros F-101 con balance",
    slots: [
      { key: "f101",    label: "Formulario 101 (PDF)",               required: true  },
      { key: "balance", label: "Balance de Comprobación (Excel)",     required: true  },
    ],
  },
  {
    code: "A2",
    name: "A2 · Ingresos",
    desc: "Ordinarios + IVA vs Facturación + Conciliación",
    slots: [
      { key: "f104", label: "Formularios 104 (selecciona los 12 meses de una vez)", required: true, multi: true },
      { key: "facturacion", label: "Reporte Facturación SRI (Excel)",              required: true },
    ],
  },
  {
    code: "A3",
    name: "A3 · Costos y Gastos (límites)",
    desc: "9 bloques de deducibilidad",
    slots: [
      { key: "f101", label: "Formulario 101 (reutilizable)", required: true },
    ],
  },
  {
    code: "A4",
    name: "A4 · Conciliación Ingresos",
    desc: "Exentos / no objeto / RIMPE",
    slots: [
      { key: "f101",         label: "Formulario 101",                          required: true  },
      { key: "mayor_exentos", label: "Libro Mayor cuentas exentas (Excel)",    required: false },
    ],
  },
  {
    code: "A5",
    name: "A5 · Conciliación Costos y Gastos",
    desc: "5 cuadros + prorrateo",
    slots: [
      { key: "f101",               label: "Formulario 101",                          required: true  },
      { key: "mayor_no_deducibles", label: "Libro Mayor no deducibles (Excel)",      required: false },
    ],
  },
  {
    code: "A6",
    name: "A6 · Beneficios Tributarios",
    desc: "Deducciones + contratos + exoneraciones",
    slots: [
      { key: "f101", label: "Formulario 101", required: true },
    ],
  },
  {
    code: "A7",
    name: "A7 · Crédito Tributario",
    desc: "IR multi-año + ISD",
    slots: [
      { key: "f101", label: "Formulario 101", required: true },
    ],
  },
  {
    code: "A8",
    name: "A8 · Comercio Exterior",
    desc: "Pagos al exterior (CDI / sin CDI / reembolsos)",
    slots: [
      { key: "ats", label: "ATS XML (SRI)", required: true },
    ],
  },
  {
    code: "A9",
    name: "A9 · Inventarios",
    desc: "9 casilleros + Kardex",
    slots: [
      { key: "f101",  label: "Formulario 101",              required: true  },
      { key: "kardex", label: "Kardex (Excel) — opcional",  required: false },
    ],
  },
];

export default function ICTDashboard() {
  const nav = useNavigate();
  const [session, setSession] = useState(undefined); // undefined = cargando
  const [editOpen, setEditOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const s = await getActiveSession();
      setSession(s);
    } catch {
      setSession(null);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  if (session === undefined) {
    return <div style={{ padding: 40, textAlign: "center" }}>Cargando...</div>;
  }
  if (session === null) {
    return <ICTLanding />;
  }

  const readyCount = (session.anexos || []).filter((a) => a.status === "ready").length;

  async function handleDownload() {
    setDownloading(true);
    try {
      await downloadExcel(session.id);
    } catch (e) {
      alert(`Error descargando: ${e.message}`);
    } finally {
      setDownloading(false);
    }
  }

  async function handleClose() {
    if (!confirm("¿Cerrar este proyecto ICT? Podrás crear uno nuevo, pero no recuperar este.")) return;
    await deleteSession(session.id);
    setSession(null);
  }

  return (
    <div>
      <header style={{
        background: "#0a2540", color: "#fff", padding: "16px 24px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div>
          <strong>ICT 2025</strong>
          <span style={{ marginLeft: 12, opacity: 0.7, fontSize: 13 }}>
            · {session.razon_social} (RUC {session.ruc})
          </span>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span style={{ fontSize: 13, opacity: 0.8 }}>Progreso: {readyCount}/10 anexos</span>
          <Button variant="secondary" onClick={() => setEditOpen(true)}>Editar datos</Button>
          <Button onClick={handleDownload} disabled={downloading}>
            {downloading ? "Generando..." : "Descargar Excel"}
          </Button>
          <button
            onClick={handleClose}
            style={{
              background: "transparent", color: "#fff", border: "1px solid #fff",
              padding: "6px 14px", borderRadius: 6, cursor: "pointer",
            }}
          >
            Cerrar proyecto
          </button>
        </div>
      </header>

      <main style={{ maxWidth: 1100, margin: "30px auto", padding: 20 }}>
        <h2>Anexos del Informe de Cumplimiento Tributario</h2>
        <div style={{ display: "grid", gap: 16 }}>
          {ANEXOS_INFO.map((info) => {
            const anexo = (session.anexos || []).find((a) => a.anexo_code === info.code);
            return (
              <ICTAnexoCard
                key={info.code}
                info={info}
                anexo={anexo || { anexo_code: info.code, status: "empty", warnings: [], uploaded_files: {} }}
                sessionId={session.id}
                onChanged={refresh}
              />
            );
          })}
        </div>
      </main>

      <ICTEditContribuyenteModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        session={session}
        onSaved={refresh}
      />
    </div>
  );
}
