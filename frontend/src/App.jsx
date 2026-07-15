import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import ChatWidget from "./components/ChatWidget";
import ChatPage from "./pages/ChatPage";
import ConversationLogsPage from "./pages/ConversationLogsPage";
import DashboardPage from "./pages/DashboardPage";
import FaqsPage from "./pages/FaqsPage";
import GovernancePage from "./pages/GovernancePage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";
import LoginPage from "./pages/LoginPage";
import ReportsPage from "./pages/ReportsPage";
import SecurityPage from "./pages/SecurityPage";
import UsersPage from "./pages/UsersPage";
import { AuthProvider, useAuth } from "./hooks/useAuth";

const C = "#272163";

function Guard({ children, adminOnly = false, showFloatingChat = true }) {
  const { user, checkingSession } = useAuth();

  if (checkingSession) {
    // Todavía no sabemos si hay sesión (esperando /auth/me). No redirigir
    // todavía: eso causaría un parpadeo a /login incluso con sesión válida.
    return null;
  }

  if (!user) return <Navigate to="/login" replace />;

  if (adminOnly && user.role !== "admin") {
    return <Navigate to="/chat" replace />;
  }

  return (
    <>
      {children}
      {showFloatingChat && <ChatWidget primaryColor={C} position="bottom-right" />}
    </>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route path="/chat" element={<Guard><ChatPage /></Guard>} />
      <Route path="/dashboard" element={<Guard adminOnly><DashboardPage /></Guard>} />
      <Route path="/dashboard/users" element={<Guard adminOnly><UsersPage /></Guard>} />
      <Route path="/dashboard/faqs" element={<Guard adminOnly><FaqsPage /></Guard>} />
      <Route path="/dashboard/knowledge-base" element={<Guard adminOnly><KnowledgeBasePage /></Guard>} />
      <Route path="/dashboard/conversation-logs" element={<Guard adminOnly><ConversationLogsPage /></Guard>} />
      <Route path="/dashboard/reports" element={<Guard adminOnly><ReportsPage /></Guard>} />
      <Route path="/dashboard/governance" element={<Guard adminOnly><GovernancePage /></Guard>} />
      <Route path="/dashboard/security" element={<Guard adminOnly showFloatingChat={false}><SecurityPage /></Guard>} />

      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
