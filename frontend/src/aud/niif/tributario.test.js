import { describe, expect, it } from "vitest";

import { estadoTributario, textoTributarioInicial } from "./cicloLogic";

describe("textoTributarioInicial · pre-llenado del recuadro", () => {
  it("usa lo guardado si existe", () => {
    expect(textoTributarioInicial({ taxScope: "ya escrito" }, { tributario_sugerido: { texto: "sug" } })).toBe("ya escrito");
  });
  it("cae a la base legal sugerida cuando está vacío", () => {
    expect(textoTributarioInicial({ taxScope: "" }, { tributario_sugerido: { texto: "Base legal sugerida…" } })).toBe("Base legal sugerida…");
  });
  it("vacío si no hay nada", () => {
    expect(textoTributarioInicial({}, {})).toBe("");
    expect(textoTributarioInicial(null, null)).toBe("");
  });
});

describe("estadoTributario · gate de «Confirmar base técnica»", () => {
  it("no aplica cuando la prueba no tiene tratamiento tributario", () => {
    expect(estadoTributario(false, "", false)).toEqual({ ok: true, motivo: "" });
  });
  it("bloquea si el texto está vacío", () => {
    const r = estadoTributario(true, "   ", true);
    expect(r.ok).toBe(false);
    expect(r.motivo).toMatch(/Describa el tratamiento/);
  });
  it("bloquea si quedan citas «VERIFICAR» sin resolver", () => {
    const r = estadoTributario(true, "VERIFICAR — confirmar el artículo en el SRI", true);
    expect(r.ok).toBe(false);
    expect(r.motivo).toMatch(/VERIFICAR/);
  });
  it("bloquea si no se marcó la casilla de conformidad", () => {
    const r = estadoTributario(true, "LRTI Art. 10 núm. 11: 1 % anual, tope 10 %.", false);
    expect(r.ok).toBe(false);
    expect(r.motivo).toMatch(/Revisé la base legal/);
  });
  it("habilita solo con texto, sin VERIFICAR y casilla marcada", () => {
    expect(estadoTributario(true, "LRTI Art. 10 núm. 11: 1 % anual, tope 10 %.", true)).toEqual({ ok: true, motivo: "" });
  });
});
