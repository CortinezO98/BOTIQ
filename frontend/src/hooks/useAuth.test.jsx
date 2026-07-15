import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";

vi.mock("../services/api", () => ({
  authAPI: {
    me: vi.fn().mockRejectedValue(new Error("sin sesión")),
    login: vi.fn().mockResolvedValue({
      data: { user: { id: "1", email: "admin@iq-online.com", role: "admin", mfa_enabled: false } },
    }),
    logout: vi.fn(),
    mfaVerify: vi.fn(),
  },
}));

import { AuthProvider, useAuth } from "./useAuth";

// Dos consumidores distintos de useAuth(), ambos dentro del MISMO
// AuthProvider — simula la situación real: LoginPage llama a login(),
// Navbar (u otro componente hermano) también llama a useAuth() por su
// cuenta para leer `user`.
function LoginTrigger() {
  const { login } = useAuth();
  return (
    <button onClick={() => login("admin@iq-online.com", "pass")}>
      Entrar
    </button>
  );
}

function UserDisplay() {
  const { user } = useAuth();
  return <span data-testid="user-email">{user ? user.email : "sin sesión"}</span>;
}

describe("useAuth (Context compartido)", () => {
  it("login() en un componente se refleja de inmediato en OTRO componente que también usa useAuth()", async () => {
    render(
      <AuthProvider>
        <LoginTrigger />
        <UserDisplay />
      </AuthProvider>
    );

    // Al montar, syncUser() corre y falla (sin sesión) -> "sin sesión"
    await waitFor(() => {
      expect(screen.getByTestId("user-email").textContent).toBe("sin sesión");
    });

    await act(async () => {
      screen.getByText("Entrar").click();
    });

    // Bug real corregido: sin Context compartido, UserDisplay nunca se
    // enteraba de que LoginTrigger hizo login (cada uno tenía su propio
    // useState). Con Context, ambos leen el mismo estado.
    await waitFor(() => {
      expect(screen.getByTestId("user-email").textContent).toBe("admin@iq-online.com");
    });
  });

  it("useAuth() fuera de <AuthProvider> lanza un error explícito en vez de fallar en silencio", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<UserDisplay />)).toThrow(/AuthProvider/);
    consoleError.mockRestore();
  });
});
