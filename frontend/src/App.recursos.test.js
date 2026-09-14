// Fila CSV de la consola REC: accesos por recurso y estado de la cuenta.

import { describe, expect, it } from "vitest";
import { RECURSO_CSV_HEADERS, recursoCuentaCsvFila } from "./App.jsx";

describe("recursoCuentaCsvFila", () => {
  it("mapea accesos, estado y fechas en el orden de los encabezados", () => {
    const fila = recursoCuentaCsvFila({
      nombre: "Ana Pérez", empresa: "ACME", email: "ana@acme.ec",
      created_at: "2026-09-14T10:20:30.123", ultimo_ingreso_at: null,
      accesos: ["anticipo-ir-2026"], activo: false,
      consentimiento_at: "2026-09-14T10:20:00",
    });
    expect(fila).toEqual([
      "Ana Pérez", "ACME", "ana@acme.ec", "2026-09-14 10:20", "",
      "no", "si", "Desactivada", "2026-09-14 10:20",
    ]);
    expect(fila).toHaveLength(RECURSO_CSV_HEADERS.length);
  });

  it("tolera accesos ausentes", () => {
    const fila = recursoCuentaCsvFila({ nombre: "x", activo: true });
    expect(fila.slice(5, 8)).toEqual(["no", "no", "Activa"]);
  });
});
