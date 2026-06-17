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
      formats: ["iife"],
    },
  },
});


