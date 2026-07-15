import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import { ThemeProvider, useTheme } from "./useTheme";

function ThemeConsumer() {
  const { theme, toggleTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme-value">{theme}</span>
      <button onClick={toggleTheme}>Cambiar tema</button>
    </div>
  );
}

describe("ThemeProvider / useTheme", () => {
  afterEach(() => {
    cleanup();
    localStorage.removeItem("botiq_theme");
    document.documentElement.removeAttribute("data-theme");
  });

  it("arranca en 'light' por defecto (sin preferencia guardada ni del sistema) y setea data-theme en <html>", async () => {
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );

    expect(screen.getByTestId("theme-value").textContent).toBe("light");
    await waitFor(() => {
      expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    });
  });

  it("toggleTheme() cambia a 'dark', actualiza <html> y persiste en localStorage", async () => {
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );

    screen.getByText("Cambiar tema").click();

    await waitFor(() => {
      expect(screen.getByTestId("theme-value").textContent).toBe("dark");
    });
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("botiq_theme")).toBe("dark");
  });

  it("respeta el tema guardado en localStorage al montar de nuevo", async () => {
    localStorage.setItem("botiq_theme", "dark");

    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );

    expect(screen.getByTestId("theme-value").textContent).toBe("dark");
  });

  it("useTheme() fuera de <ThemeProvider> lanza un error explícito", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<ThemeConsumer />)).toThrow(/ThemeProvider/);
    consoleError.mockRestore();
  });
});
