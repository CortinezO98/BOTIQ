import { useCallback, useEffect, useState } from "react";
import { authAPI } from "../services/api";

function readUser() {
  try {
    return JSON.parse(localStorage.getItem("botiq_user"));
  } catch {
    return null;
  }
}

export function useAuth() {
  const [user, setUser] = useState(readUser);
  const [loading, setLoading] = useState(false);
  const [checkingSession, setCheckingSession] = useState(false);
  const [error, setError] = useState(null);

  const syncUser = useCallback(async () => {
    const token = localStorage.getItem("botiq_token");
    if (!token) {
      setUser(null);
      return null;
    }

    setCheckingSession(true);
    try {
      const { data } = await authAPI.me();
      localStorage.setItem("botiq_user", JSON.stringify(data));
      setUser(data);
      return data;
    } catch {
      localStorage.removeItem("botiq_token");
      localStorage.removeItem("botiq_user");
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
      localStorage.setItem("botiq_token", data.access_token);
      localStorage.setItem("botiq_user", JSON.stringify(data.user));
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

  const logout = useCallback(() => {
    localStorage.removeItem("botiq_token");
    localStorage.removeItem("botiq_user");
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
