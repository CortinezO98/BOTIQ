// pages/DashboardPage.jsx
import Dashboard from "../components/Dashboard";
import { useAuth } from "../hooks/useAuth";
import { useNavigate } from "react-router-dom";
import { Bot, MessageCircle, LogOut } from "lucide-react";

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div style={{ minHeight: "100vh" }}>
      <nav style={{ background: "#1E3A5F", padding: "0 24px", height: "56px", display: "flex", alignItems: "center", justifyContent: "space-between", position: "sticky", top: 0, zIndex: 100 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Bot size={20} color="#fff" />
          <span style={{ color: "#fff", fontWeight: 700, fontSize: "16px" }}>BOTIQ</span>
          <span style={{ color: "rgba(255,255,255,0.4)", margin: "0 4px" }}>/</span>
          <span style={{ color: "rgba(255,255,255,0.7)", fontSize: "14px" }}>Dashboard</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <span style={{ color: "rgba(255,255,255,0.7)", fontSize: "13px" }}>{user?.full_name}</span>
          <button onClick={() => navigate("/chat")} style={{ background: "rgba(255,255,255,0.1)", border: "none", color: "#fff", padding: "6px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "13px", display: "flex", alignItems: "center", gap: "6px" }}>
            <MessageCircle size={14} /> Chat
          </button>
          <button onClick={logout} style={{ background: "none", border: "none", color: "rgba(255,255,255,0.7)", cursor: "pointer" }}>
            <LogOut size={18} />
          </button>
        </div>
      </nav>
      <Dashboard />
    </div>
  );
}
