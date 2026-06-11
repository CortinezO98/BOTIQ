import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8002/api/v1";

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("botiq_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("botiq_token");
      localStorage.removeItem("botiq_user");
      window.location.href = "/login";
    }

    return Promise.reject(err);
  }
);

export const authAPI = {
  login: (email, password) => {
    const form = new FormData();
    form.append("username", email);
    form.append("password", password);

    return api.post("/auth/login", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  me: () => api.get("/auth/me"),
};

export const chatAPI = {
  sendMessage: (message, sessionId, imageFile) => {
    const form = new FormData();
    form.append("message", message);

    if (sessionId) form.append("session_id", sessionId);
    if (imageFile) form.append("image", imageFile);

    return api.post("/chat/message", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  endSession: (sessionId) => api.post(`/chat/session/${sessionId}/end`),
  conversations: () => api.get("/chat/conversations"),
  conversationMessages: (id) => api.get(`/chat/conversations/${id}/messages`),
};

export const faqAPI = {
  list: () => api.get("/employees/faqs"),
  create: (data) => api.post("/employees/faqs", data),
  update: (id, data) => api.put(`/employees/faqs/${id}`, data),
  remove: (id) => api.delete(`/employees/faqs/${id}`),
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
  knowledgeGaps: (limit = 20) => api.get(`/dashboard/knowledge-gaps?limit=${limit}`),
  escalationRate: (days = 30) => api.get(`/dashboard/escalation-rate?days=${days}`),
};

export const supportAPI = {
  sync: () => api.post("/support/sync-knowledge-base"),
  status: () => api.get("/support/knowledge-base/status"),
};

export const adminAPI = {
  listUsers: () => api.get("/admin/users"),
  createUser: (data) => api.post("/admin/users", data),
  updateUser: (id, data) => api.put(`/admin/users/${id}`, data),
  changeRole: (id, role) => api.patch(`/admin/users/${id}/role`, { role }),
  disableUser: (id) => api.patch(`/admin/users/${id}/disable`),
  enableUser: (id) => api.patch(`/admin/users/${id}/enable`),
};

export default api;
