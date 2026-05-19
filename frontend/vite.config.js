import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// El servidor de desarrollo proxea /api hacia el backend de Render para
// evitar problemas de CORS en local. En producción no aplica: el frontend
// estático apunta al backend mediante VITE_API_BASE (.env) y el dominio
// real está en CORS_ALLOW_ORIGINS del servicio.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  server: {
    proxy: {
      "/api": {
        target: "https://auditbrain-python-runner.onrender.com",
        changeOrigin: true,
        secure: true,
      },
    },
  },
});
