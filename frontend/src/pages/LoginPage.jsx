import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const C = "#272163";
const CD = "#1a1645";
const CL = "#3a3490";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [show, setShow] = useState(false);
  const { login, loading, error } = useAuth();
  const nav = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    try { const u = await login(email, pass); nav(u.role === "admin" ? "/dashboard" : "/chat"); }
    catch {}
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: `linear-gradient(135deg, ${C} 0%, ${CL} 50%, #6366f1 100%)`,
      display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
      position: "relative", overflow: "hidden",
    }}>
      {/* Fondo decorativo */}
      <div style={{
        position: "absolute", width: 400, height: 400, borderRadius: "50%",
        background: "rgba(255,255,255,0.04)", top: -100, right: -100,
      }} />
      <div style={{
        position: "absolute", width: 300, height: 300, borderRadius: "50%",
        background: "rgba(255,255,255,0.03)", bottom: -80, left: -80,
      }} />

      <div style={{
        background: "#fff", borderRadius: 20, padding: "40px 40px",
        width: "100%", maxWidth: 420,
        boxShadow: "0 24px 64px rgba(39,33,99,0.35)",
        position: "relative",
      }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{
            width: 72, height: 72, background: C, borderRadius: 20,
            display: "flex", alignItems: "center", justifyContent: "center",
            margin: "0 auto 16px",
            boxShadow: `0 8px 24px rgba(39,33,99,0.3)`,
          }}>
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
              <circle cx="20" cy="20" r="18" stroke="rgba(255,255,255,0.3)" strokeWidth="2"/>
              <path d="M12 20 L20 12 L28 20 L20 28 Z" fill="rgba(255,255,255,0.2)" stroke="#fff" strokeWidth="1.5"/>
              <circle cx="20" cy="20" r="4" fill="#fff"/>
              <path d="M20 8 L20 12 M20 28 L20 32 M8 20 L12 20 M28 20 L32 20" stroke="#fff" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
          <h1 style={{ fontSize: 28, fontWeight: 700, color: C, margin: 0, letterSpacing: "-0.5px" }}>
            BOTIQ
          </h1>
          <p style={{ color: "#6b6b8a", fontSize: 13, marginTop: 6 }}>
            Asistente Corporativo Inteligente
          </p>
        </div>

        <form onSubmit={submit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Email corporativo
            </label>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)} required
              placeholder="usuario@iq.com"
              style={{
                width: "100%", padding: "11px 14px", border: `1.5px solid #e2e1f0`,
                borderRadius: 10, fontSize: 14, outline: "none", boxSizing: "border-box",
                transition: "border-color 0.2s, box-shadow 0.2s", background: "#fafafa",
              }}
              onFocus={e => { e.target.style.borderColor = C; e.target.style.boxShadow = `0 0 0 3px rgba(39,33,99,0.1)`; e.target.style.background = "#fff"; }}
              onBlur={e => { e.target.style.borderColor = "#e2e1f0"; e.target.style.boxShadow = "none"; e.target.style.background = "#fafafa"; }}
            />
          </div>

          <div style={{ marginBottom: 28 }}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Contraseña
            </label>
            <div style={{ position: "relative" }}>
              <input
                type={show ? "text" : "password"} value={pass} onChange={e => setPass(e.target.value)} required
                placeholder="••••••••"
                style={{
                  width: "100%", padding: "11px 44px 11px 14px", border: `1.5px solid #e2e1f0`,
                  borderRadius: 10, fontSize: 14, outline: "none", boxSizing: "border-box",
                  transition: "border-color 0.2s, box-shadow 0.2s", background: "#fafafa",
                }}
                onFocus={e => { e.target.style.borderColor = C; e.target.style.boxShadow = `0 0 0 3px rgba(39,33,99,0.1)`; e.target.style.background = "#fff"; }}
                onBlur={e => { e.target.style.borderColor = "#e2e1f0"; e.target.style.boxShadow = "none"; e.target.style.background = "#fafafa"; }}
              />
              <button type="button" onClick={() => setShow(v => !v)} style={{
                position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
                background: "none", border: "none", cursor: "pointer", color: "#9CA3AF", fontSize: 16,
              }}>
                {show ? "🙈" : "👁"}
              </button>
            </div>
          </div>

          {error && (
            <div style={{
              background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8,
              padding: "10px 14px", marginBottom: 16, fontSize: 13, color: "#dc2626",
              display: "flex", alignItems: "center", gap: 8,
            }}>
              ⚠️ {error}
            </div>
          )}

          <button type="submit" disabled={loading} style={{
            width: "100%", padding: "13px",
            background: loading ? "#9CA3AF" : `linear-gradient(135deg, ${C}, ${CL})`,
            color: "#fff", border: "none", borderRadius: 10,
            fontSize: 15, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer",
            boxShadow: loading ? "none" : `0 4px 16px rgba(39,33,99,0.3)`,
            transition: "all 0.2s", letterSpacing: "0.3px",
          }}>
            {loading ? "Ingresando..." : "Ingresar →"}
          </button>
        </form>

        <div style={{ textAlign: "center", marginTop: 24 }}>
          <p style={{ color: "#9CA3AF", fontSize: 11 }}>
            IQ Corporation · Powered by Vertex AI
          </p>
        </div>
      </div>
    </div>
  );
}
