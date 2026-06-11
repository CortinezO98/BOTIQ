/**
 * Hook de autenticación: login, logout, estado del usuario.
 */

import { useState, useCallback } from "react";
import { authAPI } from "../services/api";

export function useAuth() {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("botiq_user");
    return stored ? JSON.parse(stored) : null;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const login = useCallback(async (email, password) => {
    setLoading(true);
    setError(null);
    try {
      const response = await authAPI.login(email, password);
      const { access_token, user: userData } = response.data;

      localStorage.setItem("botiq_token", access_token);
      localStorage.setItem("botiq_user", JSON.stringify(userData));
      setUser(userData);
      return userData;
    } catch (err) {
      const message = err.response?.data?.detail || "Error al iniciar sesión";
      setError(message);
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("botiq_token");
    localStorage.removeItem("botiq_user");
    setUser(null);
  }, []);

  const isAdmin = user?.role === "admin";
  const isSupport = user?.role === "support_engineer" || isAdmin;

  return { user, loading, error, login, logout, isAdmin, isSupport };
}
