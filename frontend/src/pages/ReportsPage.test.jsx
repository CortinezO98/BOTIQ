import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("recharts", () => ({
  Area: () => <div />,
  AreaChart: () => <div data-testid="area-chart" />,
  Bar: () => <div />,
  BarChart: () => <div data-testid="bar-chart" />,
  CartesianGrid: () => <div />,
  Cell: () => <div />,
  Pie: () => <div data-testid="pie" />,
  PieChart: () => <div data-testid="pie-chart" />,
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  Tooltip: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
}));

vi.mock("../services/api", () => ({
  dashboardAPI: {
    metrics: vi.fn().mockResolvedValue({
      data: {
        total_conversations: 120,
        total_messages: 480,
        total_tokens_used: 36000,
        avg_response_time_ms: 1450,
      },
    }),
    byDay: vi.fn().mockResolvedValue({
      data: [
        { date: "2026-07-14", count: 18 },
        { date: "2026-07-15", count: 22 },
      ],
    }),
    byModule: vi.fn().mockResolvedValue({
      data: [
        { module: "employee", count: 70 },
        { module: "support_rag", count: 50 },
      ],
    }),
    tokenConsumption: vi.fn().mockResolvedValue({
      data: [
        { date: "2026-07-14", tokens: 15000 },
        { date: "2026-07-15", tokens: 21000 },
      ],
    }),
    escalationRate: vi.fn().mockResolvedValue({
      data: {
        rate_pct: 12.5,
        escalated: 15,
        total: 120,
      },
    }),
    topFaqs: vi.fn().mockResolvedValue({
      data: [
        {
          question: "¿Cómo cambio mi contraseña?",
          category: "Accesos",
          hits: 25,
        },
      ],
    }),
  },
  chatAPI: {
    adminConversationLogsExport: vi.fn().mockResolvedValue({
      data: new Blob(["id,user"], { type: "text/csv" }),
    }),
  },
  downloadBlob: vi.fn(),
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

import { dashboardAPI } from "../services/api";
import ReportsPage from "./ReportsPage";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ReportsPage profesional", () => {
  it("muestra KPIs, hallazgos y reportes", async () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("120").length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText("Conversaciones")).toBeInTheDocument();
    expect(screen.getByText("Tokens consumidos")).toBeInTheDocument();
    expect(screen.getByText("Hallazgos principales")).toBeInTheDocument();
    expect(screen.getByText("FAQs más consultadas")).toBeInTheDocument();
    expect(screen.getByText("¿Cómo cambio mi contraseña?")).toBeInTheDocument();
  });

  it("actualiza automáticamente al cambiar el período", async () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("120").length).toBeGreaterThanOrEqual(1);
    });

    fireEvent.change(screen.getByLabelText("Período del reporte"), {
      target: { value: "90" },
    });

    await waitFor(() => {
      expect(dashboardAPI.metrics).toHaveBeenCalledWith(90);
      expect(dashboardAPI.byDay).toHaveBeenCalledWith(90);
      expect(dashboardAPI.byModule).toHaveBeenCalledWith(90);
      expect(dashboardAPI.tokenConsumption).toHaveBeenCalledWith(90);
      expect(dashboardAPI.escalationRate).toHaveBeenCalledWith(90);
      expect(screen.getByText("90 días")).toBeInTheDocument();
    });
  });

  it("permite exportar logs de conversaciones", async () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("120").length).toBeGreaterThanOrEqual(1);
    });

    fireEvent.click(
      screen.getByRole("button", { name: /logs de conversaciones/i }),
    );

    await waitFor(() => {
      expect(
        screen.getByText(/reporte de conversaciones fue exportado/i),
      ).toBeInTheDocument();
    });
  });
});
