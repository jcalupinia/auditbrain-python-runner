// Validaciones del formulario de descarga del SRI, copiadas de la app de
// escritorio (aplicacion.py, "Iniciar proceso"). Puras, sin React, para
// probarlas sin montar la página.

// Establecimiento: "Todos" (o vacío) o exactamente 3 dígitos.
export function validarEstablecimiento(valor) {
  const v = String(valor || "").trim();
  if (!v || v.toLowerCase() === "todos") return { ok: true, valor: "Todos" };
  if (/^\d{3}$/.test(v)) return { ok: true, valor: v };
  return { ok: false, error: "El establecimiento debe ser 'Todos' o un número de tres dígitos (ej. 001)." };
}

// Punto de emisión: hasta 3 dígitos; obligatorio cuando hay establecimiento
// concreto (el robot lo exige después del login; mejor avisar antes).
export function validarPuntoEmision(valor, establecimiento) {
  const v = String(valor || "").replace(/\D/g, "").slice(0, 3);
  if (establecimiento !== "Todos" && !v) {
    return { ok: false, error: "El punto de emisión es obligatorio cuando se indica un establecimiento." };
  }
  return { ok: true, valor: v };
}

function ultimoDia(anio, mes) {
  return new Date(anio, mes, 0).getDate();
}

// Fecha fin del período pedido, según el modo de fecha del formulario.
export function fechaFinPeriodo({ modo_fecha, anio, mes, mes_fin, dia }) {
  const a = Number(anio);
  if (modo_fecha === "Año completo") return new Date(a, 11, 31);
  if (modo_fecha === "Rango de meses") { const m = Number(mes_fin); return new Date(a, m - 1, ultimoDia(a, m)); }
  const m = Number(mes);
  const d = Number(dia) > 0 ? Number(dia) : ultimoDia(a, m);
  return new Date(a, m - 1, d);
}

// El web service del SRI deja de entregar el XML de Emitidos pasados ~30 días
// de la autorización. Devuelve el aviso del escritorio o null si no aplica.
export function avisoXmlEmitidos({ origen, estado_emitidos, formatos, modo_rapido, periodo }, hoy = new Date(), dias = 30) {
  if (origen !== "Emitidos" || modo_rapido) return null;
  if (String(estado_emitidos || "").toLowerCase() !== "autorizados") return null;
  if (!formatos.includes("XML")) return null;
  const limite = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - dias);
  const fin = fechaFinPeriodo(periodo);
  if (fin >= limite) return null;
  const f = (x) => `${String(x.getDate()).padStart(2, "0")}/${String(x.getMonth() + 1).padStart(2, "0")}/${x.getFullYear()}`;
  const base = `Advertencia de fecha: para XML Emitidos, el período termina el ${f(fin)}, fuera del límite de ${dias} días (antes del ${f(limite)}).`;
  if (formatos.includes("PDF")) {
    return { continuar: true, formatos: formatos.filter((x) => x !== "XML"), mensaje: `${base} Se continuará automáticamente solo con PDF.` };
  }
  return { continuar: false, formatos, mensaje: `${base} Selecciona PDF o usa una fecha dentro de los últimos ${dias} días.` };
}
