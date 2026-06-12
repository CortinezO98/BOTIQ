import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import BotiqLogo from "../Brand/BotiqLogo";

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
        background: `linear-gradient(135deg, ${C}, #3a3490)`,
        minHeight: 58,
        padding: "0 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        boxShadow: "0 2px 14px rgba(39,33,99,0.22)",
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <button
          onClick={() => nav(isAdmin ? "/dashboard" : "/chat")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "transparent",
            border: "none",
            cursor: "pointer",
            padding: 0,
          }}
        >
          <BotiqLogo variant="light" size="sm" />
        </button>

        {isDashboardArea && (
          <>
            <span style={{ color: "rgba(255,255,255,0.32)" }}>/</span>
            <span style={{ color: "rgba(255,255,255,0.72)", fontSize: 13 }}>
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
            background: `${roleInfo.color}28`,
            color:
              roleInfo.color === "#7c3aed"
                ? "#ddd6fe"
                : roleInfo.color === "#0284c7"
                ? "#bae6fd"
                : "#bbf7d0",
            fontSize: 11,
            padding: "4px 10px",
            borderRadius: 999,
            fontWeight: 700,
            border: "1px solid rgba(255,255,255,0.12)",
          }}
        >
          {roleInfo.label}
        </span>

        <span style={{ color: "rgba(255,255,255,0.74)", fontSize: 13 }}>
          {user?.full_name?.split(" ")[0]}
        </span>

        <button
          onClick={logout}
          title="Cerrar sesión"
          style={{
            background: "rgba(255,255,255,0.09)",
            border: "1px solid rgba(255,255,255,0.16)",
            color: "rgba(255,255,255,0.78)",
            width: 32,
            height: 32,
            borderRadius: 9,
            cursor: "pointer",
            fontSize: 15,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "background 0.2s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.18)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.09)")}
        >
          ⎋
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
        border: "1px solid rgba(255,255,255,0.18)",
        color: "#fff",
        padding: "7px 12px",
        borderRadius: 8,
        cursor: "pointer",
        fontSize: 12,
        fontWeight: 650,
        display: "flex",
        alignItems: "center",
        gap: 5,
        transition: "background 0.2s, transform 0.2s",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "rgba(255,255,255,0.2)";
        e.currentTarget.style.transform = "translateY(-1px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = active
          ? "rgba(255,255,255,0.26)"
          : "rgba(255,255,255,0.12)";
        e.currentTarget.style.transform = "translateY(0)";
      }}
    >
      {children}
    </button>
  );
}
