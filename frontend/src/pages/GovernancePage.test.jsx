import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../services/api", () => ({
  adminAPI: {
    feedbackSummary: vi.fn().mockResolvedValue({
      data: {
        feedback: { total_up: 12, total_down: 3, approval_rate: 80 },
        satisfaction: { total_surveys: 8, avg_score: 1.4, resolved_by_bot: 6, resolution_rate: 75 },
        worst_rated_messages: [{ message_id: "abc-123", total_down: 2 }],
      },
    }),
    listIncidentAlerts: vi.fn().mockResolvedValue({
      data: [
        {
          id: "1",
          application_name: "Portal RRHH",
          app_or_url: "https://rrhh.iq-online.com",
          severity: "high",
          affected_users_count: 5,
          status: "open",
          recommendation: "Escalar a infraestructura.",
          first_seen_at: "2026-07-15T10:00:00Z",
          last_seen_at: "2026-07-15T10:20:00Z",
        },
      ],
    }),
    listAiKnowledge: vi.fn().mockResolvedValue({
      data: [
        {
          id: "2",
          question: "¿Cómo limpio el caché de Chrome?",
          answer: "Andá a Configuración > Privacidad...",
          confidence: 0.62,
          status: "pending",
          usage_count: 3,
          created_at: "2026-07-15T09:00:00Z",
        },
      ],
    }),
  },
}));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({ user: { role: "admin" }, logout: vi.fn(), isAdmin: true }),
}));

import GovernancePage from "./GovernancePage";

describe("GovernancePage", () => {
  it("se monta sin errores y muestra los datos cargados", async () => {
    expect(() => render(<MemoryRouter><GovernancePage /></MemoryRouter>)).not.toThrow();

    await waitFor(() => {
      expect(screen.getByText("Portal RRHH")).toBeInTheDocument();
    });

    expect(screen.getByText(/¿Cómo limpio el caché de Chrome\?/)).toBeInTheDocument();
    expect(screen.getByText(/80%/)).toBeInTheDocument();
  });
});
