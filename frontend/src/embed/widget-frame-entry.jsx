import { createRoot } from "react-dom/client";

import "../index.css";
import ChatWidget from "../components/ChatWidget";
import {
  clearEmbeddedApi,
  configureEmbeddedApi,
  setEmbeddedAuthToken,
} from "../services/api";
import "./widget-frame.css";

const FRAME_VERSION = "1.0.0";
const rootElement = document.getElementById("botiq-widget-frame-root");
const root = createRoot(rootElement);

let trustedParentOrigin = null;
let activePortalId = null;
let rendered = false;
const pendingTokenRequests = new Map();

function randomId() {
  return window.crypto?.randomUUID?.()
    || `botiq-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function decodeJwtPayload(token) {
  try {
    const part = String(token || "").split(".")[1];
    if (!part) return null;
    const normalized = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(
      normalized.length + ((4 - (normalized.length % 4)) % 4),
      "=",
    );
    return JSON.parse(window.atob(padded));
  } catch {
    return null;
  }
}

function normalizeOrigin(value) {
  const url = new URL(value);
  return url.origin;
}

function validateWidgetToken(token, eventOrigin, portalId) {
  const payload = decodeJwtPayload(token);
  if (!payload || payload.purpose !== "widget_access") {
    throw new Error("Token de widget inválido.");
  }

  if (!payload.exp || payload.exp <= Math.floor(Date.now() / 1000)) {
    throw new Error("El token temporal del widget expiró.");
  }

  if (String(payload.portal_id || "") !== String(portalId || "")) {
    throw new Error("El token no pertenece al portal solicitado.");
  }

  if (normalizeOrigin(payload.allowed_origin) !== normalizeOrigin(eventOrigin)) {
    throw new Error("El origin del portal no coincide con el token.");
  }

  return payload;
}

function validateApiUrl(value) {
  const resolved = new URL(value || "/api/v1", window.location.origin);
  if (resolved.origin !== window.location.origin) {
    throw new Error(
      "El iframe solo puede comunicarse con la API del mismo dominio BOTIQ.",
    );
  }
  return resolved.href.replace(/\/$/, "");
}

function sanitizeColor(value) {
  const color = String(value || "").trim();
  return /^#[0-9a-f]{6}$/i.test(color) ? color : "#272163";
}

function showBootstrapMessage(message, isError = false) {
  root.render(
    <main
      className={`botiq-frame-bootstrap ${
        isError ? "is-error" : ""
      }`}
      role={isError ? "alert" : "status"}
    >
      <div className="botiq-frame-bootstrap__logo">B</div>
      <strong>{isError ? "No fue posible iniciar BOTIQ" : "Conectando BOTIQ"}</strong>
      <span>{message}</span>
    </main>,
  );
}

function requestFreshToken() {
  if (!trustedParentOrigin || !activePortalId) {
    return Promise.reject(
      new Error("El iframe todavía no tiene un portal confiable."),
    );
  }

  const requestId = randomId();

  return new Promise((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      pendingTokenRequests.delete(requestId);
      reject(new Error("El portal no renovó el token de BOTIQ a tiempo."));
    }, 12000);

    pendingTokenRequests.set(requestId, {
      resolve,
      reject,
      timeoutId,
    });

    window.parent.postMessage(
      {
        type: "BOTIQ_WIDGET_TOKEN_REQUIRED",
        requestId,
        portalId: activePortalId,
      },
      trustedParentOrigin,
    );
  });
}

function renderWidget({ primaryColor }) {
  if (rendered) return;
  rendered = true;

  root.render(
    <ChatWidget
      embedded
      allowedProfiles={["employee"]}
      primaryColor={sanitizeColor(primaryColor)}
      onRequestClose={() => {
        window.parent.postMessage(
          { type: "BOTIQ_WIDGET_CLOSE" },
          trustedParentOrigin,
        );
      }}
    />,
  );
}

async function initializeFromParent(event, data) {
  const portalId = String(data.portalId || "").trim();
  const token = String(data.authToken || "").trim();

  if (!portalId || !token) {
    throw new Error("Falta la identidad temporal del portal.");
  }

  validateWidgetToken(token, event.origin, portalId);

  const apiUrl = validateApiUrl(
    data.apiUrl || `${window.location.origin}/api/v1`,
  );

  trustedParentOrigin = normalizeOrigin(event.origin);
  activePortalId = portalId;

  configureEmbeddedApi({
    apiUrl,
    authToken: token,
    tokenProvider: requestFreshToken,
    portalId,
    parentOrigin: trustedParentOrigin,
  });

  renderWidget({
    primaryColor: data.primaryColor,
  });

  window.parent.postMessage(
    {
      type: "BOTIQ_WIDGET_INITIALIZED",
      version: FRAME_VERSION,
      portalId,
    },
    trustedParentOrigin,
  );
}

function handleTokenResponse(event, data) {
  if (
    !trustedParentOrigin
    || event.source !== window.parent
    || normalizeOrigin(event.origin) !== trustedParentOrigin
  ) {
    return;
  }

  const pending = pendingTokenRequests.get(data.requestId);
  if (!pending) return;

  window.clearTimeout(pending.timeoutId);
  pendingTokenRequests.delete(data.requestId);

  try {
    const token = String(data.authToken || "").trim();
    validateWidgetToken(token, event.origin, activePortalId);
    setEmbeddedAuthToken(token);
    pending.resolve(token);
  } catch (error) {
    pending.reject(error);
  }
}

window.addEventListener("message", (event) => {
  if (event.source !== window.parent || !event.data) return;

  const data = event.data;

  if (data.type === "BOTIQ_WIDGET_INIT") {
    initializeFromParent(event, data).catch((error) => {
      clearEmbeddedApi();
      showBootstrapMessage(error.message, true);
    });
    return;
  }

  if (data.type === "BOTIQ_WIDGET_TOKEN_RESPONSE") {
    handleTokenResponse(event, data);
    return;
  }

  if (
    data.type === "BOTIQ_WIDGET_DESTROY"
    && trustedParentOrigin
    && normalizeOrigin(event.origin) === trustedParentOrigin
  ) {
    clearEmbeddedApi();
    window.location.reload();
  }
});

showBootstrapMessage(
  "Esperando la sesión segura del portal…",
);

window.parent.postMessage(
  {
    type: "BOTIQ_WIDGET_READY",
    version: FRAME_VERSION,
  },
  "*",
);
