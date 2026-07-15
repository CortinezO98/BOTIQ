import { describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

vi.mock("../services/api", () => ({
  chatAPI: {
    startSession: vi.fn(),
    sendMessage: vi.fn(),
    endSession: vi.fn(),
    submitFeedback: vi.fn(),
    submitSatisfaction: vi.fn(),
    conversationMessages: vi.fn(),
  },
}));

import { useChat } from "./useChat";

describe("useChat", () => {
  it("se monta sin lanzar ReferenceError (regresión: hooks de React sin importar)", () => {
    // Bug real corregido: useState/useCallback/useRef se usaban sin
    // importar de "react", lo que reventaba TODO el ChatWidget en runtime
    // con "Uncaught ReferenceError: useState is not defined".
    let result;
    expect(() => {
      const rendered = renderHook(() => useChat());
      result = rendered.result;
    }).not.toThrow();

    expect(result.current.messages).toEqual([]);
    expect(result.current.session).toBeNull();
    expect(result.current.sessionStatus).toBe("idle");
    expect(typeof result.current.sendMessage).toBe("function");
  });
});