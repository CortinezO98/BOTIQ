import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import LoginPage from "./pages/LoginPage";
import ChatPage from "./pages/ChatPage";
import DashboardPage from "./pages/DashboardPage";
import UsersPage from "./pages/UsersPage";
import FaqsPage from "./pages/FaqsPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";

function getUser() {
  try {
    return JSON.parse(localStorage.getItem("botiq_user"));
  } catch {
    return null;
  }
}

function Guard({ children, adminOnly = false }) {
  const user = getUser();

  if (!user) return <Navigate to="/login" replace />;

  if (adminOnly && user.role !== "admin") {
    return <Navigate to="/chat" replace />;
  }

  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route
          path="/chat"
          element={
            <Guard>
              <ChatPage />
            </Guard>
          }
        />

        <Route
          path="/dashboard"
          element={
            <Guard adminOnly>
              <DashboardPage />
            </Guard>
          }
        />

        <Route
          path="/dashboard/users"
          element={
            <Guard adminOnly>
              <UsersPage />
            </Guard>
          }
        />

        <Route
          path="/dashboard/faqs"
          element={
            <Guard adminOnly>
              <FaqsPage />
            </Guard>
          }
        />

        <Route
          path="/dashboard/knowledge-base"
          element={
            <Guard adminOnly>
              <KnowledgeBasePage />
            </Guard>
          }
        />

        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
