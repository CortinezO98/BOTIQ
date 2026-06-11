import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

const api = axios.create({ baseURL: API_BASE, timeout: 30000 });

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
    const f = new FormData(); f.append("username", email); f.append("password", password);
    return api.post("/auth/login", f, { headers: { "Content-Type": "multipart/form-data" } });
  },
  me: () => api.get("/auth/me"),
};

export const chatAPI = {
  sendMessage: (message, sessionId, imageFile) => {
    const f = new FormData();
    f.append("message", message);
    if (sessionId) f.append("session_id", sessionId);
    if (imageFile) f.append("image", imageFile);
    return api.post("/chat/message", f, { headers: { "Content-Type": "multipart/form-data" } });
  },
  endSession: (sid) => api.post(`/chat/session/${sid}/end`),
};

export const faqAPI = {
  list: () => api.get("/employees/faqs"),
  create: (q, a, c) => api.post(`/employees/faqs?question=${encodeURIComponent(q)}&answer=${encodeURIComponent(a)}&category=${encodeURIComponent(c||"")}`),
  remove: (id) => api.delete(`/employees/faqs/${id}`),
};

export const serversAPI = {
  status: () => api.get("/servers/status"),
  analysis: () => api.get("/servers/analysis"),
};

export const dashboardAPI = {
  metrics: (d=30) => api.get(`/dashboard/metrics?days=${d}`),
  summary: () => api.get("/dashboard/summary"),
  byModule: (d=30) => api.get(`/dashboard/conversations-by-module?days=${d}`),
  byDay: (d=30) => api.get(`/dashboard/conversations-by-day?days=${d}`),
  topFaqs: (l=10) => api.get(`/dashboard/top-faqs?limit=${l}`),
  tokenConsumption: (d=30) => api.get(`/dashboard/token-consumption?days=${d}`),
  knowledgeGaps: (l=20) => api.get(`/dashboard/knowledge-gaps?limit=${l}`),
  escalationRate: (d=30) => api.get(`/dashboard/escalation-rate?days=${d}`),
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
