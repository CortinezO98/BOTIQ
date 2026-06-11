import Dashboard from "../components/Dashboard";
import { useAuth } from "../hooks/useAuth";
import { useNavigate } from "react-router-dom";
import { Bot, MessageCircle, LogOut } from "lucide-react";

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div style={{ minHeight: "100vh" }}>
      <nav style={{ background: "#1E3A5F", padding: "0 24px", height: 56, display: "flex", alignItems: "center", justifyContent: "space-between", position: "sticky", top: 0, zIndex: 100, boxShadow: "0 2px 8px rgba(0,0,0,0.15)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Bot size={20} color="#fff" />
          <span style={{ color: "#fff", fontWeight: 700, fontSize: 16 }}>BOTIQ</span>
          <span style={{ color: "rgba(255,255,255,0.4)", margin: "0 4px" }}>/</span>
          <span style={{ color: "rgba(255,255,255,0.7)", fontSize: 14 }}>Dashboard</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ color: "rgba(255,255,255,0.6)", fontSize: 13 }}>{user?.full_name}</span>
          <button onClick={() => nav("/chat")}
            style={{ background: "rgba(255,255,255,0.12)", border: "none", color: "#fff", padding: "6px 12px", borderRadius: 7, cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 5 }}>
            <MessageCircle size={13} /> Chat
          </button>
          <button onClick={logout} style={{ background: "none", border: "none", color: "rgba(255,255,255,0.6)", cursor: "pointer", padding: 4 }}>
            <LogOut size={17} />
          </button>
        </div>
      </nav>
      <Dashboard />
    </div>
  );
}
