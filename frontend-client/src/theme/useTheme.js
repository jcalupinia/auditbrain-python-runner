import { useEffect, useState } from "react";

/** Temas de fondo disponibles en el portal. El verde de marca se mantiene
 *  como acento en todos para combinar con la imagen y el logo AUDIT-IA. */
export const THEMES = [
  { id: "dark",  label: "Oscuro IA", swatch: "#04060a", ring: "#34d36a" },
  { id: "light", label: "Blanco",    swatch: "#ffffff", ring: "#1f9d57" },
  { id: "navy",  label: "Azul medio", swatch: "#0a2342", ring: "#34d36a" },
  { id: "slate", label: "Gris",      swatch: "#2b3038", ring: "#34d36a" },
];

const STORAGE_KEY = "ab_portal_theme";
const DEFAULT_THEME = "dark";

function applyTheme(id) {
  // "dark" es el default que ya viene en los CSS → no necesita atributo.
  if (id && id !== "dark") {
    document.documentElement.setAttribute("data-theme", id);
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

/** Hook de tema: persiste la elección del usuario en localStorage y la
 *  aplica al <html> como data-theme. Devuelve [theme, setTheme]. */
export function useTheme() {
  const [theme, setThemeState] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME;
    } catch {
      return DEFAULT_THEME;
    }
  });

  useEffect(() => {
    applyTheme(theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* almacenamiento no disponible — el tema sigue aplicado en memoria */
    }
  }, [theme]);

  return [theme, setThemeState];
}
