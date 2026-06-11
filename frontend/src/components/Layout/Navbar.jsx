import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

const C = "#272163";

const ROLE_LABELS = {
  admin: { label: "Administrador", color: "#7c3aed" },
  support_engineer: { label: "Ing. Soporte", color: "#0284c7" },
  employee: { label: "Empleado", color: "#059669" },
};

export default function Navbar({ currentPage = "chat" }) {
  const { user, logout, isAdmin } = useAuth();
  const nav = useNavigate();
  const roleInfo = ROLE_LABELS[user?.role] || ROLE_LABELS.employee;

  const isDashboardArea = [
    "dashboard",
    "users",
    "faqs",
    "knowledge-base",
  ].includes(currentPage);

  return (
    <nav
      style={{
        background: C,
        minHeight: 56,
        padding: "0 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        boxShadow: "0 2px 12px rgba(39,33,99,0.2)",
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <button
          onClick={() => nav(isAdmin ? "/dashboard" : "/chat")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "transparent",
            border: "none",
            cursor: "pointer",
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              background: "rgba(255,255,255,0.15)",
              borderRadius: 8,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <svg width="18" height="18" viewBox="0 0 40 40" fill="none">
              <path
                d="M12 20 L20 12 L28 20 L20 28 Z"
                fill="rgba(255,255,255,0.3)"
                stroke="#fff"
                strokeWidth="2"
              />
              <circle cx="20" cy="20" r="4" fill="#fff" />
            </svg>
          </div>
          <span
            style={{
              color: "#fff",
              fontWeight: 700,
              fontSize: 16,
              letterSpacing: "-0.3px",
            }}
          >
            BOTIQ
          </span>
        </button>

        {isDashboardArea && (
          <>
            <span style={{ color: "rgba(255,255,255,0.3)" }}>/</span>
            <span style={{ color: "rgba(255,255,255,0.7)", fontSize: 13 }}>
              Administración
            </span>
          </>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        {isAdmin && (
          <>
            <NavBtn active={currentPage === "dashboard"} onClick={() => nav("/dashboard")}>
              📊 Dashboard
            </NavBtn>
            <NavBtn active={currentPage === "users"} onClick={() => nav("/dashboard/users")}>
              👥 Usuarios
            </NavBtn>
            <NavBtn active={currentPage === "faqs"} onClick={() => nav("/dashboard/faqs")}>
              ❓ FAQs
            </NavBtn>
            <NavBtn active={currentPage === "knowledge-base"} onClick={() => nav("/dashboard/knowledge-base")}>
              📚 Base
            </NavBtn>
          </>
        )}

        {currentPage !== "chat" && (
          <NavBtn onClick={() => nav("/chat")}>💬 Chat</NavBtn>
        )}

        <span
          style={{
            background: `${roleInfo.color}22`,
            color:
              roleInfo.color === "#7c3aed"
                ? "#c4b5fd"
                : roleInfo.color === "#0284c7"
                ? "#7dd3fc"
                : "#6ee7b7",
            fontSize: 11,
            padding: "3px 10px",
            borderRadius: 20,
            fontWeight: 500,
          }}
        >
          {roleInfo.label}
        </span>

        <span style={{ color: "rgba(255,255,255,0.7)", fontSize: 13 }}>
          {user?.full_name?.split(" ")[0]}
        </span>

        <button
          onClick={logout}
          title="Cerrar sesión"
          style={{
            background: "rgba(255,255,255,0.08)",
            border: "1px solid rgba(255,255,255,0.15)",
            color: "rgba(255,255,255,0.7)",
            width: 32,
            height: 32,
            borderRadius: 8,
            cursor: "pointer",
            fontSize: 15,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "background 0.2s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.16)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.08)")}
        >
          ⬡
        </button>
      </div>
    </nav>
  );
}

function NavBtn({ onClick, children, active = false }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? "rgba(255,255,255,0.26)" : "rgba(255,255,255,0.12)",
        border: "1px solid rgba(255,255,255,0.2)",
        color: "#fff",
        padding: "6px 12px",
        borderRadius: 7,
        cursor: "pointer",
        fontSize: 12,
        fontWeight: 500,
        display: "flex",
        alignItems: "center",
        gap: 5,
        transition: "background 0.2s",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.2)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = active ? "rgba(255,255,255,0.26)" : "rgba(255,255,255,0.12)")}
    >
      {children}
    </button>
  );
}
