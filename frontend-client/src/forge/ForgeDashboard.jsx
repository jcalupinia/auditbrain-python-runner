// Forge Console — gestiona el "cerebro" del proyecto y lo compila a las
// herramientas de IA. Portal de clientes (rol client).
import { useEffect, useState } from "react";

import PortalShell from "../shell/PortalShell.jsx";
import * as forge from "./forgeApi.js";
import "./forge.css";

const TOOL_CODE = "FORGE_CONSOLE";

export default function ForgeDashboard() {
  const [sub, setSub] = useState(null);
  const [brains, setBrains] = useState([]);
  const [selected, setSelected] = useState(null);
  const [target, setTarget] = useState("claude-code");
  const [output, setOutput] = useState(null);
  const [phase, setPhase] = useState("idle"); // idle | compiling
  const [err, setErr] = useState(null);
  const [form, setForm] = useState({ name: "", slug: "", rules: "" });

  async function reload() {
    setErr(null);
    try {
      const [s, b] = await Promise.all([forge.getSubscription(), forge.listBrains()]);
      setSub(s);
      setBrains(b);
    } catch (e) {
      setErr(e.message || "No se pudo cargar.");
    }
  }

  useEffect(() => {
    reload();
  }, []);

  async function handleCreate(e) {
    e.preventDefault();
    setErr(null);
    const rules = form.rules
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .map((l, i) => ({ id: `regla-${i + 1}`, title: `Regla ${i + 1}`, body: l }));
    try {
      const created = await forge.createBrain({
        name: form.name,
        slug: form.slug || form.name.toLowerCase().replace(/\s+/g, "-"),
        rules,
      });
      setForm({ name: "", slug: "", rules: "" });
      setSelected(created);
      await reload();
    } catch (e) {
      setErr(e.message || "No se pudo crear el cerebro.");
    }
  }

  async function handleCompile() {
    if (!selected) return;
    setPhase("compiling");
    setErr(null);
    setOutput(null);
    try {
      const res = await forge.compileBrain(selected.id, target);
      setOutput(res);
    } catch (e) {
      setErr(e.message || "No se pudo compilar.");
    } finally {
      setPhase("idle");
    }
  }

  const targets = sub?.targets || ["claude-code"];

  return (
    <PortalShell
      title="FORGE CONSOLE"
      subtitle="Un cerebro, muchos destinos · desarrollo asistido por IA"
      activeCategory="DESARROLLO"
      activeNodeCode={TOOL_CODE}
    >
      <div className="forge-wrap">
        {sub && (
          <div className="pc-chip on" title="Tu plan actual">
            Plan: {sub.plan} · destinos: {sub.targets.length} ·
            {" "}
            cerebros: {sub.max_brains == null ? "ilimitados" : sub.max_brains}
          </div>
        )}
        {err && (
          <div className="pc-panel forge-error">
            <div className="pc-panel-b">{err}</div>
          </div>
        )}

        <div className="forge-grid">
          {/* Columna: cerebros + crear */}
          <section className="pc-panel">
            <div className="pc-panel-h">
              <div className="pc-panel-t">Cerebros</div>
            </div>
            <div className="pc-panel-b">
              {brains.length === 0 && <p className="forge-muted">Aún no tienes cerebros.</p>}
              {brains.map((b) => (
                <button
                  key={b.id}
                  className={`pc-tile forge-tile ${selected?.id === b.id ? "on" : ""}`}
                  onClick={() => {
                    setSelected(b);
                    setOutput(null);
                  }}
                >
                  <strong>{b.name}</strong>
                  <span className="forge-muted">{b.slug}</span>
                </button>
              ))}

              <form className="forge-form" onSubmit={handleCreate}>
                <div className="forge-form-t">Nuevo cerebro</div>
                <input
                  placeholder="Nombre"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
                <input
                  placeholder="slug (opcional)"
                  value={form.slug}
                  onChange={(e) => setForm({ ...form, slug: e.target.value })}
                />
                <textarea
                  placeholder="Reglas (una por línea)"
                  rows={3}
                  value={form.rules}
                  onChange={(e) => setForm({ ...form, rules: e.target.value })}
                />
                <button className="pc-btn-ghost" type="submit">
                  Crear cerebro
                </button>
              </form>
            </div>
          </section>

          {/* Columna: compilar + salida */}
          <section className="pc-panel">
            <div className="pc-panel-h">
              <div className="pc-panel-t">
                {selected ? `Compilar: ${selected.name}` : "Compilar"}
              </div>
            </div>
            <div className="pc-panel-b">
              {!selected && <p className="forge-muted">Elige un cerebro de la izquierda.</p>}
              {selected && (
                <>
                  <div className="forge-compile-bar">
                    <select value={target} onChange={(e) => setTarget(e.target.value)}>
                      {targets.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                    <button
                      className="pc-btn-ghost accent"
                      onClick={handleCompile}
                      disabled={phase === "compiling"}
                    >
                      {phase === "compiling" ? "Compilando…" : "Compilar"}
                    </button>
                  </div>

                  {output && (
                    <div className="forge-output">
                      <div className="forge-muted">
                        {output.count} archivo(s) · destino {output.target}
                      </div>
                      {Object.entries(output.files).map(([path, content]) => (
                        <details key={path} className="forge-file">
                          <summary>{path}</summary>
                          <pre className="pc-code">{content}</pre>
                        </details>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </section>
        </div>
      </div>
    </PortalShell>
  );
}
