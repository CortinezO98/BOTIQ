(function (window, document) {
  "use strict";

  var VERSION = "1.0.0";
  var currentScript = document.currentScript;
  var inferredBaseUrl = currentScript && currentScript.src
    ? currentScript.src.replace(/\/widget\/v1\/botiq-loader\.js(?:\?.*)?$/, "")
    : "";

  var activeInstance = null;

  function normalizeBaseUrl(value) {
    return String(value || inferredBaseUrl || "")
      .trim()
      .replace(/\/+$/, "");
  }

  function decodeJwtPayload(token) {
    try {
      var part = String(token || "").split(".")[1];
      if (!part) return null;
      var normalized = part.replace(/-/g, "+").replace(/_/g, "/");
      while (normalized.length % 4) normalized += "=";
      return JSON.parse(window.atob(normalized));
    } catch (error) {
      return null;
    }
  }

  function extractToken(value) {
    if (typeof value === "string") return value;
    if (!value || typeof value !== "object") return null;
    return value.access_token
      || value.token
      || (value.data && (value.data.access_token || value.data.token))
      || null;
  }

  function tokenIsFresh(token, leewaySeconds) {
    var payload = decodeJwtPayload(token);
    if (!payload || !payload.exp) return false;
    return payload.exp > Math.floor(Date.now() / 1000) + leewaySeconds;
  }

  function validateTokenForPortal(token, portalId) {
    var payload = decodeJwtPayload(token);
    if (!payload || payload.purpose !== "widget_access") {
      throw new Error("El portal no recibió un token BOTIQ válido.");
    }
    if (String(payload.portal_id || "") !== String(portalId || "")) {
      throw new Error("El token BOTIQ pertenece a otro portal.");
    }
    if (new URL(payload.allowed_origin).origin !== window.location.origin) {
      throw new Error("El token BOTIQ no pertenece al origin actual.");
    }
    if (!payload.exp || payload.exp <= Math.floor(Date.now() / 1000)) {
      throw new Error("El token temporal de BOTIQ está vencido.");
    }
    return payload;
  }

  function ensureStyles(baseUrl) {
    var id = "botiq-portal-widget-css";
    if (document.getElementById(id)) return;

    var link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = baseUrl + "/widget/v1/botiq-loader.css";
    document.head.appendChild(link);
  }

  function createIcon() {
    var wrapper = document.createElement("span");
    wrapper.className = "botiq-portal-widget__icon";
    wrapper.setAttribute("aria-hidden", "true");
    wrapper.innerHTML =
      '<svg viewBox="0 0 64 64" width="31" height="31" fill="none" xmlns="http://www.w3.org/2000/svg">'
      + '<rect x="14" y="18" width="36" height="30" rx="10" fill="rgba(255,255,255,.18)" stroke="#fff" stroke-width="2"/>'
      + '<path d="M24 18v-4c0-2.2 1.8-4 4-4h8c2.2 0 4 1.8 4 4v4" stroke="#fff" stroke-width="2" stroke-linecap="round"/>'
      + '<circle cx="26" cy="33" r="3.4" fill="#fff"/>'
      + '<circle cx="38" cy="33" r="3.4" fill="#fff"/>'
      + '<path d="M27 41h10M14 31H9M55 31h-5" stroke="#fff" stroke-width="2" stroke-linecap="round"/>'
      + "</svg>";
    return wrapper;
  }

  function createInstance(options) {
    var config = options || {};
    var baseUrl = normalizeBaseUrl(config.widgetBaseUrl);
    if (!baseUrl) {
      throw new Error(
        "No se pudo determinar widgetBaseUrl para BOTIQ.",
      );
    }

    var portalId = String(config.portalId || "").trim();
    if (!portalId) {
      throw new Error("portalId es obligatorio.");
    }

    if (
      typeof config.tokenProvider !== "function"
      && !config.tokenEndpoint
    ) {
      throw new Error(
        "Configura tokenProvider o tokenEndpoint para obtener el JWT temporal.",
      );
    }

    var widgetOrigin = new URL(baseUrl).origin;
    var apiUrl = String(
      config.apiUrl || (baseUrl + "/api/v1"),
    ).replace(/\/+$/, "");
    var position = config.position === "bottom-left"
      ? "bottom-left"
      : "bottom-right";

    ensureStyles(baseUrl);

    var host = document.createElement("div");
    host.className =
      "botiq-portal-widget botiq-portal-widget--" + position;
    host.dataset.botiqVersion = VERSION;

    var panel = document.createElement("div");
    panel.className = "botiq-portal-widget__panel";
    panel.hidden = true;

    var iframe = document.createElement("iframe");
    iframe.className = "botiq-portal-widget__frame";
    iframe.src = baseUrl + "/widget.html?v=" + encodeURIComponent(VERSION);
    iframe.title = config.title || "BOTIQ — Asistente corporativo";
    iframe.loading = "eager";
    iframe.referrerPolicy = "no-referrer";
    iframe.setAttribute(
      "sandbox",
      "allow-scripts allow-forms allow-same-origin",
    );
    iframe.setAttribute("allow", "clipboard-write");

    panel.appendChild(iframe);

    var status = document.createElement("div");
    status.className = "botiq-portal-widget__status";
    status.hidden = true;
    status.setAttribute("role", "alert");

    var button = document.createElement("button");
    button.type = "button";
    button.className = "botiq-portal-widget__button";
    button.setAttribute("aria-label", "Abrir BOTIQ");
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-controls", "botiq-portal-widget-panel");
    button.title = "Abrir BOTIQ";
    button.appendChild(createIcon());

    var online = document.createElement("span");
    online.className = "botiq-portal-widget__online";
    online.setAttribute("aria-hidden", "true");
    button.appendChild(online);

    panel.id = "botiq-portal-widget-panel";
    host.appendChild(panel);
    host.appendChild(status);
    host.appendChild(button);
    document.body.appendChild(host);

    var isOpen = false;
    var iframeReady = false;
    var initialized = false;
    var cachedToken = null;
    var tokenPromise = null;

    async function fetchTokenFromPortal() {
      if (typeof config.tokenProvider === "function") {
        return config.tokenProvider();
      }

      var response = await window.fetch(config.tokenEndpoint, {
        method: config.tokenMethod || "POST",
        credentials: "include",
        cache: "no-store",
        headers: Object.assign(
          {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          config.tokenHeaders || {},
        ),
        body: config.tokenBody === undefined
          ? JSON.stringify({})
          : JSON.stringify(config.tokenBody),
      });

      if (!response.ok) {
        var detail = "No fue posible iniciar la sesión BOTIQ.";
        try {
          var body = await response.json();
          detail = body.detail || body.message || detail;
        } catch (error) {
          // El portal puede responder sin JSON; se conserva mensaje genérico.
        }
        throw new Error(detail);
      }

      return response.json();
    }

    async function getToken(force) {
      if (!force && cachedToken && tokenIsFresh(cachedToken, 45)) {
        return cachedToken;
      }

      if (!tokenPromise) {
        tokenPromise = Promise.resolve(fetchTokenFromPortal())
          .then(function (value) {
            var token = extractToken(value);
            if (!token) {
              throw new Error(
                "El endpoint del portal no devolvió access_token.",
              );
            }
            validateTokenForPortal(token, portalId);
            cachedToken = token;
            return token;
          })
          .finally(function () {
            tokenPromise = null;
          });
      }

      return tokenPromise;
    }

    function postToFrame(message) {
      if (!iframe.contentWindow) return;
      iframe.contentWindow.postMessage(message, widgetOrigin);
    }

    function showError(error) {
      status.textContent = error && error.message
        ? error.message
        : "No fue posible abrir BOTIQ.";
      status.hidden = false;
      host.classList.add("has-error");
      window.console.error("[BOTIQ Widget]", error);
    }

    function clearError() {
      status.hidden = true;
      status.textContent = "";
      host.classList.remove("has-error");
    }

    async function initializeFrame() {
      if (!isOpen || !iframeReady) return;
      clearError();

      try {
        var token = await getToken(false);
        postToFrame({
          type: "BOTIQ_WIDGET_INIT",
          version: VERSION,
          portalId: portalId,
          authToken: token,
          apiUrl: apiUrl,
          primaryColor: config.primaryColor || "#272163",
        });
      } catch (error) {
        showError(error);
      }
    }

    function open() {
      isOpen = true;
      panel.hidden = false;
      host.classList.add("is-open");
      button.setAttribute("aria-expanded", "true");
      button.setAttribute("aria-label", "Cerrar BOTIQ");
      button.title = "Cerrar BOTIQ";
      initializeFrame();
    }

    function close() {
      isOpen = false;
      panel.hidden = true;
      host.classList.remove("is-open");
      button.setAttribute("aria-expanded", "false");
      button.setAttribute("aria-label", "Abrir BOTIQ");
      button.title = "Abrir BOTIQ";
      clearError();
    }

    function toggle() {
      if (isOpen) close();
      else open();
    }

    button.addEventListener("click", toggle);

    async function onMessage(event) {
      if (
        event.source !== iframe.contentWindow
        || event.origin !== widgetOrigin
        || !event.data
      ) {
        return;
      }

      var data = event.data;

      if (data.type === "BOTIQ_WIDGET_READY") {
        iframeReady = true;
        initializeFrame();
        return;
      }

      if (data.type === "BOTIQ_WIDGET_INITIALIZED") {
        initialized = true;
        clearError();
        return;
      }

      if (data.type === "BOTIQ_WIDGET_CLOSE") {
        close();
        return;
      }

      if (data.type === "BOTIQ_WIDGET_TOKEN_REQUIRED") {
        try {
          var token = await getToken(true);
          postToFrame({
            type: "BOTIQ_WIDGET_TOKEN_RESPONSE",
            requestId: data.requestId,
            authToken: token,
          });
        } catch (error) {
          showError(error);
          postToFrame({
            type: "BOTIQ_WIDGET_TOKEN_RESPONSE",
            requestId: data.requestId,
            authToken: "",
            error: error.message,
          });
        }
      }
    }

    window.addEventListener("message", onMessage);

    return {
      version: VERSION,
      open: open,
      close: close,
      toggle: toggle,
      refreshToken: function () {
        cachedToken = null;
        return getToken(true);
      },
      getState: function () {
        return {
          open: isOpen,
          ready: iframeReady,
          initialized: initialized,
          portalId: portalId,
          widgetOrigin: widgetOrigin,
        };
      },
      destroy: function () {
        window.removeEventListener("message", onMessage);
        postToFrame({ type: "BOTIQ_WIDGET_DESTROY" });
        cachedToken = null;
        tokenPromise = null;
        host.remove();
      },
    };
  }

  window.BotiqPortalWidget = {
    version: VERSION,

    init: function (options) {
      if (activeInstance) activeInstance.destroy();
      activeInstance = createInstance(options || {});
      return activeInstance;
    },

    open: function () {
      activeInstance && activeInstance.open();
    },

    close: function () {
      activeInstance && activeInstance.close();
    },

    destroy: function () {
      if (activeInstance) activeInstance.destroy();
      activeInstance = null;
    },

    getState: function () {
      return activeInstance ? activeInstance.getState() : null;
    },
  };
})(window, document);
