import { describe, expect, it } from "vitest";
import {
  calcularCorrecciones,
  contarRequierenRevision,
  contarSubidos,
  datosEncargoParaGuardar,
  encontrarJobActivo,
  estadoTile,
  ordenarPorConfianza,
} from "./ofLogic.js";

describe("ordenarPorConfianza", () => {
  it("ordena baja, media, alta — lo dudoso primero", () => {
    const cuentas = [
      { codigo_cuenta: "1", confianza: "alta" },
      { codigo_cuenta: "2", confianza: "baja" },
      { codigo_cuenta: "3", confianza: "media" },
    ];
    expect(ordenarPorConfianza(cuentas).map((c) => c.codigo_cuenta)).toEqual(["2", "3", "1"]);
  });

  it("dentro del mismo nivel de confianza, ordena por código de cuenta", () => {
    const cuentas = [
      { codigo_cuenta: "1.1.02", confianza: "baja" },
      { codigo_cuenta: "1.1.01", confianza: "baja" },
    ];
    expect(ordenarPorConfianza(cuentas).map((c) => c.codigo_cuenta)).toEqual([
      "1.1.01",
      "1.1.02",
    ]);
  });

  it("no muta el array original", () => {
    const cuentas = [{ codigo_cuenta: "1", confianza: "alta" }, { codigo_cuenta: "2", confianza: "baja" }];
    const original = [...cuentas];
    ordenarPorConfianza(cuentas);
    expect(cuentas).toEqual(original);
  });

  it("devuelve [] si no hay cuentas", () => {
    expect(ordenarPorConfianza(undefined)).toEqual([]);
  });
});

describe("contarRequierenRevision", () => {
  it("cuenta media y baja, no alta", () => {
    const cuentas = [
      { confianza: "alta" }, { confianza: "alta" },
      { confianza: "media" }, { confianza: "baja" },
    ];
    expect(contarRequierenRevision(cuentas)).toBe(2);
  });

  it("0 si todas son de alta confianza", () => {
    expect(contarRequierenRevision([{ confianza: "alta" }, { confianza: "alta" }])).toBe(0);
  });
});

describe("calcularCorrecciones", () => {
  const cuentas = [
    { codigo_cuenta: "1.1.01", categoria_final: "caja_bancos" },
    { codigo_cuenta: "1.1.02", categoria_final: "cxc" },
  ];

  it("solo incluye las que cambiaron respecto a categoria_final", () => {
    const edits = { "1.1.01": "activos_fijos", "1.1.02": "cxc" }; // la 2da no cambió
    expect(calcularCorrecciones(cuentas, edits)).toEqual([
      { codigo_cuenta: "1.1.01", categoria: "activos_fijos" },
    ]);
  });

  it("[] cuando no hay edits", () => {
    expect(calcularCorrecciones(cuentas, {})).toEqual([]);
  });

  it("ignora códigos de cuenta que ya no existen en la lista actual", () => {
    const edits = { "9.9.99": "caja_bancos" };
    expect(calcularCorrecciones(cuentas, edits)).toEqual([]);
  });
});

describe("contarSubidos", () => {
  const slots = ["f104", "f103", "mayor_general"];

  it("cuenta solo los slots con n_archivos > 0", () => {
    const estado = {
      f104: { n_archivos: 2 },
      f103: { n_archivos: 0 },
      mayor_general: { n_archivos: 1 },
    };
    expect(contarSubidos(estado, slots)).toBe(2);
  });

  it("0 si estadoSlots viene vacío/null", () => {
    expect(contarSubidos(null, slots)).toBe(0);
  });
});

describe("encontrarJobActivo", () => {
  it("elige el más reciente entre borrador/revision", () => {
    const jobs = [
      { id: 1, status: "done" },
      { id: 2, status: "borrador" },
      { id: 3, status: "revision" },
    ];
    expect(encontrarJobActivo(jobs).id).toBe(3);
  });

  it("null si no hay ninguno en borrador/revision", () => {
    expect(encontrarJobActivo([{ id: 1, status: "done" }, { id: 2, status: "failed" }])).toBeNull();
  });

  it("null con lista vacía", () => {
    expect(encontrarJobActivo([])).toBeNull();
  });
});

describe("datosEncargoParaGuardar", () => {
  it("recorta espacios de cliente_name y period_label", () => {
    const form = {
      cliente_name: "  Cliente X  ",
      period_label: "  2025  ",
      period_end: "",
      prepared_by_name: "",
      reviewed_by_name: "",
      firma_auditora: "audit_consulting",
    };
    const out = datosEncargoParaGuardar(form);
    expect(out.cliente_name).toBe("Cliente X");
    expect(out.period_label).toBe("2025");
  });

  it("convierte period_end vacío a null", () => {
    const form = {
      cliente_name: "C", period_label: "2025", period_end: "",
      prepared_by_name: "", reviewed_by_name: "", firma_auditora: "audit_consulting",
    };
    expect(datosEncargoParaGuardar(form).period_end).toBeNull();
  });

  it("conserva period_end cuando viene con valor", () => {
    const form = {
      cliente_name: "C", period_label: "2025", period_end: "2025-12-31",
      prepared_by_name: "", reviewed_by_name: "", firma_auditora: "audit_consulting",
    };
    expect(datosEncargoParaGuardar(form).period_end).toBe("2025-12-31");
  });

  it("convierte prepared_by_name / reviewed_by_name vacíos (o solo espacios) a null", () => {
    const form = {
      cliente_name: "C", period_label: "2025", period_end: "",
      prepared_by_name: "   ", reviewed_by_name: "", firma_auditora: "audit_consulting",
    };
    const out = datosEncargoParaGuardar(form);
    expect(out.prepared_by_name).toBeNull();
    expect(out.reviewed_by_name).toBeNull();
  });

  it("recorta espacios de prepared_by_name / reviewed_by_name con valor", () => {
    const form = {
      cliente_name: "C", period_label: "2025", period_end: "",
      prepared_by_name: "  Ana  ", reviewed_by_name: "  Beatriz  ",
      firma_auditora: "partner_auditing",
    };
    const out = datosEncargoParaGuardar(form);
    expect(out.prepared_by_name).toBe("Ana");
    expect(out.reviewed_by_name).toBe("Beatriz");
  });

  it("conserva firma_auditora tal cual", () => {
    const form = {
      cliente_name: "C", period_label: "2025", period_end: "",
      prepared_by_name: "", reviewed_by_name: "", firma_auditora: "partner_auditing",
    };
    expect(datosEncargoParaGuardar(form).firma_auditora).toBe("partner_auditing");
  });
});

describe("estadoTile", () => {
  it("done cuando el job está done, sea o no la clasificación", () => {
    expect(estadoTile("done", true)).toBe("done");
    expect(estadoTile("done", false)).toBe("done");
  });

  it("en revision, el tile de clasificación queda parcial ('')", () => {
    expect(estadoTile("revision", true)).toBe("");
  });

  it("en revision, las cédulas siguen dim (aún no se generó el Excel)", () => {
    expect(estadoTile("revision", false)).toBe("dim");
  });

  it("en borrador, todo dim", () => {
    expect(estadoTile("borrador", true)).toBe("dim");
    expect(estadoTile("borrador", false)).toBe("dim");
  });
});
