import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../services/api", () => ({
  chatAPI: {
    adminConversationLogs: vi.fn().mockResolvedValue({
      data: [
        {
          id: "conversation-1",
          user_full_name: "Ana Torres",
          user_email: "ana@iq-online.com",
          selected_profile: "employee",
          session_status: "ended",
          question_count: 4,
          last_message: "Necesito ayuda con mi contraseña",
          detected_url: "https://portal.empresa.com",
          detected_ip: null,
          ticket_eligible: false,
          escalated_to_aranda: false,
          aranda_ticket_id: null,
          created_at: "2026-07-15T10:00:00Z",
          ended_at: "2026-07-15T10:10:00Z",
        },
        {
          id: "conversation-2",
          user_full_name: "Carlos Rojas",
          user_email: "carlos@iq-online.com",
          selected_profile: "support_engineer",
          session_status: "blocked",
          question_count: 2,
          last_message: "Consulta fuera del alcance",
          detected_url: null,
          detected_ip: "10.0.0.10",
          ticket_eligible: true,
          escalated_to_aranda: true,
          aranda_ticket_id: "AR-12345",
          created_at: "2026-07-15T11:00:00Z",
          ended_at: "2026-07-15T11:05:00Z",
        },
      ],
    }),
    adminConversationMessages: vi.fn().mockResolvedValue({
      data: [
        {
          id: "message-1",
          role: "user",
          content: "Necesito ayuda con mi contraseña",
          created_at: "2026-07-15T10:00:00Z",
        },
        {
          id: "message-2",
          role: "assistant",
          content: "Te explico cómo restablecerla.",
          created_at: "2026-07-15T10:01:00Z",
          tokens_used: 120,
        },
      ],
    }),
    adminConversationLogsExport: vi.fn().mockResolvedValue({
      data: new Blob(["id,user"], { type: "text/csv" }),
    }),
  },
  downloadBlob: vi.fn(),
}));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    user: { role: "admin", full_name: "Admin BOTIQ" },
    logout: vi.fn(),
    isAdmin: true,
  }),
}));

vi.mock("../hooks/useTheme", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: vi.fn() }),
}));

vi.mock("../hooks/useSidebar", () => ({
  useSidebar: () => ({
    collapsed: false,
    toggleCollapsed: vi.fn(),
    mobileOpen: false,
    toggleMobile: vi.fn(),
    closeMobile: vi.fn(),
  }),
}));

import ConversationLogsPage from "./ConversationLogsPage";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ConversationLogsPage profesional", () => {
  it("renderiza métricas y conversaciones", async () => {
    render(
      <MemoryRouter>
        <ConversationLogsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Ana Torres").length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText("Conversaciones")).toBeInTheDocument();
    expect(screen.getByText("Escaladas a Aranda")).toBeInTheDocument();
    expect(screen.getAllByText("Carlos Rojas").length).toBeGreaterThanOrEqual(1);
  });

  it("abre el detalle de una conversación", async () => {
    render(
      <MemoryRouter>
        <ConversationLogsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Ana Torres").length).toBeGreaterThanOrEqual(1);
    });

    fireEvent.click(
      screen.getAllByRole("button", { name: /ver conversación de ana torres/i })[0],
    );

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    expect(screen.getByText("Conversación completa")).toBeInTheDocument();
    expect(
      screen.getByText("Te explico cómo restablecerla."),
    ).toBeInTheDocument();
  });

  it("permite buscar y aplicar filtros", async () => {
    render(
      <MemoryRouter>
        <ConversationLogsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Ana Torres").length).toBeGreaterThanOrEqual(1);
    });

    fireEvent.change(screen.getByLabelText("Buscar logs"), {
      target: { value: "Ana" },
    });

    const applyButton = await screen.findByRole("button", {
      name: /aplicar filtros/i,
    });

    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(screen.getByLabelText("Buscar logs")).toHaveValue("Ana");
    });
  });
});
