import Dashboard from "../components/Dashboard";
import Navbar from "../components/Layout/Navbar";

export default function DashboardPage() {
  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar currentPage="dashboard" />
      <Dashboard />
    </div>
  );
}
