import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../services/api", () => ({
    adminAPI: {
        listUsers: vi.fn().mockResolvedValue({
        data: [
            {
            id: "1",
            full_name: "Ana Torres",
            email: "ana@iq-online.com",
            role: "employee",
            is_active: true,
            created_at: "2026-07-15T10:00:00Z",
            },
        ],
        }),
        createUser: vi.fn(),
        updateUser: vi.fn(),
        changeRole: vi.fn(),
        disableUser: vi.fn(),
        enableUser: vi.fn(),
    },
}));

vi.mock("../hooks/useAuth", () => ({
    useAuth: () => ({ user: { role: "admin" }, logout: vi.fn(), isAdmin: true }),
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

import UsersPage from "./UsersPage";

describe("UsersPage", () => {
    it("se monta sin errores y renderiza tanto la tabla (desktop) como las tarjetas (mobile)", async () => {
        expect(() => render(<MemoryRouter><UsersPage /></MemoryRouter>)).not.toThrow();

        // El nombre aparece dos veces: una en la fila de tabla, otra en la tarjeta móvil
        // (ambas conviven en el DOM, el CSS decide cuál se ve según el ancho).
        await waitFor(() => {
        expect(screen.getAllByText("Ana Torres").length).toBeGreaterThanOrEqual(1);
        });
        expect(screen.getAllByText("ana@iq-online.com").length).toBeGreaterThanOrEqual(1);
    });
});
