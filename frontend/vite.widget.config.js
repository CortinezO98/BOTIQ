/**
 * Configuración de build para el widget embebible de BOTIQ.
 * Genera un bundle JS único que se puede insertar en cualquier página.
 *
 * Uso en páginas externas:
 * <script src="https://tu-dominio.com/botiq-widget.js"></script>
 * <script>BotiqWidget.init({ apiUrl: '...', primaryColor: '#1E3A5F' })</script>
 */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist-widget",
    lib: {
      entry: "src/embed/widget-entry.jsx",
      name: "BotiqWidget",
      fileName: "botiq-widget",
      formats: ["iife"],   // Immediately Invoked Function Expression — compatible con <script>
    },
    rollupOptions: {
      external: [],        // Incluir React en el bundle (self-contained)
    },
  },
});
