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

describe("api.js — interceptor de Authorization para el widget embebible", () => {
    afterEach(() => {
        localStorage.removeItem("botiq_token");
    });

    it("NO agrega header Authorization cuando no hay token de widget (caso normal: app principal, cookies)", async () => {
        let capturedConfig;
        await api.get("/health", { adapter: fakeAdapter((config) => { capturedConfig = config; }) });

        expect(getAuthHeader(capturedConfig)).toBeUndefined();
    });

    it("agrega el header Authorization cuando embed/widget-entry.jsx guardó un token en localStorage", async () => {
        localStorage.setItem("botiq_token", "un-jwt-de-prueba");

        let capturedConfig;
        await api.get("/health", { adapter: fakeAdapter((config) => { capturedConfig = config; }) });

        expect(getAuthHeader(capturedConfig)).toBe("Bearer un-jwt-de-prueba");
    });
});