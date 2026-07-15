import { useCallback, useEffect, useState } from "react";
import { authAPI } from "../services/api";

export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [error, setError] = useState(null);

  // Ya no leemos token de localStorage: la cookie httpOnly viaja sola con
  // cada petición (withCredentials en api.js). Para saber si hay sesión
  // activa, simplemente preguntamos a /auth/me.
  const syncUser = useCallback(async () => {
    setCheckingSession(true);
    try {
      const { data } = await authAPI.me();
      setUser(data);
      return data;
    } catch {
      setUser(null);
      return null;
    } finally {
      setCheckingSession(false);
    }
  }, []);

  useEffect(() => {
    syncUser();
  }, [syncUser]);

  const login = useCallback(async (email, password) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await authAPI.login(email, password);
      // El backend ya seteó las cookies httpOnly en esta misma respuesta.
      setUser(data.user);
      return data.user;
    } catch (err) {
      const msg = err.response?.data?.detail || "Error al iniciar sesión";
      setError(msg);
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      // Revoca el refresh token en el backend y limpia las cookies.
      await authAPI.logout();
    } catch {
      // Si el backend no responde, igual limpiamos el estado local.
    }
    setUser(null);
    window.location.href = "/login";
  }, []);

  return {
    user,
    loading,
    checkingSession,
    error,
    login,
    logout,
    syncUser,
    isAdmin: user?.role === "admin",
    isSupport: ["support_engineer", "admin"].includes(user?.role),
  };
}