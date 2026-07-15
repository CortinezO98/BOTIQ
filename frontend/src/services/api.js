import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || window.__BOTIQ_API_URL__ || "http://localhost:8002/api/v1";

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  // La sesión vive en cookies httpOnly (botiq_access_token / botiq_refresh_token).
  // Sin esto, el navegador no manda ni recibe esas cookies en llamadas cross-origin
  // (localhost:5180 -> localhost:8002 son orígenes distintos aunque mismo "site").
  withCredentials: true,
});

let refreshPromise = null;

function isAuthEndpoint(url = "") {
  return url.includes("/auth/login") || url.includes("/auth/refresh") || url.includes("/auth/register");
}

// Si una petición falla con 401 (access token vencido), intenta renovar la
// sesión UNA vez vía /auth/refresh y reintenta la petición original. Si el
// refresh también falla, la sesión realmente expiró y el error sigue su curso
// normal (useAuth.syncUser lo interpreta como "sin sesión").
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status === 401 &&
      original &&
      !original._retried &&
      !isAuthEndpoint(original.url || "")
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
        // El refresh también falló: dejamos que el 401 original se propague.
      }
    }
    return Promise.reject(error);
  }
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
    return api.post("/chat/message", form, {
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