import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../services/api", () => ({
  adminAPI: {
    listUsers: vi.fn().mockResolvedValue({
      data: [
        {
          id: "1",
          full_name: "Ana Torres",
          email: "ana@iq-online.com",
          role: "employee",
          is_active: true,
          mfa_enabled: false,
          created_at: "2026-07-15T10:00:00Z",
        },
        {
          id: "2",
          full_name: "Carlos Rojas",
          email: "carlos@iq-online.com",
          role: "admin",
          is_active: false,
          mfa_enabled: true,
          created_at: "2026-07-14T10:00:00Z",
        },
      ],
    }),
    createUser: vi.fn(),
    updateUser: vi.fn(),
    changeRole: vi.fn(),
    disableUser: vi.fn(),
    enableUser: vi.fn(),
  },
  downloadCsvFromRows: vi.fn(),
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

import UsersPage from "./UsersPage";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("UsersPage profesional", () => {
  it("renderiza métricas, filtros, tabla y tarjetas móviles", async () => {
    render(<MemoryRouter><UsersPage /></MemoryRouter>);

    await waitFor(() => {
      expect(screen.getAllByText("Ana Torres").length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText("Usuarios totales")).toBeInTheDocument();
    expect(screen.getAllByText("MFA activo").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByPlaceholderText("Buscar por nombre o correo...")).toBeInTheDocument();
    expect(screen.getAllByText("Carlos Rojas").length).toBeGreaterThanOrEqual(1);
  });

  it("filtra usuarios por búsqueda", async () => {
    render(<MemoryRouter><UsersPage /></MemoryRouter>);

    await waitFor(() => {
      expect(screen.getAllByText("Ana Torres").length).toBeGreaterThanOrEqual(1);
    });

    fireEvent.change(
      screen.getByPlaceholderText("Buscar por nombre o correo..."),
      { target: { value: "carlos" } },
    );

    expect(screen.queryAllByText("Ana Torres")).toHaveLength(0);
    expect(screen.getAllByText("Carlos Rojas").length).toBeGreaterThanOrEqual(1);
  });

  it("abre el modal de creación", async () => {
    render(<MemoryRouter><UsersPage /></MemoryRouter>);

    await waitFor(() => {
      expect(screen.getAllByText("Ana Torres").length).toBeGreaterThanOrEqual(1);
    });

    fireEvent.click(screen.getByRole("button", { name: /nuevo usuario/i }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Crear nuevo usuario")).toBeInTheDocument();
  });
});
