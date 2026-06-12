import ChatHistory from "../components/ChatHistory";
import ChatWidget from "../components/ChatWidget";
import BotiqAvatar from "../components/Brand/BotiqAvatar";
import Navbar from "../components/Layout/Navbar";
import { useAuth } from "../hooks/useAuth";

const C = "#272163";

export default function ChatPage() {
  const { user, isSupport } = useAuth();

  return (
    <div className="botiq-page">
      <Navbar currentPage="chat" />

      <div className="botiq-chat-layout">
        <ChatHistory />

        <main className="botiq-chat-main">
          <section
            className="animate__animated animate__fadeIn"
            style={{
              width: "min(100%, 760px)",
              textAlign: "center",
              padding: "clamp(18px, 4vw, 34px)",
              position: "relative",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                position: "absolute",
                width: 420,
                height: 420,
                borderRadius: "50%",
                background: `${C}08`,
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
                zIndex: 0,
              }}
            />

            <div style={{ position: "relative", zIndex: 1 }}>
              <div style={{ display: "flex", justifyContent: "center", marginBottom: 20 }}>
                <BotiqAvatar size={88} color={C} online />
              </div>

              <h1
                style={{
                  fontSize: "clamp(24px, 4vw, 34px)",
                  fontWeight: 900,
                  color: C,
                  marginBottom: 10,
                  letterSpacing: "-0.8px",
                }}
              >
                ¡Bienvenido, {user?.full_name?.split(" ")[0] || "usuario"}!
              </h1>

              <p
                style={{
                  color: "#6b6b8a",
                  fontSize: "clamp(13px, 2vw, 15px)",
                  maxWidth: 560,
                  margin: "0 auto",
                  lineHeight: 1.75,
                }}
              >
                BOTIQ está listo para ayudarte con soporte, aplicativos, URLs,
                documentación corporativa, validación de servicios y control de tickets antes de escalar a Aranda.
              </p>

              <div
                style={{
                  marginTop: 22,
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
                    🔧 Modo soporte disponible: RAG con PDFs/documentos, validación de usuario de red y análisis de servidores.
                  </p>
                </div>
              )}

              <p style={{ color: "#6b6b8a", fontSize: 12, marginTop: 20 }}>
                Usa el botón flotante inferior derecho para iniciar una conversación.
                <span className="botiq-mobile-only"> El historial se oculta en móvil para optimizar el espacio.</span>
              </p>
            </div>
          </section>
        </main>
      </div>

      <ChatWidget primaryColor={C} position="bottom-right" />
    </div>
  );
}

function Chip({ children }) {
  return (
    <span
      style={{
        background: "#fff",
        border: "1px solid #e2e1f0",
        color: C,
        padding: "7px 11px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 800,
        boxShadow: "0 8px 20px rgba(39,33,99,0.07)",
      }}
    >
      {children}
    </span>
  );
}
