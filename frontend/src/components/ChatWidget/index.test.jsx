import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const startSession = vi.fn();
const clearChat = vi.fn();
const sendMessage = vi.fn();
const submitFeedback = vi.fn();
const submitSatisfaction = vi.fn();

vi.mock("../../hooks/useChat", () => ({
  useChat: () => ({
    messages: [],
    loading: false,
    session: null,
    sessionStatus: "idle",
    startSession,
    sendMessage,
    clearChat,
    submitFeedback,
    submitSatisfaction,
  }),
}));

vi.mock("../../services/api", () => ({
  supportAPI: {
    status: vi.fn().mockResolvedValue({
      data: { drive_configured: true },
    }),
  },
  healthAPI: {
    check: vi.fn().mockResolvedValue({
      data: { ai_available: true },
    }),
  },
}));

import ChatWidget from "./index";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ChatWidget mejorado", () => {
  it("se monta sin errores", () => {
    expect(() => render(<ChatWidget embedded />)).not.toThrow();
  });

  it("muestra los perfiles iniciales", () => {
    render(<ChatWidget embedded />);

    expect(screen.getAllByText("Empleado")).toHaveLength(1);
    expect(screen.getAllByText("Ing. Soporte")).toHaveLength(1);
    expect(
      screen.getByRole("button", {
        name: /validar e iniciar como soporte/i,
      }),
    ).toBeInTheDocument();
  });

  it("inicia una sesión de empleado", async () => {
    startSession.mockResolvedValueOnce({});

    render(<ChatWidget embedded />);

    fireEvent.click(
      screen.getByRole("button", { name: /empleado/i }),
    );

    await waitFor(() => {
      expect(startSession).toHaveBeenCalledWith({
        selected_profile: "employee",
        network_username: undefined,
      });
    });
  });

  it("valida que soporte tenga usuario de red", async () => {
    render(<ChatWidget embedded />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /validar e iniciar como soporte/i,
      }),
    );

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent(/ingresa tu usuario de red/i);
  });

  it("muestra el badge de modo degradado", async () => {
    const api = await import("../../services/api");
    api.healthAPI.check.mockResolvedValueOnce({
      data: { ai_available: false },
    });

    render(<ChatWidget embedded />);

    expect(
      await screen.findByText(/modo degradado/i),
    ).toBeInTheDocument();
  });

  it("abre el widget flotante", () => {
    render(<ChatWidget />);

    fireEvent.click(
      screen.getByRole("button", { name: /abrir botiq/i }),
    );

    expect(screen.getByText("Antes de iniciar")).toBeInTheDocument();
  });
});
