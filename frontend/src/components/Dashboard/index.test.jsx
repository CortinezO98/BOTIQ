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

vi.mock("../../services/api", () => ({
  dashboardAPI: {
    metrics: vi.fn().mockResolvedValue({
      data: {
        total_conversations: 120,
        total_messages: 480,
        total_tokens_used: 36000,
        avg_response_time_ms: 1500,
        avg_satisfaction: 4.4,
      },
    }),
    summary: vi.fn().mockResolvedValue({ data: {} }),
    byModule: vi.fn().mockResolvedValue({
      data: [
        { module: "employee", count: 70 },
        { module: "support_rag", count: 50 },
      ],
    }),
    byDay: vi.fn().mockResolvedValue({
      data: [
        { date: "2026-07-14", count: 18 },
        { date: "2026-07-15", count: 22 },
      ],
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
    tokenConsumption: vi.fn().mockResolvedValue({
      data: [
        { date: "2026-07-14", tokens: 15000 },
        { date: "2026-07-15", tokens: 21000 },
      ],
    }),
    knowledgeGaps: vi.fn().mockResolvedValue({
      data: [
        {
          id: "gap-1",
          question: "¿Cómo configuro la VPN?",
          category: "Conectividad",
          frequency: 4,
          resolved: false,
        },
      ],
    }),
    escalationRate: vi.fn().mockResolvedValue({
      data: {
        rate_pct: 12.5,
        escalated: 15,
        total: 120,
      },
    }),
  },
  supportAPI: {
    sync: vi.fn().mockResolvedValue({
      data: { message: "Sincronización iniciada" },
    }),
  },
}));

import { dashboardAPI, supportAPI } from "../../services/api";
import Dashboard from "./index";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Dashboard profesional", () => {
  it("muestra indicadores y hallazgos", async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Conversaciones")).toBeInTheDocument();
    });

    expect(screen.getAllByText("120").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Estado general de BOTIQ")).toBeInTheDocument();
    expect(screen.getByText("Costo IA estimado")).toBeInTheDocument();
    expect(screen.getByText("$ 72")).toBeInTheDocument();
    expect(screen.getByText("¿Cómo cambio mi contraseña?")).toBeInTheDocument();
    expect(screen.getByText("¿Cómo configuro la VPN?")).toBeInTheDocument();
  });

  it("actualiza automáticamente al cambiar el período", async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Conversaciones")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Período del dashboard"), {
      target: { value: "90" },
    });

    await waitFor(() => {
      expect(dashboardAPI.metrics).toHaveBeenCalledWith(90);
      expect(dashboardAPI.byDay).toHaveBeenCalledWith(90);
      expect(dashboardAPI.byModule).toHaveBeenCalledWith(90);
    });
  });

  it("permite sincronizar la base de conocimiento", async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Conversaciones")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole("button", { name: /sincronizar conocimiento/i }),
    );

    await waitFor(() => {
      expect(supportAPI.sync).toHaveBeenCalledWith(false);
      expect(screen.getByText("Sincronización iniciada")).toBeInTheDocument();
    });
  });
});
