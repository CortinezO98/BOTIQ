import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const syncUser = vi.fn();

const authState = {
  user: {
    id: "admin-1",
    email: "admin@empresa.com",
    role: "admin",
    is_active: true,
    mfa_enabled: false,
  },
};

vi.mock("../services/api", () => ({
  authAPI: {
    mfaSetup: vi.fn().mockResolvedValue({
      data: {
        secret: "JBSWY3DPEHPK3PXP",
        otpauth_uri: "otpauth://totp/BOTIQ",
        qr_code_base64: "ZmFrZS1xci1pbWFnZQ==",
      },
    }),
    mfaConfirm: vi.fn().mockResolvedValue({ data: { success: true } }),
    mfaDisable: vi.fn().mockResolvedValue({ data: { success: true } }),
  },
}));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    user: authState.user,
    syncUser,
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

import { authAPI } from "../services/api";
import SecurityPage from "./SecurityPage";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  authState.user.mfa_enabled = false;
});

describe("SecurityPage profesional", () => {
  it("muestra el estado de MFA inactivo", () => {
    render(
      <MemoryRouter>
        <SecurityPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("Verificación en dos pasos")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /activar mfa/i })).toBeInTheDocument();
    expect(screen.getByText("MFA pendiente")).toBeInTheDocument();
  });

  it("inicia y confirma el enrolamiento MFA", async () => {
    render(
      <MemoryRouter>
        <SecurityPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /activar mfa/i }));

    await waitFor(() => {
      expect(screen.getByAltText(/código qr para configurar mfa/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Código de verificación"), {
      target: { value: "123456" },
    });

    fireEvent.click(
      screen.getByRole("button", { name: /confirmar y activar/i }),
    );

    await waitFor(() => {
      expect(authAPI.mfaConfirm).toHaveBeenCalledWith("123456");
      expect(syncUser).toHaveBeenCalled();
    });
  });

  it("permite abrir el formulario de desactivación", () => {
    authState.user.mfa_enabled = true;

    render(
      <MemoryRouter>
        <SecurityPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /desactivar mfa/i }));

    expect(
      screen.getByText("Confirmar desactivación de MFA"),
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Ingresa tu contraseña")).toBeInTheDocument();
  });
});
