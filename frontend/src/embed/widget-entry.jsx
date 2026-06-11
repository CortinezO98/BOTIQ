/**
 * Entry point del widget embebible de BOTIQ.
 * Este archivo se compila como bundle IIFE para inserción en páginas externas.
 *
 * CÓMO INCRUSTAR EN OTRA PÁGINA:
 * ─────────────────────────────────────────────────────────────────
 * 1. Agregar antes del </body>:
 *
 * <div id="botiq-widget-root"></div>
 * <script src="https://tu-dominio.com/botiq-widget.js"></script>
 * <script>
 *   BotiqWidget.init({
 *     apiUrl: 'https://tu-api.com',
 *     primaryColor: '#1E3A5F',
 *     position: 'bottom-right',
 *     authToken: 'JWT_DEL_USUARIO_AUTENTICADO',  // Opcional: si ya tiene sesión
 *   });
 * </script>
 * ─────────────────────────────────────────────────────────────────
 */

import { createRoot } from "react-dom/client";
import ChatWidget from "../components/ChatWidget";

// API pública del widget
window.BotiqWidget = {
  init(config = {}) {
    const {
      apiUrl = "http://localhost:8000",
      primaryColor = "#1E3A5F",
      position = "bottom-right",
      authToken = null,
      containerId = "botiq-widget-root",
    } = config;

    // Guardar configuración
    if (authToken) {
      localStorage.setItem("botiq_token", authToken);
    }

    // Configurar URL de la API
    window.__BOTIQ_API_URL__ = apiUrl;

    // Crear contenedor si no existe
    let container = document.getElementById(containerId);
    if (!container) {
      container = document.createElement("div");
      container.id = containerId;
      document.body.appendChild(container);
    }

    // Montar el widget React
    const root = createRoot(container);
    root.render(
      <ChatWidget primaryColor={primaryColor} position={position} />
    );

    console.log("✅ BOTIQ Widget iniciado");
  },

  destroy() {
    const container = document.getElementById("botiq-widget-root");
    if (container) container.remove();
  },
};
