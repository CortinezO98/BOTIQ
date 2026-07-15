import Sidebar from "./Sidebar";
import { useSidebar } from "../../hooks/useSidebar";

/**
 * Contenedor único para todas las vistas autenticadas.
 * Mantiene la funcionalidad existente y centraliza la relación entre
 * sidebar, contenido, modo colapsado y drawer móvil.
 */
export default function AppShell({ currentPage, children }) {
  const { collapsed } = useSidebar();

  return (
    <div
      className="botiq-page botiq-admin-page botiq-app-shell"
      data-sidebar-collapsed={collapsed ? "true" : "false"}
    >
      <Sidebar currentPage={currentPage} />

      <div
        className={`botiq-sidebar-content${collapsed ? " botiq-sidebar-content--collapsed" : ""}`}
      >
        <div className="botiq-app-shell__surface">
          {children}
        </div>
      </div>
    </div>
  );
}
