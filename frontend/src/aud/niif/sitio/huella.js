// Huella de un archivo del sitio, independiente del final de línea: con
// core.autocrlf=true el mismo commit sale con CRLF o LF según la máquina.
import { createHash } from "node:crypto";

export const huella = (texto) =>
  createHash("sha256").update(texto.replace(/\r\n/g, "\n"), "utf8").digest("hex");
