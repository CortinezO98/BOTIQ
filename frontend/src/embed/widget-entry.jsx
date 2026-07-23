/**
 * BOTIQ Widget embebible en cualquier página.
 * 
 * USO:
 * <div id="botiq-root"></div>
 * <script src="botiq-widget.iife.js"></script>
 * <script>
 *   BotiqWidget.init({
 *     apiUrl: 'https://tu-api.com',
 *     authToken: 'JWT_TOKEN',
 *     primaryColor: '#272163',
 *     position: 'bottom-right',
 *   });
 * </script>
 */
import { createRoot } from "react-dom/client";
import ChatWidget from "../components/ChatWidget";

window.BotiqWidget = {
  _root: null,
  init({ apiUrl = "http://localhost:8000", authToken = null, primaryColor = "#272163", position = "bottom-right", containerId = "botiq-root" } = {}) {
    // Token efímero del widget. Nunca persistir credenciales en localStorage.
    localStorage.removeItem("botiq_token");
    window.__BOTIQ_EMBED_AUTH_TOKEN__ = authToken || null;
    window.__BOTIQ_API_URL__ = apiUrl;
    let el = document.getElementById(containerId);
    if (!el) { el = document.createElement("div"); el.id = containerId; document.body.appendChild(el); }
    this._root = createRoot(el);
    this._root.render(<ChatWidget primaryColor={primaryColor} position={position} />);
  },
  destroy() {
    this._root?.unmount();
    document.getElementById("botiq-root")?.remove();
    delete window.__BOTIQ_EMBED_AUTH_TOKEN__;
    delete window.__BOTIQ_API_URL__;
    this._root = null;
  },
};
