import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  FileText,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  Menu,
  MessageCircle,
  Moon,
  ShieldCheck,
  Sun,
  Users,
  X,
} from "lucide-react";

import { useAuth } from "../../hooks/useAuth";
import { useSidebar } from "../../hooks/useSidebar";
import { useTheme } from "../../hooks/useTheme";
import BotiqBotIcon from "../Brand/BotiqBotIcon";
import BotiqLogo from "../Brand/BotiqLogo";

const ROLE_LABELS = {
  admin: { label: "Administrador", short: "ADM" },
  support_engineer: { label: "Ing. Soporte", short: "SOP" },
  employee: { label: "Empleado", short: "EMP" },
};

const NAV_GROUPS = [
  {
    label: "Principal",
    items: [
      { key: "dashboard", label: "Dashboard", icon: LayoutDashboard, path: "/dashboard", adminOnly: true },
      { key: "users", label: "Usuarios", icon: Users, path: "/dashboard/users", adminOnly: true },
      { key: "faqs", label: "FAQs", icon: CircleHelp, path: "/dashboard/faqs", adminOnly: true },
      { key: "knowledge-base", label: "Base de conocimiento", icon: BookOpen, path: "/dashboard/knowledge-base", adminOnly: true },
      { key: "conversation-logs", label: "Logs", icon: FileText, path: "/dashboard/conversation-logs", adminOnly: true },
    ],
  },
  {
    label: "Gestión",
    items: [
      { key: "reports", label: "Reportes", icon: BarChart3, path: "/dashboard/reports", adminOnly: true },
      { key: "governance", label: "Gobierno IA", icon: ShieldCheck, path: "/dashboard/governance", adminOnly: true },
      { key: "security", label: "Seguridad", icon: LockKeyhole, path: "/dashboard/security", adminOnly: true },
    ],
  },
  {
    label: "Asistente",
    items: [
      { key: "chat", label: "Chat", icon: MessageCircle, path: "/chat", adminOnly: false },
    ],
  },
];

export default function Sidebar({ currentPage = "chat" }) {
  const { user, logout, isAdmin } = useAuth();
  const {
    collapsed,
    toggleCollapsed,
    mobileOpen,
    toggleMobile,
    closeMobile,
  } = useSidebar();
  const { theme, toggleTheme } = useTheme();

  const navigate = useNavigate();
  const location = useLocation();
  const roleInfo = ROLE_LABELS[user?.role] || ROLE_LABELS.employee;

  useEffect(() => {
    closeMobile();
  }, [location.pathname, closeMobile]);

  const go = (path) => {
    closeMobile();
    navigate(path);
  };

  const visibleGroups = NAV_GROUPS
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !item.adminOnly || isAdmin),
    }))
    .filter((group) => group.items.length > 0);

  const firstName = user?.full_name?.trim()?.split(/\s+/)[0] || "Usuario";
  const initials = (user?.full_name || user?.email || "U")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  return (
    <>
      <button
        type="button"
        className="botiq-nav-mobile-toggle"
        onClick={toggleMobile}
        aria-label={mobileOpen ? "Cerrar menú principal" : "Abrir menú principal"}
        aria-expanded={mobileOpen}
        aria-controls="botiq-primary-sidebar"
      >
        {mobileOpen ? <X size={21} aria-hidden="true" /> : <Menu size={21} aria-hidden="true" />}
      </button>

      <button
        type="button"
        className={`botiq-sidebar-backdrop${mobileOpen ? " botiq-sidebar-backdrop--visible" : ""}`}
        onClick={closeMobile}
        aria-label="Cerrar menú lateral"
        tabIndex={mobileOpen ? 0 : -1}
      />

      <aside
        id="botiq-primary-sidebar"
        className={`botiq-sidebar${collapsed ? " botiq-sidebar--collapsed" : ""}${mobileOpen ? " botiq-sidebar--mobile-open" : ""}`}
        aria-label="Menú principal de BOTIQ"
      >
        <div className="botiq-sidebar__ambient" aria-hidden="true" />

        <header className="botiq-sidebar__header">
          <button
            type="button"
            className="botiq-sidebar__brand"
            onClick={() => go(isAdmin ? "/dashboard" : "/chat")}
            aria-label="Ir al inicio de BOTIQ"
          >
            {collapsed ? (
              <span className="botiq-sidebar__brand-icon">
                <BotiqBotIcon size={29} color="#272163" light />
              </span>
            ) : (
              <BotiqLogo variant="light" size="sm" showSubtitle={false} />
            )}
          </button>

          <button
            type="button"
            className="botiq-sidebar__collapse"
            onClick={toggleCollapsed}
            aria-label={collapsed ? "Expandir menú lateral" : "Colapsar menú lateral"}
            aria-expanded={!collapsed}
            title={collapsed ? "Expandir menú" : "Colapsar menú"}
          >
            {collapsed
              ? <ChevronRight size={19} aria-hidden="true" />
              : <ChevronLeft size={19} aria-hidden="true" />}
          </button>
        </header>

        {!collapsed && (
          <div className="botiq-sidebar__caption">
            <span className="botiq-sidebar__status-dot" />
            Plataforma operativa
          </div>
        )}

        <nav className="botiq-sidebar__navigation" aria-label="Navegación principal">
          {visibleGroups.map((group) => (
            <section className="botiq-sidebar__group" key={group.label}>
              {!collapsed && <p className="botiq-sidebar__group-label">{group.label}</p>}

              <div className="botiq-sidebar__items">
                {group.items.map((item) => (
                  <SidebarLink
                    key={item.key}
                    item={item}
                    active={currentPage === item.key}
                    collapsed={collapsed}
                    onClick={() => go(item.path)}
                  />
                ))}
              </div>
            </section>
          ))}
        </nav>

        <footer className="botiq-sidebar__footer">
          <div className={`botiq-sidebar__profile${collapsed ? " is-collapsed" : ""}`}>
            <div className="botiq-sidebar__avatar" aria-hidden="true">
              {initials || "U"}
            </div>

            {!collapsed && (
              <div className="botiq-sidebar__profile-copy">
                <strong title={user?.full_name || firstName}>{firstName}</strong>
                <span>{roleInfo.label}</span>
              </div>
            )}

            {!collapsed && (
              <span className="botiq-sidebar__role-chip">{roleInfo.short}</span>
            )}
          </div>

          <div className={`botiq-sidebar__actions${collapsed ? " is-collapsed" : ""}`}>
            <button
              type="button"
              className="botiq-sidebar__utility"
              onClick={toggleTheme}
              title={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
              aria-label={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
            >
              {theme === "dark"
                ? <Sun size={18} aria-hidden="true" />
                : <Moon size={18} aria-hidden="true" />}
              {!collapsed && <span>{theme === "dark" ? "Modo claro" : "Modo oscuro"}</span>}
            </button>

            <button
              type="button"
              className="botiq-sidebar__utility botiq-sidebar__utility--danger"
              onClick={logout}
              title="Cerrar sesión"
              aria-label="Cerrar sesión"
            >
              <LogOut size={18} aria-hidden="true" />
              {!collapsed && <span>Cerrar sesión</span>}
            </button>
          </div>
        </footer>
      </aside>
    </>
  );
}

function SidebarLink({ item, active, collapsed, onClick }) {
  const Icon = item.icon;

  return (
    <button
      type="button"
      className={`botiq-sidebar__link${active ? " is-active" : ""}`}
      onClick={onClick}
      title={collapsed ? item.label : undefined}
      aria-current={active ? "page" : undefined}
      data-tooltip={collapsed ? item.label : undefined}
    >
      <span className="botiq-sidebar__link-icon">
        <Icon size={19} strokeWidth={2.1} aria-hidden="true" />
      </span>
      {!collapsed && <span className="botiq-sidebar__link-label">{item.label}</span>}
      {active && <span className="botiq-sidebar__active-indicator" aria-hidden="true" />}
    </button>
  );
}
