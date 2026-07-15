import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import BotiqLogo from "../components/Brand/BotiqLogo";
import BotiqAvatar from "../components/Brand/BotiqAvatar";

const C = "#272163";
const CH = "var(--botiq-heading)"; // texto/headings: sí se adapta a modo oscuro (C se mantiene fijo por los patrones ${C}XX de alpha-transparencia)
const CL = "#3a3490";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [show, setShow] = useState(false);
  const [mfaChallengeToken, setMfaChallengeToken] = useState(null);
  const [mfaCode, setMfaCode] = useState("");
  const { login, verifyMfa, loading, error } = useAuth();
  const nav = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      const result = await login(email.trim(), pass);
      if (result.mfaRequired) {
        setMfaChallengeToken(result.mfaChallengeToken);
        return;
      }
      nav(result.user.role === "admin" ? "/dashboard" : "/chat");
    } catch {
      // El error ya queda expuesto vía el hook (useAuth().error) y se
      // muestra abajo del formulario.
    }
  };

  const handleMfaSubmit = async (e) => {
    e.preventDefault();
    try {
      const user = await verifyMfa(mfaChallengeToken, mfaCode.trim());
      nav(user.role === "admin" ? "/dashboard" : "/chat");
    } catch {
      // El error ya queda expuesto vía el hook.
    }
  };

  return (
    <div
      className="botiq-login-page-inline"
      style={{
        minHeight: "100vh",
        background:
          "radial-gradient(circle at top left, rgba(79,70,229,0.32), transparent 34%), linear-gradient(135deg, #1a1645 0%, #272163 48%, #3a3490 100%)",
        display: "grid",
        placeItems: "center",
        padding: 24,
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        className="animate__animated animate__fadeIn animate__slow"
        style={{
          position: "absolute",
          width: 360,
          height: 360,
          borderRadius: "50%",
          background: "rgba(255,255,255,0.06)",
          right: -110,
          top: -90,
          filter: "blur(1px)",
        }}
      />

      <div
        className="animate__animated animate__fadeInUp animate__slow"
        style={{
          position: "absolute",
          width: 240,
          height: 240,
          borderRadius: "50%",
          background: "rgba(79,70,229,0.18)",
          left: -70,
          bottom: -60,
        }}
      />

      <div
        className="botiq-login-grid-inline"
        style={{
          width: "100%",
          maxWidth: 980,
          display: "grid",
          gridTemplateColumns: "1.1fr 0.9fr",
          gap: 28,
          alignItems: "center",
          position: "relative",
          zIndex: 1,
        }}
      >
        <section
          className="botiq-login-hero-inline animate__animated animate__fadeInLeft"
          style={{ color: "#fff", padding: "20px 8px" }}
        >
          <BotiqLogo variant="light" size="lg" showSubtitle />

          <h1
            style={{
              marginTop: 34,
              marginBottom: 14,
              fontSize: "clamp(32px, 5vw, 54px)",
              lineHeight: 1.05,
              letterSpacing: "-1.6px",
              fontWeight: 850,
              maxWidth: 620,
            }}
          >
            Soporte corporativo inteligente en un solo lugar.
          </h1>

          <p
            style={{
              maxWidth: 560,
              color: "rgba(255,255,255,0.76)",
              fontSize: 16,
              lineHeight: 1.7,
            }}
          >
            BOTIQ centraliza consultas de empleados, base de conocimiento RAG,
            validación de servidores y métricas administrativas con IA.
          </p>

          <div
            className="botiq-login-pills-inline"
            style={{ marginTop: 28, display: "flex", flexWrap: "wrap", gap: 10 }}
          >
            <Pill>💬 Chat interno</Pill>
            <Pill>📚 RAG corporativo</Pill>
            <Pill>🖥️ Servidores</Pill>
            <Pill>📊 Dashboard</Pill>
          </div>
        </section>

        <section
          className={`botiq-login-card-inline animate__animated ${error ? "animate__shakeX" : "animate__fadeInRight"}`}
          style={{
            background: "rgba(255,255,255,0.96)",
            border: "1px solid rgba(255,255,255,0.35)",
            borderRadius: 24,
            padding: "38px 34px",
            boxShadow: "0 28px 80px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.9), inset 0 -6px 16px rgba(39,33,99,0.03)",
            backdropFilter: "blur(12px)",
          }}
        >
          {mfaChallengeToken ? (
            <>
              <div style={{ textAlign: "center", marginBottom: 30 }}>
                <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
                  <BotiqAvatar size={72} online />
                </div>

                <h2 style={{ margin: 0, color: CH, fontSize: 25, fontWeight: 850, letterSpacing: "-0.6px" }}>
                  Verificación en dos pasos
                </h2>

                <p style={{ marginTop: 7, color: "var(--botiq-muted)", fontSize: 13 }}>
                  Ingresa el código de 6 dígitos de tu app de autenticación.
                </p>
              </div>

              <form onSubmit={handleMfaSubmit}>
                <div style={{ marginBottom: 18 }}>
                  <label style={labelStyle}>Código de verificación</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]{6}"
                    maxLength={6}
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ""))}
                    required
                    autoFocus
                    placeholder="000000"
                    style={{ ...inputStyle, textAlign: "center", fontSize: 22, letterSpacing: 8, fontWeight: 700 }}
                    onFocus={focusInput}
                    onBlur={blurInput}
                  />
                </div>

                {error && (
                  <div
                    className="animate__animated animate__shakeX"
                    style={{
                      background: "#fef2f2",
                      border: "1px solid #fecaca",
                      color: "#991b1b",
                      borderRadius: 10,
                      padding: "10px 12px",
                      fontSize: 13,
                      marginBottom: 16,
                    }}
                  >
                    ⚠️ {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading || mfaCode.length !== 6}
                  style={{
                    width: "100%",
                    border: "none",
                    borderRadius: 12,
                    padding: "13px 16px",
                    background: loading || mfaCode.length !== 6 ? "#9ca3af" : `linear-gradient(135deg, ${C}, ${CL})`,
                    color: "#fff",
                    fontWeight: 750,
                    fontSize: 15,
                    cursor: loading || mfaCode.length !== 6 ? "not-allowed" : "pointer",
                    boxShadow: loading || mfaCode.length !== 6 ? "none" : `0 8px 22px ${C}3d`,
                    transition: "all 0.2s ease",
                  }}
                >
                  {loading ? "Verificando..." : "Verificar →"}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setMfaChallengeToken(null);
                    setMfaCode("");
                  }}
                  style={{
                    width: "100%",
                    border: "none",
                    background: "transparent",
                    color: "var(--botiq-muted)",
                    fontSize: 13,
                    marginTop: 14,
                    cursor: "pointer",
                  }}
                >
                  ← Volver a intentar con otra cuenta
                </button>
              </form>
            </>
          ) : (
            <>
              <div style={{ textAlign: "center", marginBottom: 30 }}>
                <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
                  <BotiqAvatar size={72} online />
                </div>

                <h2 style={{ margin: 0, color: CH, fontSize: 25, fontWeight: 850, letterSpacing: "-0.6px" }}>
                  Iniciar sesión
                </h2>

                <p style={{ marginTop: 7, color: "var(--botiq-muted)", fontSize: 13 }}>
                  Accede con tu cuenta corporativa.
                </p>
              </div>

              <form onSubmit={handleSubmit}>
                <div style={{ marginBottom: 16 }}>
                  <label style={labelStyle}>Email corporativo</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                    placeholder="usuario@empresa.com"
                    style={inputStyle}
                    onFocus={focusInput}
                    onBlur={blurInput}
                  />
                </div>

                <div style={{ marginBottom: 18 }}>
                  <label style={labelStyle}>Contraseña</label>
                  <div style={{ position: "relative" }}>
                    <input
                      type={show ? "text" : "password"}
                      value={pass}
                      onChange={(e) => setPass(e.target.value)}
                      required
                      autoComplete="current-password"
                      placeholder="Tu contraseña"
                      style={{ ...inputStyle, paddingRight: 48 }}
                      onFocus={focusInput}
                      onBlur={blurInput}
                    />

                    <button
                      type="button"
                      onClick={() => setShow((value) => !value)}
                      style={{
                        position: "absolute",
                        right: 12,
                        top: "50%",
                        transform: "translateY(-50%)",
                        background: "transparent",
                        border: "none",
                        color: "var(--botiq-muted)",
                        cursor: "pointer",
                        fontSize: 16,
                      }}
                      title={show ? "Ocultar contraseña" : "Ver contraseña"}
                    >
                      {show ? "🙈" : "👁️"}
                    </button>
                  </div>
                </div>

                {error && (
                  <div
                    className="animate__animated animate__shakeX"
                    style={{
                      background: "#fef2f2",
                      border: "1px solid #fecaca",
                      color: "#991b1b",
                      borderRadius: 10,
                      padding: "10px 12px",
                      fontSize: 13,
                      marginBottom: 16,
                    }}
                  >
                    ⚠️ {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    width: "100%",
                    border: "none",
                    borderRadius: 12,
                    padding: "13px 16px",
                    background: loading ? "#9ca3af" : `linear-gradient(135deg, ${C}, ${CL})`,
                    color: "#fff",
                    fontWeight: 750,
                    fontSize: 15,
                    cursor: loading ? "not-allowed" : "pointer",
                    boxShadow: loading ? "none" : `0 8px 22px ${C}3d`,
                    transition: "all 0.2s ease",
                  }}
                >
                  {loading ? "Ingresando..." : "Ingresar a BOTIQ →"}
                </button>
              </form>
            </>
          )}

          <p style={{ textAlign: "center", color: "#9ca3af", fontSize: 11, marginTop: 24 }}>
            IQ Corporation · Powered by Vertex AI
          </p>
        </section>
      </div>
    </div>
  );
}

function Pill({ children }) {
  return (
    <span
      style={{
        background: "rgba(255,255,255,0.1)",
        border: "1px solid rgba(255,255,255,0.18)",
        color: "rgba(255,255,255,0.86)",
        padding: "8px 12px",
        borderRadius: 999,
        fontSize: 13,
        fontWeight: 600,
      }}
    >
      {children}
    </span>
  );
}

const labelStyle = { display: "block", color: "#374151", fontSize: 12, fontWeight: 700, marginBottom: 7 };

const inputStyle = {
  width: "100%",
  border: "1.5px solid var(--botiq-border)",
  borderRadius: 11,
  padding: "11px 14px",
  background: "#fafafa",
  outline: "none",
  color: "var(--botiq-text)",
  fontSize: 14,
  transition: "border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease",
  boxSizing: "border-box",
};

function focusInput(e) {
  e.target.style.borderColor = C;
  e.target.style.boxShadow = `0 0 0 4px ${C}14`;
  e.target.style.background = "var(--botiq-card-bg)";
}

function blurInput(e) {
  e.target.style.borderColor = "var(--botiq-border)";
  e.target.style.boxShadow = "none";
  e.target.style.background = "#fafafa";
}
