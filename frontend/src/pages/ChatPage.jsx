// pages/ChatPage.jsx
import ChatWidget from "../components/ChatWidget";
import { useAuth } from "../hooks/useAuth";
import { useNavigate } from "react-router-dom";
import { LogOut, LayoutDashboard, Bot } from "lucide-react";

export default function ChatPage() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();

  return (
    <div style={{ minHeight: "100vh", background: "#F0F4F8" }}>
      {/* Navbar */}
      <nav style={{ background: "#1E3A5F", padding: "0 24px", height: "56px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Bot size={20} color="#fff" />
          <span style={{ color: "#fff", fontWeight: 700, fontSize: "16px" }}>BOTIQ</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <span style={{ color: "rgba(255,255,255,0.7)", fontSize: "13px" }}>{user?.full_name}</span>
          {isAdmin && (
            <button onClick={() => navigate("/dashboard")} style={{ background: "rgba(255,255,255,0.1)", border: "none", color: "#fff", padding: "6px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}>
              <LayoutDashboard size={14} /> Dashboard
            </button>
          )}
          <button onClick={logout} style={{ background: "none", border: "none", color: "rgba(255,255,255,0.7)", cursor: "pointer" }}>
            <LogOut size={18} />
          </button>
        </div>
      </nav>

      {/* Content */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "calc(100vh - 56px)" }}>
        <div style={{ textAlign: "center", color: "#6B7280" }}>
          <Bot size={64} style={{ opacity: 0.2, margin: "0 auto 16px" }} />
          <h2 style={{ fontWeight: 600, color: "#374151" }}>¡Bienvenido a BOTIQ!</h2>
          <p style={{ fontSize: "14px" }}>Haz clic en el botón azul para abrir el asistente</p>
        </div>
      </div>

      {/* Widget flotante */}
      <ChatWidget primaryColor="#1E3A5F" position="bottom-right" />
    </div>
  );
}
