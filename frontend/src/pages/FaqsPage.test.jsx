import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../services/api", () => ({
  faqAPI: {
    list: vi.fn().mockResolvedValue({
      data: [
        {
          id: "faq-1",
          question: "¿Cómo cambio mi contraseña?",
          answer: "Ingresa al portal de seguridad y selecciona cambiar contraseña.",
          category: "Accesos",
          tags: ["contraseña", "seguridad"],
          hit_count: 18,
        },
      ],
    }),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
  adminAPI: {
    listWebKnowledge: vi.fn().mockResolvedValue({
      data: [
        {
          id: "suggestion-1",
          question: "¿Cómo limpiar la caché del navegador?",
          answer: "Abre la configuración del navegador y elimina los datos almacenados.",
          category: "Navegadores",
          tags: ["caché"],
          status: "pending",
          usage_count: 2,
          confidence: 0.87,
          sources: [],
        },
      ],
    }),
    approveWebKnowledge: vi.fn(),
    rejectWebKnowledge: vi.fn(),
  },
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

import FaqsPage from "./FaqsPage";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("FaqsPage profesional", () => {
  it("renderiza métricas y FAQs oficiales", async () => {
    render(
      <MemoryRouter>
        <FaqsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("¿Cómo cambio mi contraseña?")).toBeInTheDocument();
    });

    expect(screen.getByText("FAQs activas")).toBeInTheDocument();
    expect(screen.getByText("Categorías")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/buscar pregunta/i)).toBeInTheDocument();
  });

  it("cambia a sugerencias web", async () => {
    render(
      <MemoryRouter>
        <FaqsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("¿Cómo cambio mi contraseña?")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /sugerencias web/i }));

    await waitFor(() => {
      expect(
        screen.getByText("¿Cómo limpiar la caché del navegador?"),
      ).toBeInTheDocument();
    });
  });

  it("abre el modal para crear una FAQ", async () => {
    render(
      <MemoryRouter>
        <FaqsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("¿Cómo cambio mi contraseña?")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /nueva faq/i }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Crear nueva FAQ")).toBeInTheDocument();
  });

  it("filtra las FAQs por texto", async () => {
    render(
      <MemoryRouter>
        <FaqsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("¿Cómo cambio mi contraseña?")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/buscar pregunta/i), {
      target: { value: "sin coincidencia" },
    });

    expect(screen.getByText("No encontramos coincidencias")).toBeInTheDocument();
  });
});
