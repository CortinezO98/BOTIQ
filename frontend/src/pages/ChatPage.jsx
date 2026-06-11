import ChatWidget from "../components/ChatWidget";
import Navbar from "../components/Layout/Navbar";
import { useAuth } from "../hooks/useAuth";

const C = "#272163";

export default function ChatPage() {
  const { user, isSupport } = useAuth();
  return (
    <div style={{ minHeight: "100vh", background: "#f5f5fa" }}>
      <Navbar currentPage="chat" />
      <div style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", height: "calc(100vh - 56px)",
        textAlign: "center", padding: 24,
      }}>
        <div style={{
          width: 80, height: 80, background: C, borderRadius: 24,
          display: "flex", alignItems: "center", justifyContent: "center",
          margin: "0 auto 20px", boxShadow: `0 8px 32px ${C}35`,
        }}>
          <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
            <path d="M10 20 L20 10 L30 20 L20 30 Z" fill="rgba(255,255,255,0.2)" stroke="#fff" strokeWidth="1.5"/>
            <circle cx="20" cy="20" r="5" fill="#fff"/>
            <path d="M20 6 L20 11 M20 29 L20 34 M6 20 L11 20 M29 20 L34 20" stroke="#fff" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: C, marginBottom: 8 }}>
          ¡Bienvenido, {user?.full_name?.split(" ")[0]}!
        </h2>
        <p style={{ color: "#6b6b8a", fontSize: 14, maxWidth: 360, lineHeight: 1.6 }}>
          Haz clic en el botón en la esquina inferior derecha para abrir el asistente BOTIQ.
        </p>
        {isSupport && (
          <div style={{
            marginTop: 20, background: `${C}08`,
            border: `1px solid ${C}25`, borderRadius: 10,
            padding: "12px 20px", maxWidth: 380,
          }}>
            <p style={{ fontSize: 12, color: C, fontWeight: 500 }}>
              🔧 Modo Ingeniero de Soporte — Acceso a base de conocimiento RAG y validación de servidores
            </p>
          </div>
        )}
      </div>
      <ChatWidget primaryColor={C} position="bottom-right" />
    </div>
  );
}
