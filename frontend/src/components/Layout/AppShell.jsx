import Sidebar from "./Sidebar";
import { useSidebar } from "../../hooks/useSidebar";

/**
 * Reemplaza el patrón repetido en cada página:
 *   <div className="botiq-page botiq-admin-page">
 *     <Navbar currentPage="x" />
 *     <main className="botiq-page-main">...</main>
 *   </div>
 *
 * por:
 *   <AppShell currentPage="x">
 *     <main className="botiq-page-main">...</main>
 *   </AppShell>
 */
export default function AppShell({ currentPage, children }) {
  const { collapsed } = useSidebar();

  return (
    <div className="botiq-page botiq-admin-page">
      <Sidebar currentPage={currentPage} />
      <div className={`botiq-sidebar-content${collapsed ? " botiq-sidebar-content--collapsed" : ""}`}>
        {children}
      </div>
    </div>
  );
}
