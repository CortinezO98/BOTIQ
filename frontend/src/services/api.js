import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

const api = axios.create({ baseURL: API_BASE_URL, timeout: 30000 });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("botiq_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
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
    return api.post("/auth/login", form, { headers: { "Content-Type": "multipart/form-data" } });
  },
  register: (data) => api.post("/auth/register", data),
  me: () => api.get("/auth/me"),
};

// Chat usa multipart/form-data
export const chatAPI = {
  sendMessage: (message, sessionId, imageFile) => {
    const form = new FormData();
    form.append("message", message);
    if (sessionId) form.append("session_id", sessionId);
    if (imageFile) form.append("image", imageFile);
    return api.post("/chat/message", form, { headers: { "Content-Type": "multipart/form-data" } });
  },
  endSession: (sessionId) => api.post(`/chat/session/${sessionId}/end`),
};

export const faqAPI = {
  list: () => api.get("/employees/faqs"),
  create: (question, answer, category) =>
    api.post(`/employees/faqs?question=${encodeURIComponent(question)}&answer=${encodeURIComponent(answer)}&category=${encodeURIComponent(category || "")}`),
  remove: (id) => api.delete(`/employees/faqs/${id}`),
};

export const serversAPI = {
  status: () => api.get("/servers/status"),
  analysis: () => api.get("/servers/analysis"),
};

// Dashboard — todos los endpoints reales
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
  syncKnowledgeBase: () => api.post("/support/sync-knowledge-base"),
  knowledgeBaseStatus: () => api.get("/support/knowledge-base/status"),
};

// Admin users
export const adminAPI = {
  listUsers: () => api.get("/admin/users"),
  createUser: (data) => api.post("/admin/users", data),
  updateUser: (id, data) => api.put(`/admin/users/${id}`, data),
  changeRole: (id, role) => api.patch(`/admin/users/${id}/role`, { role }),
  disableUser: (id) => api.patch(`/admin/users/${id}/disable`),
  enableUser: (id) => api.patch(`/admin/users/${id}/enable`),
};

export default api;
