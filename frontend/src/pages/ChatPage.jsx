import ChatWidget from "../components/ChatWidget";
import { useAuth } from "../hooks/useAuth";
import { useNavigate } from "react-router-dom";
import { LogOut, LayoutDashboard, Bot, Settings } from "lucide-react";

export default function ChatPage() {
  const { user, logout, isAdmin, isSupport } = useAuth();
  const nav = useNavigate();

  return (
    <div style={{ minHeight: "100vh", background: "#F0F4F8" }}>
      {/* Navbar */}
      <nav style={{ background: "#1E3A5F", padding: "0 24px", height: 56, display: "flex", alignItems: "center", justifyContent: "space-between", boxShadow: "0 2px 8px rgba(0,0,0,0.15)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Bot size={20} color="#fff" />
          <span style={{ color: "#fff", fontWeight: 700, fontSize: 16, letterSpacing: "-0.3px" }}>BOTIQ</span>
          <span style={{ background: "rgba(255,255,255,0.15)", color: "rgba(255,255,255,0.8)", fontSize: 10, padding: "2px 8px", borderRadius: 20, fontWeight: 500 }}>
            {user?.role === "admin" ? "Admin" : user?.role === "support_engineer" ? "Soporte" : "Empleado"}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ color: "rgba(255,255,255,0.6)", fontSize: 13 }}>{user?.full_name}</span>
          {isAdmin && (
            <button onClick={() => nav("/dashboard")}
              style={{ background: "rgba(255,255,255,0.12)", border: "none", color: "#fff", padding: "6px 12px", borderRadius: 7, cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 5 }}>
              <LayoutDashboard size={13} /> Dashboard
            </button>
          )}
          <button onClick={logout} title="Cerrar sesión"
            style={{ background: "none", border: "none", color: "rgba(255,255,255,0.6)", cursor: "pointer", padding: 4, borderRadius: 4 }}>
            <LogOut size={17} />
          </button>
        </div>
      </nav>

      {/* Contenido principal */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "calc(100vh - 56px)", textAlign: "center", padding: 24 }}>
        <div style={{ width: 80, height: 80, background: "#1E3A5F", borderRadius: 24, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px", boxShadow: "0 8px 24px rgba(30,58,95,0.2)" }}>
          <Bot size={40} color="#fff" />
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: "#1E3A5F", marginBottom: 8 }}>
          ¡Bienvenido, {user?.full_name?.split(" ")[0]}!
        </h2>
        <p style={{ color: "#6B7280", fontSize: 14, maxWidth: 360, lineHeight: 1.6 }}>
          Haz clic en el botón azul en la esquina inferior derecha para abrir BOTIQ y comenzar.
        </p>

        {isSupport && (
          <div style={{ marginTop: 24, background: "#EFF6FF", border: "1px solid #BFDBFE", borderRadius: 10, padding: "12px 20px", maxWidth: 360 }}>
            <p style={{ fontSize: 12, color: "#1D4ED8", fontWeight: 500 }}>
              🔧 Modo Ingeniero de Soporte activo — Acceso a base de conocimiento RAG y validación de servidores.
            </p>
          </div>
        )}
      </div>

      {/* Widget flotante */}
      <ChatWidget primaryColor="#1E3A5F" position="bottom-right" />
    </div>
  );
}
