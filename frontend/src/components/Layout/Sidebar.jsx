import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { useSidebar } from "../../hooks/useSidebar";
import { useTheme } from "../../hooks/useTheme";
import BotiqLogo from "../Brand/BotiqLogo";

const ROLE_LABELS = {
  admin: { label: "Administrador", color: "#7c3aed" },
  support_engineer: { label: "Ing. Soporte", color: "#0284c7" },
  employee: { label: "Empleado", color: "#059669" },
};

const NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", icon: "📊", path: "/dashboard", adminOnly: true },
  { key: "users", label: "Usuarios", icon: "👥", path: "/dashboard/users", adminOnly: true },
  { key: "faqs", label: "FAQs", icon: "❓", path: "/dashboard/faqs", adminOnly: true },
  { key: "knowledge-base", label: "Base", icon: "📚", path: "/dashboard/knowledge-base", adminOnly: true },
  { key: "conversation-logs", label: "Logs", icon: "🧾", path: "/dashboard/conversation-logs", adminOnly: true },
  { key: "reports", label: "Reportes", icon: "📈", path: "/dashboard/reports", adminOnly: true },
  { key: "governance", label: "Gobierno IA", icon: "🛡️", path: "/dashboard/governance", adminOnly: true },
  { key: "security", label: "Seguridad", icon: "🔒", path: "/dashboard/security", adminOnly: true },
  { key: "chat", label: "Chat", icon: "💬", path: "/chat", adminOnly: false },
];

export default function Sidebar({ currentPage = "chat" }) {
  const { user, logout, isAdmin } = useAuth();
  const { collapsed, toggleCollapsed, mobileOpen, toggleMobile, closeMobile } = useSidebar();
  const { theme, toggleTheme } = useTheme();
  const nav = useNavigate();
  const roleInfo = ROLE_LABELS[user?.role] || ROLE_LABELS.employee;

  const go = (path) => {
    closeMobile();
    nav(path);
  };

  const visibleItems = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin);

  return (
    <>
      <button
        className="botiq-nav-mobile-toggle"
        onClick={toggleMobile}
        aria-label="Abrir menú"
        style={{
          display: "none",
          position: "fixed",
          top: 14,
          left: 14,
          zIndex: 210,
          width: 40,
          height: 40,
          borderRadius: 10,
          background: "var(--botiq-primary)",
          border: "none",
          color: "#fff",
          fontSize: 18,
          cursor: "pointer",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        ☰
      </button>

      <div
        className={`botiq-sidebar-backdrop${mobileOpen ? " botiq-sidebar-backdrop--visible" : ""}`}
        onClick={closeMobile}
      />

      {/* Sin clases de animate.css a propósito: el sidebar no debe re-animar
          en cada cambio de página, solo el login sigue teniendo animación. */}
      <nav
        className={`botiq-sidebar${collapsed ? " botiq-sidebar--collapsed" : ""}${mobileOpen ? " botiq-sidebar--mobile-open" : ""}`}
      >
        <div style={{ padding: collapsed ? "18px 12px" : "18px 20px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <button
            onClick={() => go(isAdmin ? "/dashboard" : "/chat")}
            style={{ background: "transparent", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center", overflow: "hidden" }}
          >
            <BotiqLogo variant="light" size="sm" showSubtitle={false} />
          </button>
        </div>

        <button
          onClick={toggleCollapsed}
          title={collapsed ? "Expandir menú" : "Colapsar menú"}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: collapsed ? "center" : "flex-end",
            gap: 6,
            margin: "0 12px 10px",
            padding: "6px 10px",
            background: "rgba(255,255,255,0.08)",
            border: "1px solid rgba(255,255,255,0.14)",
            borderRadius: 8,
            color: "rgba(255,255,255,0.75)",
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          {collapsed ? "»" : "« Colapsar"}
        </button>

        <div style={{ flex: 1, overflowY: "auto", padding: "4px 10px", display: "flex", flexDirection: "column", gap: 4 }}>
          {visibleItems.map((item) => (
            <SidebarLink
              key={item.key}
              icon={item.icon}
              label={item.label}
              active={currentPage === item.key}
              collapsed={collapsed}
              onClick={() => go(item.path)}
            />
          ))}
        </div>

        <div style={{ padding: collapsed ? "10px" : "12px 16px 16px", borderTop: "1px solid rgba(255,255,255,0.12)" }}>
          <button
            onClick={toggleTheme}
            title={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              width: "100%",
              background: "rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.14)",
              borderRadius: 8,
              color: "#fff",
              cursor: "pointer",
              fontSize: 13,
              padding: "8px 10px",
              marginBottom: 8,
              justifyContent: collapsed ? "center" : "flex-start",
            }}
          >
            <span>{theme === "dark" ? "☀️" : "🌙"}</span>
            {!collapsed && <span>{theme === "dark" ? "Modo claro" : "Modo oscuro"}</span>}
          </button>

          {!collapsed && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span
                style={{
                  background: `${roleInfo.color}28`,
                  color: roleInfo.color === "#7c3aed" ? "#ddd6fe" : roleInfo.color === "#0284c7" ? "#bae6fd" : "#bbf7d0",
                  fontSize: 11,
                  padding: "3px 9px",
                  borderRadius: 999,
                  fontWeight: 700,
                  whiteSpace: "nowrap",
                }}
              >
                {roleInfo.label}
              </span>
              <span style={{ color: "rgba(255,255,255,0.8)", fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {user?.full_name?.split(" ")[0]}
              </span>
            </div>
          )}

          <button
            onClick={logout}
            title="Cerrar sesión"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              width: "100%",
              background: "rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.14)",
              borderRadius: 8,
              color: "#fff",
              cursor: "pointer",
              fontSize: 13,
              padding: "8px 10px",
              justifyContent: collapsed ? "center" : "flex-start",
            }}
          >
            <span>⎋</span>
            {!collapsed && <span>Cerrar sesión</span>}
          </button>
        </div>
      </nav>
    </>
  );
}

function SidebarLink({ icon, label, active, collapsed, onClick }) {
  return (
    <button
      onClick={onClick}
      title={collapsed ? label : undefined}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        justifyContent: collapsed ? "center" : "flex-start",
        padding: collapsed ? "10px 0" : "10px 12px",
        borderRadius: 9,
        border: "none",
        background: active ? "rgba(255,255,255,0.18)" : "transparent",
        color: "#fff",
        cursor: "pointer",
        fontSize: 13,
        fontWeight: active ? 700 : 550,
        width: "100%",
        textAlign: "left",
      }}
    >
      <span style={{ fontSize: 16, flexShrink: 0 }}>{icon}</span>
      {!collapsed && <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>}
    </button>
  );
}
