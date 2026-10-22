// Sesión de un trabajo SRI en el navegador: el permiso firmado del motor dura
// 5 minutos (backend/app/aud/motor_analitico/router.py, VIDA_SEG) y una
// descarga puede tardar mucho más. El sondeo renueva el permiso antes de que
// venza; si no, el trabajo seguía en el servidor pero la pantalla se quedaba
// en "procesando" para siempre (401 silenciosos).
export const SONDEO_MS = 2500;            // 24/min: el motor admite 30/min por usuario
export const MARGEN_RENOVACION_MS = 30000;

export function sesionDesdePermiso(p, ahora = Date.now()) {
  const vidaSeg = Number(p?.expira_en) > 0 ? Number(p.expira_en) : 300;
  return { url: p.url, token: p.token, vence: ahora + vidaSeg * 1000 };
}

export function debeRenovar(vence, ahora = Date.now(), margen = MARGEN_RENOVACION_MS) {
  return !vence || ahora >= vence - margen;
}

// Paridad con la app de escritorio: sin formato y sin modo rápido no hay nada
// que descargar, así que no se lanza el robot.
export function formatosValidos(formatos, modoRapido) {
  return Boolean(modoRapido) || (Array.isArray(formatos) && formatos.length > 0);
}
