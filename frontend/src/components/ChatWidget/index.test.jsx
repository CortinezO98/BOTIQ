import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  messages: [],
  startSession: vi.fn(),
  clearChat: vi.fn(),
  sendMessage: vi.fn(),
  submitFeedback: vi.fn(),
  submitSatisfaction: vi.fn(),
}));

vi.mock("../../hooks/useChat", () => ({
  useChat: () => ({
    messages: mocks.messages,
    loading: false,
    session: mocks.messages.length
      ? { selected_profile: "support_engineer" }
      : null,
    sessionStatus: mocks.messages.length ? "active" : "idle",
    startSession: mocks.startSession,
    sendMessage: mocks.sendMessage,
    clearChat: mocks.clearChat,
    submitFeedback: mocks.submitFeedback,
    submitSatisfaction: mocks.submitSatisfaction,
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
  mocks.messages = [];
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
    mocks.startSession.mockResolvedValueOnce({});

    render(<ChatWidget embedded />);

    fireEvent.click(
      screen.getByRole("button", { name: /empleado/i }),
    );

    await waitFor(() => {
      expect(mocks.startSession).toHaveBeenCalledWith({
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

  it("identifica una respuesta proveniente de la KB de servidores", () => {
    mocks.messages = [
      {
        id: "server-answer-1",
        role: "assistant",
        content: "LETO se encuentra en estado crítico.",
        meta: {
          module: "server_validation",
          answerSource: "servers_rag",
          sources: ["Inventario de servidores"],
        },
        ts: new Date(),
      },
    ];

    render(<ChatWidget embedded />);

    expect(screen.getByText("KB Servidores")).toBeInTheDocument();
    expect(screen.getByText(/Inventario de servidores/i)).toBeInTheDocument();
  });

  it("oculta el perfil de soporte cuando el portal solo permite empleados", () => {
    render(
      <ChatWidget
        embedded
        allowedProfiles={["employee"]}
      />,
    );

    expect(
      screen.getByRole("button", { name: /empleado/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Ing. Soporte"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText(/usuario de red/i),
    ).not.toBeInTheDocument();
  });

  it("notifica al portal cuando se solicita cerrar el iframe", () => {
    const onRequestClose = vi.fn();

    render(
      <ChatWidget
        embedded
        allowedProfiles={["employee"]}
        onRequestClose={onRequestClose}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: /cerrar chat/i }),
    );

    expect(onRequestClose).toHaveBeenCalledTimes(1);
  });

});
