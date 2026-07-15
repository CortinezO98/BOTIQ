import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../services/api", () => ({
  adminAPI: {
    feedbackSummary: vi.fn().mockResolvedValue({
      data: {
        feedback: { total_up: 12, total_down: 3, approval_rate: 80 },
        satisfaction: { total_surveys: 8, avg_score: 4.4, resolved_by_bot: 6, resolution_rate: 75 },
        worst_rated_messages: [{ message_id: "abc-123", total_down: 2 }],
      },
    }),
    listIncidentAlerts: vi.fn().mockResolvedValue({
      data: [{
        id: "1",
        application_name: "Portal RRHH",
        app_or_url: "https://rrhh.iq-online.com",
        category: "availability",
        severity: "high",
        affected_users_count: 5,
        status: "open",
        recommendation: "Escalar a infraestructura.",
        first_seen_at: "2026-07-15T10:00:00Z",
        last_seen_at: "2026-07-15T10:20:00Z",
      }],
    }),
    listAiKnowledge: vi.fn().mockResolvedValue({
      data: [{
        id: "2",
        question: "¿Cómo limpio el caché de Chrome?",
        answer: "Ve a Configuración > Privacidad.",
        confidence: 0.62,
        status: "pending",
        usage_count: 3,
        created_at: "2026-07-15T09:00:00Z",
      }],
    }),
    acknowledgeIncident: vi.fn().mockResolvedValue({ data: {} }),
    resolveIncident: vi.fn().mockResolvedValue({ data: {} }),
    approveAiKnowledge: vi.fn().mockResolvedValue({ data: {} }),
    rejectAiKnowledge: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

vi.mock("../hooks/useAuth", () => ({ useAuth: () => ({ user: { role: "admin" }, logout: vi.fn(), isAdmin: true }) }));
vi.mock("../hooks/useTheme", () => ({ useTheme: () => ({ theme: "light", toggleTheme: vi.fn() }) }));
vi.mock("../hooks/useSidebar", () => ({ useSidebar: () => ({ collapsed: false, toggleCollapsed: vi.fn(), mobileOpen: false, toggleMobile: vi.fn(), closeMobile: vi.fn() }) }));

import { adminAPI } from "../services/api";
import GovernancePage from "./GovernancePage";

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("GovernancePage profesional", () => {
  it("muestra indicadores, incidentes y conocimiento IA", async () => {
    render(<MemoryRouter><GovernancePage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("Portal RRHH")).toBeInTheDocument());
    expect(screen.getByText("¿Cómo limpio el caché de Chrome?")).toBeInTheDocument();
    expect(screen.getAllByText("80%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Madurez de gobierno")).toBeInTheDocument();
  });

  it("reconoce un incidente con confirmación", async () => {
    render(<MemoryRouter><GovernancePage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("Portal RRHH")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /reconocer/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirmar acción/i }));
    await waitFor(() => expect(adminAPI.acknowledgeIncident).toHaveBeenCalledWith("1", ""));
  });

  it("aprueba conocimiento generado por IA", async () => {
    render(<MemoryRouter><GovernancePage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("¿Cómo limpio el caché de Chrome?")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /aprobar como faq/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirmar acción/i }));
    await waitFor(() => expect(adminAPI.approveAiKnowledge).toHaveBeenCalledWith("2"));
  });
});
