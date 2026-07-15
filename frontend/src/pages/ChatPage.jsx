import BotiqAvatar from "../components/Brand/BotiqAvatar";
import Navbar from "../components/Layout/Navbar";
import { useAuth } from "../hooks/useAuth";

const C = "#272163";

export default function ChatPage() {
  const { user, isSupport } = useAuth();
  const firstName = user?.full_name?.split(" ")[0] || "Usuario";

  return (
    <div style={{ minHeight: "100vh", background: "var(--botiq-surface)" }}>
      <Navbar currentPage="chat" />

      <main
        className="animate__animated animate__fadeIn"
        style={{
          minHeight: "calc(100vh - 58px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          padding: "clamp(18px, 4vw, 34px)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            width: 420,
            height: 420,
            borderRadius: "50%",
            background: `${C}08`,
            top: -180,
            right: -140,
          }}
        />

        <section
          className="animate__animated animate__fadeInUp"
          style={{
            background: "var(--botiq-card-bg)",
            border: "1px solid var(--botiq-border)",
            boxShadow: "0 18px 60px rgba(39,33,99,0.1)",
            borderRadius: 24,
            padding: "clamp(26px, 4vw, 42px) clamp(20px, 4vw, 36px)",
            maxWidth: 590,
            width: "100%",
            position: "relative",
            zIndex: 1,
          }}
        >
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 20 }}>
            <BotiqAvatar size={86} color={C} online />
          </div>

          <h1
            style={{
              fontSize: "clamp(24px, 4vw, 32px)",
              fontWeight: 900,
              color: C,
              marginBottom: 10,
              letterSpacing: "-0.7px",
            }}
          >
            ¡Bienvenido, {firstName}!
          </h1>

          <p
            style={{
              color: "var(--botiq-muted)",
              fontSize: "clamp(13px, 2vw, 15px)",
              maxWidth: 460,
              margin: "0 auto",
              lineHeight: 1.75,
            }}
          >
            BOTIQ está listo para ayudarte con soporte, aplicativos, URLs,
            documentación corporativa, validación de servicios y trazabilidad de
            conversaciones por usuario.
          </p>

          <div
            style={{
              marginTop: 24,
              display: "flex",
              justifyContent: "center",
              gap: 10,
              flexWrap: "wrap",
            }}
          >
            <Chip>💬 FAQs empleados</Chip>
            <Chip>📚 Base conocimiento</Chip>
            <Chip>🔎 Estados de servicios</Chip>
            <Chip>🎫 Aranda última instancia</Chip>
          </div>

          {isSupport && (
            <div
              style={{
                margin: "24px auto 0",
                background: `${C}08`,
                border: `1px solid ${C}25`,
                borderRadius: 14,
                padding: "12px 18px",
                maxWidth: 560,
              }}
            >
              <p style={{ fontSize: 12, color: C, fontWeight: 750, margin: 0, lineHeight: 1.6 }}>
                🔧 Modo Ingeniero de Soporte — acceso a RAG, base de conocimiento,
                validación de usuario de red y análisis de servidores.
              </p>
            </div>
          )}

          <p style={{ color: "var(--botiq-muted)", fontSize: 12, marginTop: 22 }}>
            Usa el botón flotante inferior derecho para iniciar una conversación.
          </p>
        </section>
      </main>
    </div>
  );
}

function Chip({ children }) {
  return (
    <span
      style={{
        background: "var(--botiq-surface)",
        border: "1px solid var(--botiq-border)",
        color: C,
        padding: "7px 12px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 750,
      }}
    >
      {children}
    </span>
  );
}
