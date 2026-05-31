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
        // Por defecto proxea al backend de Render. Para desarrollo contra un
        // backend local, exporta VITE_PROXY_TARGET=http://127.0.0.1:8000 antes
        // de `npm run dev` (sin tocar este archivo).
        target:
          process.env.VITE_PROXY_TARGET ||
          "https://auditbrain-python-runner.onrender.com",
        changeOrigin: true,
        secure: true,
      },
    },
  },
});
