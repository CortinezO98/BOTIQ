import Dashboard from "../components/Dashboard";
import AppShell from "../components/Layout/AppShell";

export default function DashboardPage() {
  return (
    <AppShell currentPage="dashboard">
      <Dashboard />
    </AppShell>
  );
}
