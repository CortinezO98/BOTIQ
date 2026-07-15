import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

vi.mock("../../services/api", () => ({
  dashboardAPI: {
    metrics: vi.fn().mockResolvedValue({ data: {} }),
    summary: vi.fn().mockResolvedValue({ data: {} }),
    byModule: vi.fn().mockResolvedValue({ data: [] }),
    byDay: vi.fn().mockResolvedValue({ data: [] }),
    topFaqs: vi.fn().mockResolvedValue({ data: [] }),
    tokenConsumption: vi.fn().mockResolvedValue({ data: [] }),
    knowledgeGaps: vi.fn().mockResolvedValue({ data: [] }),
    escalationRate: vi.fn().mockResolvedValue({ data: {} }),
  },
  supportAPI: {},
}));

import Dashboard from "./index";

describe("Dashboard", () => {
  it("se monta sin lanzar ReferenceError (regresión: useState/useEffect/useMemo sin importar)", () => {
    expect(() => render(<Dashboard />)).not.toThrow();
  });
});
