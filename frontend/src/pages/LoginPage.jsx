// pages/LoginPage.jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Bot } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { login, loading, error } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const user = await login(email, password);
      navigate(user.role === "admin" ? "/dashboard" : "/chat");
    } catch {}
  };

  return (
    <div style={{ minHeight: "100vh", background: "#F9FAFB", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "#fff", borderRadius: "16px", padding: "40px", width: "100%", maxWidth: "400px", boxShadow: "0 4px 24px rgba(0,0,0,0.08)" }}>
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <div style={{ width: "56px", height: "56px", background: "#1E3A5F", borderRadius: "16px", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
            <Bot size={28} color="#fff" />
          </div>
          <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#111827", margin: 0 }}>BOTIQ</h1>
          <p style={{ color: "#6B7280", margin: "4px 0 0", fontSize: "14px" }}>Asistente Corporativo Inteligente</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontSize: "13px", fontWeight: 500, color: "#374151", marginBottom: "6px" }}>
              Email corporativo
            </label>
            <input
              type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
              style={{ width: "100%", padding: "10px 14px", border: "1px solid #E5E7EB", borderRadius: "8px", fontSize: "14px", outline: "none", boxSizing: "border-box" }}
            />
          </div>
          <div style={{ marginBottom: "24px" }}>
            <label style={{ display: "block", fontSize: "13px", fontWeight: 500, color: "#374151", marginBottom: "6px" }}>
              Contraseña
            </label>
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
              style={{ width: "100%", padding: "10px 14px", border: "1px solid #E5E7EB", borderRadius: "8px", fontSize: "14px", outline: "none", boxSizing: "border-box" }}
            />
          </div>

          {error && (
            <div style={{ background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: "8px", padding: "10px 14px", marginBottom: "16px", fontSize: "13px", color: "#DC2626" }}>
              {error}
            </div>
          )}

          <button
            type="submit" disabled={loading}
            style={{ width: "100%", padding: "12px", background: loading ? "#9CA3AF" : "#1E3A5F", color: "#fff", border: "none", borderRadius: "8px", fontSize: "15px", fontWeight: 600, cursor: loading ? "not-allowed" : "pointer" }}
          >
            {loading ? "Iniciando sesión..." : "Ingresar"}
          </button>
        </form>
      </div>
    </div>
  );
}
