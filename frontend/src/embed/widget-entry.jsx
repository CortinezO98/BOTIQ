/**
 * BOTIQ Widget embebible — insertar en cualquier página corporativa.
 *
 * USO:
 * <div id="botiq-root"></div>
 * <script src="https://tu-dominio/botiq-widget.iife.js"></script>
 * <script>
 *   BotiqWidget.init({
 *     apiUrl: 'https://tu-api.com',
 *     authToken: 'JWT_DEL_USUARIO',   // opcional
 *     primaryColor: '#1E3A5F',
 *     position: 'bottom-right',
 *   });
 * </script>
 */
import { createRoot } from "react-dom/client";
import ChatWidget from "../components/ChatWidget";

window.BotiqWidget = {
  _root: null,

  init({ apiUrl = "http://localhost:8000", authToken = null, primaryColor = "#1E3A5F", position = "bottom-right", containerId = "botiq-root" } = {}) {
    if (authToken) localStorage.setItem("botiq_token", authToken);
    window.__BOTIQ_API_URL__ = apiUrl;

    let container = document.getElementById(containerId);
    if (!container) {
      container = document.createElement("div");
      container.id = containerId;
      document.body.appendChild(container);
    }

    this._root = createRoot(container);
    this._root.render(<ChatWidget primaryColor={primaryColor} position={position} />);
    console.log("✅ BOTIQ Widget cargado");
  },

  destroy() {
    this._root?.unmount();
    document.getElementById("botiq-root")?.remove();
  },
};
