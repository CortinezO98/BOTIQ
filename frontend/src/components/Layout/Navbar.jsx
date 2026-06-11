import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

const C = "#272163";

const ROLE_LABELS = {
  admin: { label: "Administrador", color: "#7c3aed" },
  support_engineer: { label: "Ing. Soporte", color: "#0284c7" },
  employee: { label: "Empleado", color: "#059669" },
};

export default function Navbar({ currentPage = "chat" }) {
  const { user, logout, isAdmin, isSupport } = useAuth();
  const nav = useNavigate();
  const roleInfo = ROLE_LABELS[user?.role] || ROLE_LABELS.employee;

  return (
    <nav style={{
      background: C,
      height: 56, padding: "0 24px",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      boxShadow: "0 2px 12px rgba(39,33,99,0.2)",
      position: "sticky", top: 0, zIndex: 100,
    }}>
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{
          width: 32, height: 32, background: "rgba(255,255,255,0.15)",
          borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <svg width="18" height="18" viewBox="0 0 40 40" fill="none">
            <path d="M12 20 L20 12 L28 20 L20 28 Z" fill="rgba(255,255,255,0.3)" stroke="#fff" strokeWidth="2"/>
            <circle cx="20" cy="20" r="4" fill="#fff"/>
          </svg>
        </div>
        <span style={{ color: "#fff", fontWeight: 700, fontSize: 16, letterSpacing: "-0.3px" }}>BOTIQ</span>
        {currentPage === "dashboard" && (
          <>
            <span style={{ color: "rgba(255,255,255,0.3)", margin: "0 2px" }}>/</span>
            <span style={{ color: "rgba(255,255,255,0.7)", fontSize: 13 }}>Dashboard</span>
          </>
        )}
      </div>

      {/* Right */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {/* Badge de rol */}
        <span style={{
          background: `${roleInfo.color}22`,
          color: roleInfo.color === "#7c3aed" ? "#c4b5fd" :
                 roleInfo.color === "#0284c7" ? "#7dd3fc" : "#6ee7b7",
          fontSize: 11, padding: "3px 10px", borderRadius: 20, fontWeight: 500,
        }}>
          {roleInfo.label}
        </span>

        {/* Nombre */}
        <span style={{ color: "rgba(255,255,255,0.7)", fontSize: 13 }}>
          {user?.full_name?.split(" ")[0]}
        </span>

        {/* Botones de nav */}
        {isAdmin && currentPage !== "dashboard" && (
          <NavBtn onClick={() => nav("/dashboard")}>
            📊 Dashboard
          </NavBtn>
        )}
        {currentPage === "dashboard" && (
          <NavBtn onClick={() => nav("/chat")}>
            💬 Chat
          </NavBtn>
        )}

        {/* Logout */}
        <button onClick={logout} title="Cerrar sesión" style={{
          background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)",
          color: "rgba(255,255,255,0.7)", width: 32, height: 32,
          borderRadius: 8, cursor: "pointer", fontSize: 15,
          display: "flex", alignItems: "center", justifyContent: "center",
          transition: "background 0.2s",
        }}
          onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.16)"}
          onMouseLeave={e => e.currentTarget.style.background = "rgba(255,255,255,0.08)"}
        >
          ⬡
        </button>
      </div>
    </nav>
  );
}

function NavBtn({ onClick, children }) {
  return (
    <button onClick={onClick} style={{
      background: "rgba(255,255,255,0.12)", border: "1px solid rgba(255,255,255,0.2)",
      color: "#fff", padding: "6px 12px", borderRadius: 7, cursor: "pointer",
      fontSize: 12, fontWeight: 500, display: "flex", alignItems: "center", gap: 5,
      transition: "background 0.2s",
    }}
      onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.2)"}
      onMouseLeave={e => e.currentTarget.style.background = "rgba(255,255,255,0.12)"}
    >
      {children}
    </button>
  );
}
