import Dashboard from "../components/Dashboard";
import Navbar from "../components/Layout/Navbar";

export default function DashboardPage() {
  return (
    <div className="botiq-page-shell">
      <Navbar currentPage="dashboard" />
      <Dashboard />
    </div>
  );
}


