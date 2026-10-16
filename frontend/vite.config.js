import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// El proxy /api es exclusivo del servidor de desarrollo.
// Requiere VITE_PROXY_TARGET explícito para evitar conexiones accidentales
// a servicios heredados. La compilación de producción usa VITE_API_BASE.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  server: {
    proxy: {
      "/api": {
        // Sin destino por defecto: configurar VITE_PROXY_TARGET para desarrollo.
        target: process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: true,
      },
    },
  },
});
