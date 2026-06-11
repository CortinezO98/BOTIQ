import { useState, useCallback } from "react";
import { authAPI } from "../services/api";

export function useAuth() {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("botiq_user")); } catch { return null; }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const login = useCallback(async (email, password) => {
    setLoading(true); setError(null);
    try {
      const { data } = await authAPI.login(email, password);
      localStorage.setItem("botiq_token", data.access_token);
      localStorage.setItem("botiq_user", JSON.stringify(data.user));
      setUser(data.user);
      return data.user;
    } catch (e) {
      const msg = e.response?.data?.detail || "Error al iniciar sesión";
      setError(msg); throw new Error(msg);
    } finally { setLoading(false); }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("botiq_token"); localStorage.removeItem("botiq_user");
    setUser(null);
  }, []);

  return { user, loading, error, login, logout,
    isAdmin: user?.role === "admin",
    isSupport: ["support_engineer","admin"].includes(user?.role) };
}
