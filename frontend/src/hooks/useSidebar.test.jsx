import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { SidebarProvider, useSidebar } from "./useSidebar";

function SidebarConsumer() {
  const { collapsed, toggleCollapsed, mobileOpen, toggleMobile } = useSidebar();
  return (
    <div>
      <span data-testid="collapsed-value">{String(collapsed)}</span>
      <span data-testid="mobile-value">{String(mobileOpen)}</span>
      <button onClick={toggleCollapsed}>Colapsar</button>
      <button onClick={toggleMobile}>Abrir mobile</button>
    </div>
  );
}

describe("SidebarProvider / useSidebar", () => {
  afterEach(() => {
    cleanup();
    localStorage.removeItem("botiq_sidebar_collapsed");
  });

  it("arranca expandido (collapsed=false) por defecto", () => {
    render(
      <SidebarProvider>
        <SidebarConsumer />
      </SidebarProvider>
    );
    expect(screen.getByTestId("collapsed-value").textContent).toBe("false");
  });

  it("toggleCollapsed() cambia el estado y persiste en localStorage", () => {
    render(
      <SidebarProvider>
        <SidebarConsumer />
      </SidebarProvider>
    );

    fireEvent.click(screen.getByText("Colapsar"));

    expect(screen.getByTestId("collapsed-value").textContent).toBe("true");
    expect(localStorage.getItem("botiq_sidebar_collapsed")).toBe("true");
  });

  it("respeta el estado colapsado guardado en localStorage al montar de nuevo", () => {
    localStorage.setItem("botiq_sidebar_collapsed", "true");

    render(
      <SidebarProvider>
        <SidebarConsumer />
      </SidebarProvider>
    );

    expect(screen.getByTestId("collapsed-value").textContent).toBe("true");
  });

  it("toggleMobile() abre/cierra el drawer mobile de forma independiente del colapso", () => {
    render(
      <SidebarProvider>
        <SidebarConsumer />
      </SidebarProvider>
    );

    fireEvent.click(screen.getByText("Abrir mobile"));
    expect(screen.getByTestId("mobile-value").textContent).toBe("true");
    expect(screen.getByTestId("collapsed-value").textContent).toBe("false");
  });

  it("useSidebar() fuera de <SidebarProvider> lanza un error explícito", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<SidebarConsumer />)).toThrow(/SidebarProvider/);
    consoleError.mockRestore();
  });
});
