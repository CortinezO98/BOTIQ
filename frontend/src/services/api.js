import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

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

export const chatAPI = {
  sendMessage: (data) => api.post("/chat/message", data),
};

export const faqAPI = {
  list: () => api.get("/employees/faqs"),
  create: (data) => api.post("/employees/faqs", data),
  remove: (id) => api.delete(`/employees/faqs/${id}`),
};

export const serversAPI = {
  status: () => api.get("/servers/status"),
  analysis: () => api.get("/servers/analysis"),
};

export const dashboardAPI = {
  metrics: (days = 30) => api.get(`/dashboard/metrics?days=${days}`),
  summary: () => api.get("/dashboard/summary"),
};

export const supportAPI = {
  syncKnowledgeBase: () => api.post("/support/sync-knowledge-base"),
  knowledgeBaseStatus: () => api.get("/support/knowledge-base/status"),
};

export default api;
