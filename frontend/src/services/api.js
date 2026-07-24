import axios from "axios";

function normalizeApiUrl(value) {
  const raw = String(value || "").trim().replace(/\/+$/, "");
  if (!raw) return "http://localhost:8002/api/v1";
  return /\/api\/v1$/i.test(raw) ? raw : `${raw}/api/v1`;
}

function backendRootFromApi(apiUrl) {
  return normalizeApiUrl(apiUrl).replace(/\/api\/v1\/?$/i, "");
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

function tokenExpiresSoon(token, leewaySeconds = 30) {
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return false;
  return payload.exp <= Math.floor(Date.now() / 1000) + leewaySeconds;
}

const DEFAULT_API_URL = normalizeApiUrl(
  import.meta.env.VITE_API_URL
    || window.__BOTIQ_API_URL__
    || "http://localhost:8002/api/v1",
);

const runtime = {
  mode: "cookie",
  apiUrl: DEFAULT_API_URL,
  authToken: null,
  tokenProvider: null,
  portalId: null,
  parentOrigin: null,
};

const api = axios.create({
  baseURL: DEFAULT_API_URL,
  timeout: 30000,
  withCredentials: true,
});

let refreshPromise = null;
let widgetTokenPromise = null;

function extractToken(value) {
  if (typeof value === "string") return value;
  return value?.access_token || value?.token || null;
}

async function ensureWidgetToken(force = false) {
  if (runtime.mode !== "widget") return null;

  if (
    !force
    && runtime.authToken
    && !tokenExpiresSoon(runtime.authToken)
  ) {
    return runtime.authToken;
  }

  if (typeof runtime.tokenProvider !== "function") {
    return runtime.authToken;
  }

  if (!widgetTokenPromise) {
    widgetTokenPromise = Promise.resolve(runtime.tokenProvider())
      .then((value) => {
        const token = extractToken(value);
        if (!token) {
          throw new Error(
            "El portal no entregó un token temporal válido para BOTIQ.",
          );
        }
        runtime.authToken = token;
        return token;
      })
      .finally(() => {
        widgetTokenPromise = null;
      });
  }

  return widgetTokenPromise;
}

export function configureEmbeddedApi({
  apiUrl,
  authToken = null,
  tokenProvider = null,
  portalId,
  parentOrigin,
} = {}) {
  const normalizedApiUrl = normalizeApiUrl(apiUrl || DEFAULT_API_URL);

  runtime.mode = "widget";
  runtime.apiUrl = normalizedApiUrl;
  runtime.authToken = authToken || null;
  runtime.tokenProvider = tokenProvider || null;
  runtime.portalId = String(portalId || "").trim() || null;
  runtime.parentOrigin = String(parentOrigin || "").trim() || null;

  api.defaults.baseURL = normalizedApiUrl;
  api.defaults.withCredentials = false;

  // Compatibilidad temporal para integraciones antiguas que consultaban
  // esta variable. El interceptor ya no depende de ella.
  window.__BOTIQ_API_URL__ = normalizedApiUrl;

  return {
    apiUrl: runtime.apiUrl,
    mode: runtime.mode,
    portalId: runtime.portalId,
    parentOrigin: runtime.parentOrigin,
  };
}

export function setEmbeddedAuthToken(token) {
  runtime.authToken = token || null;
}

export function clearEmbeddedApi() {
  runtime.mode = "cookie";
  runtime.apiUrl = DEFAULT_API_URL;
  runtime.authToken = null;
  runtime.tokenProvider = null;
  runtime.portalId = null;
  runtime.parentOrigin = null;
  widgetTokenPromise = null;

  api.defaults.baseURL = DEFAULT_API_URL;
  api.defaults.withCredentials = true;

  delete window.__BOTIQ_API_URL__;
  delete window.__BOTIQ_EMBED_AUTH_TOKEN__;
}

export function getApiRuntimeConfig() {
  return {
    mode: runtime.mode,
    apiUrl: runtime.apiUrl,
    portalId: runtime.portalId,
    parentOrigin: runtime.parentOrigin,
    hasAuthToken: Boolean(runtime.authToken),
    hasTokenProvider: typeof runtime.tokenProvider === "function",
  };
}

export const healthAPI = {
  check: () =>
    axios.get(`${backendRootFromApi(runtime.apiUrl)}/health`, {
      timeout: 5000,
      withCredentials: runtime.mode !== "widget",
    }),
};

function isAuthEndpoint(url = "") {
  return (
    url.includes("/auth/login")
    || url.includes("/auth/refresh")
    || url.includes("/auth/register")
  );
}

api.interceptors.request.use(async (config) => {
  if (runtime.mode !== "widget") return config;

  const token = await ensureWidgetToken(false);
  if (!token) {
    throw new Error(
      "No existe un token temporal para inicializar el widget BOTIQ.",
    );
  }

  config.headers = config.headers || {};
  config.headers.Authorization = `Bearer ${token}`;
  config.headers["X-BOTIQ-Portal-Id"] = runtime.portalId;
  config.headers["X-BOTIQ-Parent-Origin"] = runtime.parentOrigin;
  config.withCredentials = false;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;

    if (
      runtime.mode === "widget"
      && error.response?.status === 401
      && original
      && !original._widgetRetried
    ) {
      original._widgetRetried = true;
      runtime.authToken = null;

      try {
        await ensureWidgetToken(true);
        return api(original);
      } catch {
        return Promise.reject(error);
      }
    }

    if (
      runtime.mode !== "widget"
      && error.response?.status === 401
      && original
      && !original._retried
      && !isAuthEndpoint(original.url || "")
    ) {
      original._retried = true;
      try {
        if (!refreshPromise) {
          refreshPromise = api.post("/auth/refresh").finally(() => {
            refreshPromise = null;
          });
        }
        await refreshPromise;
        return api(original);
      } catch {
        // La cookie de refresh también expiró; se propaga el 401 original.
      }
    }

    return Promise.reject(error);
  },
);

export const authAPI = {
  login: (email, password) => {
    const form = new FormData();
    form.append("username", email);
    form.append("password", password);
    return api.post("/auth/login", form);
  },
  me: () => api.get("/auth/me"),
  refresh: () => api.post("/auth/refresh"),
  logout: () => api.post("/auth/logout"),

  // MFA (TOTP)
  mfaVerify: (mfaChallengeToken, code) =>
    api.post("/auth/mfa/verify", { mfa_challenge_token: mfaChallengeToken, code }),
  mfaSetup: () => api.post("/auth/mfa/setup"),
  mfaConfirm: (code) => api.post("/auth/mfa/confirm", { code }),
  mfaDisable: (password, code) => api.post("/auth/mfa/disable", { password, code }),
};

export const chatAPI = {
  startSession: (data) => api.post("/chat/session/start", data),

  sendMessage: (message, sessionId, imageFile = null) => {
    const form = new FormData();
    form.append("message", message || "");
    form.append("session_id", sessionId);
    if (imageFile) form.append("image", imageFile);
    return api.post("/chat/message-smart", form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60000,
    });
  },

  endSession: (sessionId) => api.post(`/chat/session/${sessionId}/end`),

  conversations: () => api.get("/chat/conversations"),

  conversationMessages: (id) => api.get(`/chat/conversations/${id}/messages`),

  adminConversationLogs: (params = {}) => api.get("/chat/admin/conversation-logs", { params }),

  adminConversationMessages: (conversationId) =>
    api.get(`/chat/admin/conversation-logs/${conversationId}/messages`),

  adminConversationLogsExport: (params = {}) =>
    api.get("/chat/admin/conversation-logs/export", { params, responseType: "blob", timeout: 60000 }),

  // Feedback 👍/👎 por mensaje del bot
  submitFeedback: (messageId, rating, comment = null) =>
    api.post(`/chat/message/${messageId}/feedback`, { rating, comment }),

  // Encuesta de satisfacción al cerrar conversación
  submitSatisfaction: (sessionId, score, comment = null) =>
    api.post(`/chat/session/${sessionId}/satisfaction`, { score, comment }),
};

export const faqAPI = {
  list: () => api.get("/employees/faqs"),
  create: (data) => api.post("/employees/faqs", data),
  update: (id, data) => api.put(`/employees/faqs/${id}`, data),
  remove: (id) => api.delete(`/employees/faqs/${id}`),
};

export const supportAPI = {
  sync: (force = false) => api.post(`/support/sync-knowledge-base?force=${force}`),
  status: () => api.get("/support/knowledge-base/status"),
  documents: () => api.get("/support/knowledge-base/documents"),
  reindexDocument: (fileId) =>
    api.post(`/support/knowledge-base/documents/${fileId}/reindex`, null, { timeout: 120000 }),
};

export const serversAPI = {
  status: () => api.get("/servers/status"),
  analysis: () => api.get("/servers/analysis"),
};

export const serversKnowledgeAPI = {
  sync: (force = false) => api.post(`/servers-kb/sync-knowledge-base?force=${force}`),
  status: () => api.get("/servers-kb/knowledge-base/status"),
  documents: () => api.get("/servers-kb/knowledge-base/documents"),
  reindexDocument: (fileId) =>
    api.post(`/servers-kb/knowledge-base/documents/${fileId}/reindex`, null, { timeout: 120000 }),
  ask: (message) => api.post("/servers-kb/ask", { message }, { timeout: 60000 }),
};

export const dashboardAPI = {
  metrics: (days = 30) => api.get(`/dashboard/metrics?days=${days}`),
  summary: () => api.get("/dashboard/summary"),
  byModule: (days = 30) => api.get(`/dashboard/conversations-by-module?days=${days}`),
  byDay: (days = 30) => api.get(`/dashboard/conversations-by-day?days=${days}`),
  topFaqs: (limit = 10) => api.get(`/dashboard/top-faqs?limit=${limit}`),
  tokenConsumption: (days = 30) => api.get(`/dashboard/token-consumption?days=${days}`),
  knowledgeGaps: (limit = 20, status = "open") =>
    api.get(`/dashboard/knowledge-gaps?limit=${limit}&status=${status}`),
  escalationRate: (days = 30) => api.get(`/dashboard/escalation-rate?days=${days}`),
};

export const adminAPI = {
  listUsers: () => api.get("/admin/users"),
  createUser: (data) => api.post("/admin/users", data),
  updateUser: (id, data) => api.put(`/admin/users/${id}`, data),
  changeRole: (id, role) => api.patch(`/admin/users/${id}/role`, { role }),
  disableUser: (id) => api.patch(`/admin/users/${id}/disable`),
  enableUser: (id) => api.patch(`/admin/users/${id}/enable`),

  listNetworkUsers: (q = "") => api.get("/admin/network-users", { params: { q } }),
  createNetworkUser: (data) => api.post("/admin/network-users", data),
  updateNetworkUser: (id, data) => api.put(`/admin/network-users/${id}`, data),

  listWebKnowledge: (status = "pending", q = "", limit = 100) =>
    api.get("/admin/web-knowledge-cache", { params: { status, q, limit } }),
  updateWebKnowledge: (id, data) => api.put(`/admin/web-knowledge-cache/${id}`, data),
  approveWebKnowledge: (id, data = {}) => api.patch(`/admin/web-knowledge-cache/${id}/approve`, data),
  rejectWebKnowledge: (id, reason = "") => api.patch(`/admin/web-knowledge-cache/${id}/reject`, { reason }),

  // Gobierno de IA — respuestas generadas sin fuente interna (general_assistant_service)
  listAiKnowledge: (status = "pending", q = "", limit = 100) =>
    api.get("/admin/ai-knowledge-cache", { params: { status, q, limit } }),
  approveAiKnowledge: (id, data = {}) => api.patch(`/admin/ai-knowledge-cache/${id}/approve`, data),
  rejectAiKnowledge: (id, reason = "") => api.patch(`/admin/ai-knowledge-cache/${id}/reject`, { reason }),

  // Gobierno de IA — alertas de incidentes masivos
  listIncidentAlerts: (status = "open", limit = 50) =>
    api.get("/admin/incident-alerts", { params: { status, limit } }),
  incidentAlertsCount: () => api.get("/dashboard/incident-alerts/count"),
  acknowledgeIncident: (id, notes = "") => api.patch(`/admin/incident-alerts/${id}/acknowledge`, { notes }),
  resolveIncident: (id, notes = "") => api.patch(`/admin/incident-alerts/${id}/resolve`, { notes }),

  // Gobierno de IA — resumen de feedback 👍/👎 y satisfacción
  feedbackSummary: (limit = 10) => api.get("/chat/feedback/summary", { params: { limit } }),
};

// --- Utilidades de reportería ---

export function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export function downloadCsvFromRows(rows, filename) {
  // rows: array de objetos planos. Separador ";" + BOM para compatibilidad con Excel.
  if (!rows || rows.length === 0) return;
  const headers = Object.keys(rows[0]);
  const escape = (value) => {
    const s = String(value ?? "");
    return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.join(";"), ...rows.map((r) => headers.map((h) => escape(r[h])).join(";"))];
  const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  downloadBlob(blob, filename);
}

export default api;
