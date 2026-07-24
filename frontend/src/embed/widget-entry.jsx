/**
 * BOTIQ Widget embebible directo (modo legado).
 *
 * Para integraciones nuevas usa /widget/v1/botiq-loader.js, que crea un
 * iframe aislado. Este archivo se mantiene por compatibilidad con portales
 * que ya compilan botiq-widget.iife.js.
 */
import { createRoot } from "react-dom/client";

import ChatWidget from "../components/ChatWidget";
import {
  clearEmbeddedApi,
  configureEmbeddedApi,
} from "../services/api";

window.BotiqWidget = {
  _root: null,
  _containerId: null,

  init({
    apiUrl = "http://localhost:8002",
    authToken = null,
    tokenProvider = null,
    portalId = null,
    parentOrigin = window.location.origin,
    primaryColor = "#272163",
    position = "bottom-right",
    containerId = "botiq-root",
    allowedProfiles = ["employee"],
  } = {}) {
    this.destroy();

    localStorage.removeItem("botiq_token");
    localStorage.removeItem("botiq_user");

    configureEmbeddedApi({
      apiUrl,
      authToken,
      tokenProvider,
      portalId,
      parentOrigin,
    });

    let element = document.getElementById(containerId);
    if (!element) {
      element = document.createElement("div");
      element.id = containerId;
      document.body.appendChild(element);
    }

    this._containerId = containerId;
    this._root = createRoot(element);
    this._root.render(
      <ChatWidget
        primaryColor={primaryColor}
        position={position}
        allowedProfiles={allowedProfiles}
      />,
    );

    return this;
  },

  destroy() {
    this._root?.unmount();

    if (this._containerId) {
      document.getElementById(this._containerId)?.remove();
    }

    clearEmbeddedApi();
    this._root = null;
    this._containerId = null;
  },
};
