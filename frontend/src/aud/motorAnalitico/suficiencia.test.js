import { describe, expect, it } from "vitest";
import { ESTADOS, filasSuficiencia, resumenLectura } from "./suficiencia.js";

const RESPUESTA = {
  estado: "Parcial", disponibles: 7, no_disponibles: 31,
  reglas: {
    "AST-007": { disponible: true, faltan: [], bases_faltantes: [], evidencia_incompleta: ["mayor.usuario"] },
    "AST-001": { disponible: false, faltan: ["mayor.origen"], bases_faltantes: [], evidencia_incompleta: [] },
    "CON-001": { disponible: false, faltan: [], bases_faltantes: ["comprobantes"], evidencia_incompleta: [] },
    "AST-004": { disponible: true, faltan: [], bases_faltantes: [], evidencia_incompleta: [],
                 motivo_no_corrida: "requiere fecha de captura real (la contable no la sustituye)" },
    "GAS-004": { disponible: true, faltan: [], bases_faltantes: [], evidencia_incompleta: [],
                 motivo_no_corrida: "pendiente de SP3-B" },
  },
};

describe("panel de suficiencia", () => {
  it("clasifica cada regla en un estado legible", () => {
    const filas = Object.fromEntries(filasSuficiencia(RESPUESTA).map((f) => [f.regla, f]));
    expect(filas["AST-007"].estado).toBe(ESTADOS.corrio);
    expect(filas["AST-007"].detalle).toBe("Sin el dato de usuario en la evidencia");
    expect(filas["AST-001"].estado).toBe(ESTADOS.sinDatos);
    expect(filas["AST-001"].detalle).toBe("Falta la columna origen");
    expect(filas["CON-001"].detalle).toBe("Falta cargar comprobantes");
    expect(filas["AST-004"].estado).toBe(ESTADOS.noCorrio);
    expect(filas["AST-004"].detalle).toBe("requiere fecha de captura real (la contable no la sustituye)");
    expect(filas["GAS-004"].estado).toBe(ESTADOS.noCorrio);
  });

  it("ordena primero lo que corrió y luego lo que no", () => {
    const orden = filasSuficiencia(RESPUESTA).map((f) => f.estado);
    expect(orden[0]).toBe(ESTADOS.corrio);
    expect(orden[orden.length - 1]).toBe(ESTADOS.sinDatos);
  });

  it("resume la lectura del archivo", () => {
    const r = resumenLectura({
      filas_leidas: 24890, filas_descartadas: 274, cuentas: 274,
      hojas_leidas: ["Hoja1"], columnas_detectadas: { codigo: 0, debe: 6, haber: 7 },
      columnas_vacias: ["usuario"], rango_fechas: ["2026-01-01", "2026-05-31"],
      sha256: "a".repeat(64),
    });
    expect(r.filas).toBe("24.890 movimientos · 274 filas descartadas");
    expect(r.periodo).toBe("2026-01-01 a 2026-05-31");
    expect(r.columnas).toBe("codigo, debe, haber");
    expect(r.vacias).toBe("usuario");
    expect(r.huella).toBe("a".repeat(16) + "…");
  });

  it("sin lectura no inventa nada", () => {
    expect(resumenLectura(null)).toBeNull();
  });
});
