// Config de la herramienta bespoke de nómina 2.0: su cara es el panel y sus descargas
// son las cédulas del motor (no el `libro` genérico). Debe coincidir con el backend.
import { describe, expect, it } from "vitest";

import { CONFIG, configDeProcesador } from "./procesoConfig";

describe("procesoConfig · nómina 2.0 (bespoke)", () => {
  const nomina = configDeProcesador("nomina_beneficios");

  it("resuelve por processor y es bespoke (panel propio)", () => {
    expect(nomina).toBe(CONFIG.nomina);
    expect(nomina.processor).toBe("nomina_beneficios");
    expect(nomina.panel).toBe(true);
    expect(nomina.titulo).toMatch(/Pasivos Acumulados y Gastos de N[oó]mina/i);
  });

  it("pide los requerimientos del backend (RQ-002/003/004/006 principales, sin actuarial)", () => {
    const ids = nomina.principales.map((p) => p.id);
    for (const req of ["RQ-002", "RQ-003", "RQ-004", "RQ-006"]) expect(ids).toContain(req);
    // La parte actuarial salió del catálogo: nada de informe/censo actuarial.
    const texto = JSON.stringify(nomina).toLowerCase();
    expect(texto).not.toContain("actuarial");
    expect(texto).not.toContain("jubila");
  });

  it("las tarjetas de ejecución abren el panel o bajan cédulas del motor", () => {
    const panel = nomina.ejecuciones.filter((e) => e.panel);
    expect(panel).toHaveLength(1);
    const zip = nomina.ejecuciones.filter((e) => e.cedulasZip);
    expect(zip).toHaveLength(1);
    // Cada cédula declarada es un .xlsx (nombre de archivo que sirve el motor).
    const cedulas = nomina.ejecuciones.filter((e) => e.cedula).map((e) => e.cedula);
    expect(cedulas.length).toBeGreaterThanOrEqual(8);
    for (const c of cedulas) expect(c).toMatch(/\.xlsx$/);
    expect(cedulas).toContain("DO-12_Hallazgos_y_Ajustes.xlsx");
    expect(cedulas).toContain("VAC_Calculadora_Vacaciones_No_Gozadas.xlsx");
    // Ninguna tarjeta bespoke usa `seccion` (eso dispararía el `libro` genérico).
    expect(nomina.ejecuciones.every((e) => !e.seccion)).toBe(true);
  });
});
