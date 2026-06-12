import ChatWidget from "../components/ChatWidget";
import Navbar from "../components/Layout/Navbar";
import { useAuth } from "../hooks/useAuth";
import BotiqAvatar from "../components/Brand/BotiqAvatar";

const C = "#272163";

export default function ChatPage() {
  const { user, isSupport } = useAuth();

  return (
    <div style={{ minHeight: "100vh", background: "#f5f5fa" }}>
      <Navbar currentPage="chat" />

      <div
        style={{
          minHeight: "calc(100vh - 58px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          padding: 24,
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
            top: -180,
            right: -140,
          }}
        />

        <div
          style={{
            background: "#fff",
            border: "1px solid #e2e1f0",
            boxShadow: "0 18px 60px rgba(39,33,99,0.1)",
            borderRadius: 24,
            padding: "38px 32px",
            maxWidth: 560,
            width: "100%",
            position: "relative",
            zIndex: 1,
          }}
        >
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 20 }}>
            <BotiqAvatar size={86} online />
          </div>

          <h2 style={{ fontSize: 25, fontWeight: 850, color: C, marginBottom: 8 }}>
            ¡Bienvenido, {user?.full_name?.split(" ")[0]}!
          </h2>

          <p
            style={{
              color: "#6b6b8a",
              fontSize: 14,
              maxWidth: 410,
              margin: "0 auto",
              lineHeight: 1.7,
            }}
          >
            BOTIQ está listo para ayudarte con soporte, documentación corporativa
            y validación de servicios.
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
            <Chip>💬 Soporte</Chip>
            <Chip>📚 Conocimiento</Chip>
            <Chip>🤖 IA</Chip>
          </div>

          {isSupport && (
            <div
              style={{
                marginTop: 24,
                background: `${C}08`,
                border: `1px solid ${C}25`,
                borderRadius: 12,
                padding: "12px 18px",
              }}
            >
              <p style={{ fontSize: 12, color: C, fontWeight: 650, margin: 0 }}>
                🔧 Modo Ingeniero de Soporte — acceso a RAG y validación de servidores.
              </p>
            </div>
          )}
        </div>
      </div>

      <ChatWidget primaryColor={C} position="bottom-right" />
    </div>
  );
}

function Chip({ children }) {
  return (
    <span
      style={{
        background: "#f5f5fa",
        border: "1px solid #e2e1f0",
        color: C,
        padding: "6px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 700,
      }}
    >
      {children}
    </span>
  );
}
