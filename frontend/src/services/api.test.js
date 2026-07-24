import { afterEach, describe, expect, it, vi } from "vitest";

import api, {
  clearEmbeddedApi,
  configureEmbeddedApi,
  getApiRuntimeConfig,
} from "./api";

function getHeader(config, name) {
  const headers = config.headers;
  if (headers && typeof headers.get === "function") {
    return headers.get(name);
  }
  return headers?.[name];
}

function fakeAdapter(onConfig) {
  return (config) => {
    onConfig(config);
    return Promise.resolve({
      data: {},
      status: 200,
      statusText: "OK",
      headers: {},
      config,
    });
  };
}

function fakeJwt(payload) {
  const encode = (value) =>
    window
      .btoa(JSON.stringify(value))
      .replace(/=/g, "")
      .replace(/\+/g, "-")
      .replace(/\//g, "_");

  return `${encode({ alg: "none", typ: "JWT" })}.${encode(payload)}.firma`;
}

describe("api.js — cookie normal y widget efímero", () => {
  afterEach(() => {
    clearEmbeddedApi();
    localStorage.removeItem("botiq_token");
    localStorage.removeItem("botiq_user");
    vi.restoreAllMocks();
  });

  it("ignora JWT heredados de localStorage en la aplicación principal", async () => {
    localStorage.setItem("botiq_token", "jwt-antiguo");
    let captured;

    await api.get("/employees/faqs", {
      adapter: fakeAdapter((config) => {
        captured = config;
      }),
    });

    expect(getHeader(captured, "Authorization")).toBeUndefined();
    expect(getApiRuntimeConfig().mode).toBe("cookie");
  });

  it("configura apiUrl dinámico y contexto del portal", async () => {
    const token = fakeJwt({
      exp: Math.floor(Date.now() / 1000) + 600,
    });

    configureEmbeddedApi({
      apiUrl: "https://botiq.example.com",
      authToken: token,
      portalId: "portal-icetex",
      parentOrigin: "https://portal.icetex.gov.co",
    });

    let captured;
    await api.get("/employees/faqs", {
      adapter: fakeAdapter((config) => {
        captured = config;
      }),
    });

    expect(captured.baseURL).toBe(
      "https://botiq.example.com/api/v1",
    );
    expect(getHeader(captured, "Authorization")).toBe(`Bearer ${token}`);
    expect(getHeader(captured, "X-BOTIQ-Portal-Id")).toBe(
      "portal-icetex",
    );
    expect(getHeader(captured, "X-BOTIQ-Parent-Origin")).toBe(
      "https://portal.icetex.gov.co",
    );
    expect(captured.withCredentials).toBe(false);
  });

  it("solicita un token nuevo cuando el actual está por expirar", async () => {
    const expired = fakeJwt({
      exp: Math.floor(Date.now() / 1000) - 10,
    });
    const renewed = fakeJwt({
      exp: Math.floor(Date.now() / 1000) + 600,
    });
    const tokenProvider = vi.fn().mockResolvedValue({
      access_token: renewed,
    });

    configureEmbeddedApi({
      apiUrl: "https://botiq.example.com/api/v1",
      authToken: expired,
      tokenProvider,
      portalId: "portal-demo",
      parentOrigin: "https://portal.example.com",
    });

    let captured;
    await api.get("/chat/conversations", {
      adapter: fakeAdapter((config) => {
        captured = config;
      }),
    });

    expect(tokenProvider).toHaveBeenCalledTimes(1);
    expect(getHeader(captured, "Authorization")).toBe(
      `Bearer ${renewed}`,
    );
  });
});
