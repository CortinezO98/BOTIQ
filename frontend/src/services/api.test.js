import { afterEach, describe, expect, it } from "vitest";
import api from "./api";

function getAuthHeader(config) {
  const headers = config.headers;
  if (headers && typeof headers.get === "function") {
    return headers.get("Authorization");
  }
  return headers?.Authorization;
}

function fakeAdapter(onConfig) {
  return (config) => {
    onConfig(config);
    return Promise.resolve({ data: {}, status: 200, statusText: "OK", headers: {}, config });
  };
}

describe("api.js — autenticación por cookie y widget", () => {
  afterEach(() => {
    localStorage.removeItem("botiq_token");
    localStorage.removeItem("botiq_user");
    delete window.__BOTIQ_EMBED_AUTH_TOKEN__;
  });

  it("ignora tokens heredados de localStorage en la aplicación principal", async () => {
    localStorage.setItem("botiq_token", "jwt-antiguo");
    let capturedConfig;

    await api.get("/health", {
      adapter: fakeAdapter((config) => { capturedConfig = config; }),
    });

    expect(getAuthHeader(capturedConfig)).toBeUndefined();
  });

  it("agrega Authorization solo cuando el widget tiene un token en memoria", async () => {
    window.__BOTIQ_EMBED_AUTH_TOKEN__ = "jwt-widget";
    let capturedConfig;

    await api.get("/health", {
      adapter: fakeAdapter((config) => { capturedConfig = config; }),
    });

    expect(getAuthHeader(capturedConfig)).toBe("Bearer jwt-widget");
  });
});
