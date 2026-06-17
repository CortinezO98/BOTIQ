import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || window.__BOTIQ_API_URL__ || "http://localhost:8002/api/v1";

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("botiq_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("botiq_token");
      localStorage.removeItem("botiq_user");
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
