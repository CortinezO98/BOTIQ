import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { authAPI } from "../services/api";

/**
 * Antes, useAuth() era un hook "de fábrica": cada componente que lo llamaba
 * (Navbar, ChatPage, LoginPage, y ahora el Guard de App.jsx) creaba su
 * PROPIO estado independiente con su propio useState. Eso significa que
 * cuando LoginPage hacía login(), solo SU copia de `user` se actualizaba —
 * Navbar y el Guard de rutas seguían viendo la sesión vieja hasta que,
 * por casualidad, algo disparara su propio syncUser().
 *
 * Con Context, hay una única instancia de estado (la que vive en
 * <AuthProvider>) y todos los componentes que llaman useAuth() leen y
 * escriben sobre la misma fuente de verdad. Login/logout se reflejan de
 * inmediato en toda la app.
 */
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [error, setError] = useState(null);

  // La sesión vive en cookies httpOnly (no en localStorage): para saber si
  // hay sesión activa, preguntamos a /auth/me. La cookie viaja sola.
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

      if (data.mfa_required) {
        // Password correcto, falta el segundo factor. Todavía NO hay
        // sesión: no tocamos `user`. LoginPage se encarga de pedir el
        // código y llamar a verifyMfa() con el challenge token.
        return { mfaRequired: true, mfaChallengeToken: data.mfa_challenge_token };
      }

      setUser(data.user);
      return { mfaRequired: false, user: data.user };
    } catch (err) {
      const msg = err.response?.data?.detail || "Error al iniciar sesión";
      setError(msg);
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const verifyMfa = useCallback(async (mfaChallengeToken, code) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await authAPI.mfaVerify(mfaChallengeToken, code);
      setUser(data.user);
      return data.user;
    } catch (err) {
      const msg = err.response?.data?.detail || "Código incorrecto";
      setError(msg);
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authAPI.logout();
    } catch {
      // Si el backend no responde, igual limpiamos el estado local.
    }
    setUser(null);
    window.location.href = "/login";
  }, []);

  const value = {
    user,
    loading,
    checkingSession,
    error,
    login,
    verifyMfa,
    logout,
    syncUser,
    isAdmin: user?.role === "admin",
    isSupport: ["support_engineer", "admin"].includes(user?.role),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth() debe usarse dentro de <AuthProvider>. Revisa que App.jsx envuelva las rutas con <AuthProvider>.");
  }
  return ctx;
}
