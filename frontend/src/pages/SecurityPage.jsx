import { useState } from "react";
import Navbar from "../components/Layout/Navbar";
import { authAPI } from "../services/api";
import { useAuth } from "../hooks/useAuth";

const C = "#272163";

export default function SecurityPage() {
    const { user, syncUser } = useAuth();
    const [setupData, setSetupData] = useState(null); // { secret, otpauth_uri, qr_code_base64 }
    const [confirmCode, setConfirmCode] = useState("");
    const [disablePassword, setDisablePassword] = useState("");
    const [disableCode, setDisableCode] = useState("");
    const [showDisableForm, setShowDisableForm] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    const mfaEnabled = !!user?.mfa_enabled;

    const startSetup = async () => {
        setLoading(true);
        setError("");
        setSuccess("");
        try {
        const { data } = await authAPI.mfaSetup();
        setSetupData(data);
        } catch (err) {
        setError(err.response?.data?.detail || "No se pudo iniciar el enrolamiento.");
        } finally {
        setLoading(false);
        }
    };

    const cancelSetup = () => {
        setSetupData(null);
        setConfirmCode("");
        setError("");
    };

    const confirmSetup = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError("");
        try {
        await authAPI.mfaConfirm(confirmCode.trim());
        setSetupData(null);
        setConfirmCode("");
        setSuccess("MFA activado. La próxima vez que inicies sesión, te pediremos el código de tu app de autenticación.");
        await syncUser();
        } catch (err) {
        setError(err.response?.data?.detail || "Código incorrecto. Verifica la hora de tu dispositivo e intenta de nuevo.");
        } finally {
        setLoading(false);
        }
    };

    const disableMfa = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError("");
        try {
        await authAPI.mfaDisable(disablePassword, disableCode.trim());
        setShowDisableForm(false);
        setDisablePassword("");
        setDisableCode("");
        setSuccess("MFA desactivado en esta cuenta.");
        await syncUser();
        } catch (err) {
        setError(err.response?.data?.detail || "No se pudo desactivar. Verifica tu contraseña y el código.");
        } finally {
        setLoading(false);
        }
    };

    return (
        <div className="botiq-page botiq-admin-page">
        <Navbar currentPage="security" />

        <main className="botiq-page-main">
            <header style={{ marginBottom: 24 }}>
            <h1 style={{ color: C, fontSize: 24, margin: 0 }}>Seguridad</h1>
            <p style={{ color: "var(--botiq-muted)", marginTop: 6, fontSize: 13 }}>
                Verificación en dos pasos (MFA) para tu cuenta de administrador.
            </p>
            </header>

            {error && <div style={alertStyle}>⚠️ {error}</div>}
            {success && <div style={successAlertStyle}>✅ {success}</div>}

            <section style={cardStyle}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
                <div>
                <h2 style={sectionTitle}>Verificación en dos pasos</h2>
                <p style={{ color: "var(--botiq-muted)", fontSize: 13, margin: 0, maxWidth: 520 }}>
                    Con MFA activo, además de tu contraseña vas a necesitar un código de 6 dígitos
                    de una app como Google Authenticator o Authy para iniciar sesión.
                </p>
                </div>
                <StatusBadge enabled={mfaEnabled} />
            </div>

            {!mfaEnabled && !setupData && (
                <button style={{ ...primaryBtn, marginTop: 18 }} onClick={startSetup} disabled={loading}>
                {loading ? "Generando..." : "Activar MFA"}
                </button>
            )}

            {setupData && (
                <div style={{ marginTop: 20, display: "grid", gridTemplateColumns: "auto 1fr", gap: 24, alignItems: "start" }}>
                <div
                    style={{
                    background: "var(--botiq-card-bg)",
                    border: "1px solid var(--botiq-border)",
                    borderRadius: 12,
                    padding: 12,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    }}
                >
                    <img
                    src={`data:image/png;base64,${setupData.qr_code_base64}`}
                    alt="Código QR para configurar MFA"
                    width={180}
                    height={180}
                    />
                </div>

                <div>
                    <ol style={{ color: "#374151", fontSize: 13, paddingLeft: 18, lineHeight: 1.8, margin: 0 }}>
                    <li>Abre Google Authenticator, Authy, o cualquier app compatible con TOTP.</li>
                    <li>Escanea el código QR de la izquierda.</li>
                    <li>
                        Si no podés escanearlo, ingresá este código manualmente:{" "}
                        <code style={codeStyle}>{setupData.secret}</code>
                    </li>
                    <li>Escribí el código de 6 dígitos que te muestra la app para confirmar.</li>
                    </ol>

                    <form onSubmit={confirmSetup} style={{ marginTop: 16, display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
                    <label style={labelStyle}>
                        Código de verificación
                        <input
                        type="text"
                        inputMode="numeric"
                        maxLength={6}
                        value={confirmCode}
                        onChange={(e) => setConfirmCode(e.target.value.replace(/\D/g, ""))}
                        placeholder="000000"
                        required
                        style={{ ...inputStyle, letterSpacing: 4, fontWeight: 700, width: 140 }}
                        />
                    </label>
                    <button type="submit" style={primaryBtn} disabled={loading || confirmCode.length !== 6}>
                        {loading ? "Verificando..." : "Confirmar y activar"}
                    </button>
                    <button type="button" style={secondaryBtn} onClick={cancelSetup} disabled={loading}>
                        Cancelar
                    </button>
                    </form>
                </div>
                </div>
            )}

            {mfaEnabled && !showDisableForm && (
                <button style={{ ...dangerBtn, marginTop: 18 }} onClick={() => setShowDisableForm(true)}>
                Desactivar MFA
                </button>
            )}

            {mfaEnabled && showDisableForm && (
                <form onSubmit={disableMfa} style={{ marginTop: 18, display: "grid", gap: 12, maxWidth: 360 }}>
                <p style={{ color: "var(--botiq-muted)", fontSize: 12, margin: 0 }}>
                    Por seguridad, necesitamos tu contraseña y un código vigente de tu app de autenticación.
                </p>
                <label style={labelStyle}>
                    Contraseña
                    <input
                    type="password"
                    value={disablePassword}
                    onChange={(e) => setDisablePassword(e.target.value)}
                    required
                    style={inputStyle}
                    />
                </label>
                <label style={labelStyle}>
                    Código de verificación
                    <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    value={disableCode}
                    onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, ""))}
                    placeholder="000000"
                    required
                    style={{ ...inputStyle, letterSpacing: 4, fontWeight: 700 }}
                    />
                </label>
                <div style={{ display: "flex", gap: 10 }}>
                    <button type="submit" style={dangerBtn} disabled={loading || disableCode.length !== 6}>
                    {loading ? "Desactivando..." : "Confirmar desactivación"}
                    </button>
                    <button
                    type="button"
                    style={secondaryBtn}
                    onClick={() => {
                        setShowDisableForm(false);
                        setDisablePassword("");
                        setDisableCode("");
                    }}
                    >
                    Cancelar
                    </button>
                </div>
                </form>
            )}
            </section>
        </main>
        </div>
    );
}

function StatusBadge({ enabled }) {
    return (
        <span
        style={{
            background: enabled ? "#dcfce7" : "#f3f4f6",
            color: enabled ? "#166534" : "#6b7280",
            padding: "5px 12px",
            borderRadius: 999,
            fontSize: 12,
            fontWeight: 700,
            whiteSpace: "nowrap",
        }}
        >
        {enabled ? "✅ Activo" : "Inactivo"}
        </span>
    );
}

const cardStyle = {
    background: "var(--botiq-card-bg)",
    border: "1px solid var(--botiq-border)",
    borderRadius: 14,
    padding: 22,
    marginBottom: 22,
    boxShadow: "0 1px 4px rgba(39,33,99,0.06)",
};

const sectionTitle = { color: C, fontSize: 16, margin: "0 0 6px" };

const labelStyle = {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    fontSize: 12,
    fontWeight: 600,
    color: "#374151",
};

const inputStyle = {
    border: "1px solid var(--botiq-border)",
    borderRadius: 8,
    padding: "9px 10px",
    fontSize: 13,
    outline: "none",
    background: "var(--botiq-card-bg)",
};

const primaryBtn = {
    background: C,
    color: "#fff",
    border: "none",
    borderRadius: 8,
    padding: "10px 16px",
    cursor: "pointer",
    fontWeight: 600,
};

const secondaryBtn = {
    background: "var(--botiq-surface)",
    color: C,
    border: "1px solid var(--botiq-border)",
    borderRadius: 8,
    padding: "10px 16px",
    cursor: "pointer",
    fontWeight: 600,
};

const dangerBtn = {
    background: "#fef2f2",
    color: "#991b1b",
    border: "1px solid #fecaca",
    borderRadius: 8,
    padding: "10px 16px",
    cursor: "pointer",
    fontWeight: 600,
};

const alertStyle = {
    background: "#fef2f2",
    color: "#991b1b",
    border: "1px solid #fecaca",
    borderRadius: 10,
    padding: "12px 14px",
    marginBottom: 18,
    fontSize: 13,
};

const successAlertStyle = {
    background: "#f0fdf4",
    color: "#166534",
    border: "1px solid #bbf7d0",
    borderRadius: 10,
    padding: "12px 14px",
    marginBottom: 18,
    fontSize: 13,
};

const codeStyle = {
    background: "var(--botiq-surface)",
    border: "1px solid var(--botiq-border)",
    borderRadius: 6,
    padding: "2px 6px",
    fontFamily: "monospace",
    fontSize: 12,
};
