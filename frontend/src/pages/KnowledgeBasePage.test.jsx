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
  supportAPI: {
    status: vi.fn().mockResolvedValue({
      data: {
        status: "active",
        total_chunks: 28,
        drive_configured: true,
        drive_folder_count: 2,
        drive_folder_ids: ["folder-1", "folder-2"],
      },
    }),
    documents: vi.fn().mockResolvedValue({
      data: {
        summary: {
          total: 2,
          indexed: 1,
          failed: 1,
          total_chunks: 28,
        },
        documents: [
          {
            file_id: "document-1",
            file_name: "Manual de soporte.pdf",
            doc_type: "pdf",
            chunk_count: 20,
            status: "indexed",
            error_message: null,
            drive_modified_at: "2026-07-15T10:00:00Z",
            last_indexed_at: "2026-07-15T10:30:00Z",
          },
          {
            file_id: "document-2",
            file_name: "Procedimiento interno.docx",
            doc_type: "docx",
            chunk_count: 8,
            status: "failed",
            error_message: "No fue posible extraer el contenido.",
            drive_modified_at: "2026-07-14T10:00:00Z",
            last_indexed_at: null,
          },
        ],
      },
    }),
    sync: vi.fn().mockResolvedValue({
      data: {
        message: "Sincronización iniciada en background",
      },
    }),
    reindexDocument: vi.fn().mockResolvedValue({
      data: {
        status: "indexed",
        chunk_count: 22,
      },
    }),
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

import KnowledgeBasePage from "./KnowledgeBasePage";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("KnowledgeBasePage profesional", () => {
  it("muestra métricas y documentos indexados", async () => {
    render(
      <MemoryRouter>
        <KnowledgeBasePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Manual de soporte.pdf")).toBeInTheDocument();
    });

    expect(screen.getByText("Documentos registrados")).toBeInTheDocument();
    expect(screen.getByText("Fragmentos RAG")).toBeInTheDocument();
    expect(screen.getByText("Base de conocimiento operativa")).toBeInTheDocument();
    expect(screen.getByText("Procedimiento interno.docx")).toBeInTheDocument();
  });

  it("filtra documentos por búsqueda", async () => {
    render(
      <MemoryRouter>
        <KnowledgeBasePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Manual de soporte.pdf")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Buscar documentos"), {
      target: { value: "procedimiento" },
    });

    expect(screen.queryByText("Manual de soporte.pdf")).not.toBeInTheDocument();
    expect(screen.getByText("Procedimiento interno.docx")).toBeInTheDocument();
  });

  it("abre la confirmación de sincronización incremental", async () => {
    render(
      <MemoryRouter>
        <KnowledgeBasePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Manual de soporte.pdf")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole("button", { name: /sincronizar cambios/i }),
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByText("Sincronización incremental recomendada"),
    ).toBeInTheDocument();
  });
});
