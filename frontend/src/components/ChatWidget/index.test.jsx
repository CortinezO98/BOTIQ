import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

vi.mock("../../hooks/useChat", () => ({
  useChat: () => ({
    messages: [],
    loading: false,
    session: null,
    sessionStatus: "idle",
    startSession: vi.fn(),
    sendMessage: vi.fn(),
    clearChat: vi.fn(),
    submitFeedback: vi.fn(),
    submitSatisfaction: vi.fn(),
  }),
}));

vi.mock("../../services/api", () => ({
  supportAPI: { status: vi.fn().mockResolvedValue({ data: {} }) },
}));

import ChatWidget from "./index";

describe("ChatWidget", () => {
  it("se monta sin lanzar ReferenceError (regresión: hooks sin importar + llave duplicada)", () => {
    // Bug real corregido: useState/useEffect/useRef sin importar, más una
    // llave de cierre duplicada "}}" en SatisfactionModal que rompía el
    // parseo del archivo completo.
    expect(() => render(<ChatWidget embedded />)).not.toThrow();
  });
});
