import { useState, useRef, useEffect } from "react";
import { useChat } from "../../hooks/useChat";
import { supportAPI } from "../../services/api";
import BotiqAvatar from "../Brand/BotiqAvatar";
import BotiqBotIcon from "../Brand/BotiqBotIcon";

const C = "#272163";
const CL = "#3a3490";

const MODULE_INFO = {
  employee: { label: "General", icon: "👤", color: "#059669" },
  support_rag: { label: "Base Conocimiento", icon: "📚", color: "#7c3aed" },
  server_validation: { label: "Servidores", icon: "🖥️", color: "#0284c7" },
};

const QUICK_QUESTIONS = [
  "No puedo acceder al portal",
  "Error al abrir Excel",
  "¿Cómo solicito soporte técnico?",
];

export default function ChatWidget({ position = "bottom-right", primaryColor = C }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [imgFile, setImgFile] = useState(null);
  const [imgPreview, setImgPreview] = useState(null);
  const [kbStatus, setKbStatus] = useState(null);

  const { messages, loading, sendMessage, clearChat } = useChat();
  const bottomRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (open && messages.length === 0) {
      supportAPI.status().then((r) => setKbStatus(r.data)).catch(() => {});
    }
  }, [open, messages.length]);

  const send = async () => {
    if (!input.trim() && !imgFile) return;

    const text = input;
    const file = imgFile;

    setInput("");
    setImgFile(null);
    setImgPreview(null);

    await sendMessage(text, file);
  };

  const handleKey = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  };

  const handleFile = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      alert("La imagen no puede superar 5MB");
      return;
    }

    setImgFile(file);

    const reader = new FileReader();
    reader.onload = (e) => setImgPreview(e.target.result);
    reader.readAsDataURL(file);

    event.target.value = "";
  };

  const pos =
    position === "bottom-left"
      ? { bottom: 24, left: 24 }
      : { bottom: 24, right: 24 };

  return (
    <div style={{ position: "fixed", zIndex: 9999, ...pos }}>
      {open && (
        <div
          style={{
            width: 390,
            height: 610,
            background: "#fff",
            borderRadius: 20,
            boxShadow: "0 24px 72px rgba(39,33,99,0.26)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            marginBottom: 14,
            border: `1px solid ${primaryColor}22`,
            animation: "botiqSlide 0.25s ease",
          }}
        >
          <div
            style={{
              background: `linear-gradient(135deg, ${primaryColor}, ${CL})`,
              padding: "14px 18px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <BotiqAvatar size={40} color={primaryColor} online />
              <div>
                <div style={{ color: "#fff", fontWeight: 800, fontSize: 15 }}>BOTIQ</div>
                <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      background: "#4ade80",
                      boxShadow: "0 0 7px #4ade80",
                    }}
                  />
                  <span style={{ color: "rgba(255,255,255,0.68)", fontSize: 11 }}>
                    Asistente IA disponible
                  </span>
                </div>
              </div>
            </div>

            <div style={{ display: "flex", gap: 5 }}>
              <HBtn onClick={clearChat} title="Nueva conversación">↺</HBtn>
              <HBtn onClick={() => setOpen(false)} title="Cerrar">✕</HBtn>
            </div>
          </div>

          {kbStatus && !kbStatus.drive_configured && messages.length === 0 && (
            <div
              style={{
                background: "#fef3c7",
                borderBottom: "1px solid #fde68a",
                padding: "8px 16px",
                fontSize: 11,
                color: "#92400e",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              ⚠️ Google Drive no conectado — modo FAQ básico activo.
            </div>
          )}

          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "14px 16px",
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            {messages.length === 0 && (
              <div style={{ textAlign: "center", paddingTop: 22 }}>
                <div style={{ display: "flex", justifyContent: "center", marginBottom: 14 }}>
                  <BotiqAvatar size={58} color={primaryColor} online />
                </div>

                <p
                  style={{
                    fontWeight: 750,
                    color: primaryColor,
                    fontSize: 15,
                    marginBottom: 4,
                  }}
                >
                  Hola, soy BOTIQ
                </p>

                <p style={{ color: "#6b6b8a", fontSize: 12, marginBottom: 16 }}>
                  ¿En qué puedo ayudarte hoy?
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  {QUICK_QUESTIONS.map((question) => (
                    <button
                      key={question}
                      onClick={() => sendMessage(question)}
                      style={{
                        background: `${primaryColor}08`,
                        border: `1px solid ${primaryColor}25`,
                        borderRadius: 20,
                        padding: "7px 14px",
                        fontSize: 12,
                        cursor: "pointer",
                        color: primaryColor,
                        fontWeight: 600,
                        transition: "all 0.2s",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = `${primaryColor}15`;
                        e.currentTarget.style.borderColor = `${primaryColor}50`;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = `${primaryColor}08`;
                        e.currentTarget.style.borderColor = `${primaryColor}25`;
                      }}
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <Bubble key={msg.id} msg={msg} primaryColor={primaryColor} />
            ))}

            {loading && (
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <BotiqAvatar size={28} color={primaryColor} />
                <div
                  style={{
                    background: "#f5f5fa",
                    borderRadius: "4px 12px 12px 12px",
                    padding: "10px 14px",
                  }}
                >
                  <Typing />
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {imgPreview && (
            <div
              style={{
                padding: "6px 14px",
                background: "#f9f9fc",
                borderTop: `1px solid ${primaryColor}15`,
              }}
            >
              <div style={{ position: "relative", display: "inline-block" }}>
                <img
                  src={imgPreview}
                  alt=""
                  style={{
                    height: 54,
                    borderRadius: 8,
                    objectFit: "cover",
                    border: `2px solid ${primaryColor}30`,
                  }}
                />
                <button
                  onClick={() => {
                    setImgFile(null);
                    setImgPreview(null);
                  }}
                  style={{
                    position: "absolute",
                    top: -7,
                    right: -7,
                    background: "#dc2626",
                    border: "none",
                    borderRadius: "50%",
                    width: 19,
                    height: 19,
                    cursor: "pointer",
                    color: "#fff",
                    fontSize: 11,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  ✕
                </button>
              </div>
            </div>
          )}

          <div
            style={{
              padding: "10px 14px",
              borderTop: `1px solid ${primaryColor}15`,
              background: "#fff",
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-end", gap: 7 }}>
              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                style={{ display: "none" }}
                onChange={handleFile}
              />

              <button
                onClick={() => fileRef.current?.click()}
                title="Adjuntar imagen"
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "#9ca3af",
                  padding: 6,
                  flexShrink: 0,
                  fontSize: 18,
                  transition: "color 0.2s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = primaryColor)}
                onMouseLeave={(e) => (e.currentTarget.style.color = "#9ca3af")}
              >
                📎
              </button>

              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Escribe tu consulta..."
                rows={1}
                style={{
                  flex: 1,
                  border: `1.5px solid ${primaryColor}20`,
                  borderRadius: 18,
                  padding: "9px 13px",
                  fontSize: 13,
                  resize: "none",
                  outline: "none",
                  fontFamily: "inherit",
                  maxHeight: 80,
                  overflowY: "auto",
                  background: "#fafafa",
                  transition: "border-color 0.2s, box-shadow 0.2s",
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = primaryColor;
                  e.target.style.boxShadow = `0 0 0 3px ${primaryColor}12`;
                  e.target.style.background = "#fff";
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = `${primaryColor}20`;
                  e.target.style.boxShadow = "none";
                  e.target.style.background = "#fafafa";
                }}
              />

              <button
                onClick={send}
                disabled={loading || (!input.trim() && !imgFile)}
                style={{
                  background:
                    loading || (!input.trim() && !imgFile)
                      ? "#d1d5db"
                      : `linear-gradient(135deg, ${primaryColor}, ${CL})`,
                  border: "none",
                  borderRadius: "50%",
                  width: 36,
                  height: 36,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor:
                    loading || (!input.trim() && !imgFile) ? "not-allowed" : "pointer",
                  flexShrink: 0,
                  color: "#fff",
                  boxShadow:
                    loading || (!input.trim() && !imgFile)
                      ? "none"
                      : `0 2px 8px ${primaryColor}50`,
                }}
              >
                ▶
              </button>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((value) => !value)}
        style={{
          width: 58,
          height: 58,
          background: `linear-gradient(135deg, ${primaryColor}, ${CL})`,
          border: "none",
          borderRadius: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          marginLeft: "auto",
          boxShadow: `0 5px 24px ${primaryColor}60`,
          transition: "transform 0.2s, box-shadow 0.2s",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = "scale(1.08)";
          e.currentTarget.style.boxShadow = `0 7px 30px ${primaryColor}75`;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = "scale(1)";
          e.currentTarget.style.boxShadow = `0 5px 24px ${primaryColor}60`;
        }}
      >
        {open ? (
          <span style={{ color: "#fff", fontSize: 20 }}>✕</span>
        ) : (
          <BotiqBotIcon size={31} color={primaryColor} light />
        )}
      </button>

      <style>
        {`
          @keyframes botiqSlide {
            from { opacity: 0; transform: translateY(16px); }
            to { opacity: 1; transform: translateY(0); }
          }
        `}
      </style>
    </div>
  );
}

function Bubble({ msg, primaryColor }) {
  const isUser = msg.role === "user";
  const mod = MODULE_INFO[msg.meta?.module];

  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        alignItems: "flex-start",
        flexDirection: isUser ? "row-reverse" : "row",
      }}
    >
      {isUser ? (
        <Ava color="#e2e1f0" size={28}>
          <span style={{ fontSize: 12 }}>👤</span>
        </Ava>
      ) : (
        <BotiqAvatar size={28} color={primaryColor} />
      )}

      <div style={{ maxWidth: "78%" }}>
        <div
          style={{
            background: isUser
              ? `linear-gradient(135deg, ${primaryColor}, ${primaryColor}dd)`
              : msg.meta?.isError
              ? "#fef2f2"
              : "#f5f5fa",
            color: isUser ? "#fff" : msg.meta?.isError ? "#dc2626" : "#1a1a2e",
            borderRadius: isUser ? "14px 4px 14px 14px" : "4px 14px 14px 14px",
            padding: "10px 14px",
            fontSize: 13,
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
            boxShadow: isUser
              ? `0 2px 8px ${primaryColor}30`
              : "0 1px 3px rgba(0,0,0,0.06)",
          }}
        >
          {msg.content}
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>
          {mod && !isUser && (
            <span
              style={{
                fontSize: 10,
                color: mod.color,
                display: "flex",
                alignItems: "center",
                gap: 2,
              }}
            >
              {mod.icon} {mod.label}
            </span>
          )}

          {msg.meta?.sources?.length > 0 && (
            <span style={{ fontSize: 10, color: "#6b6b8a" }}>
              📄 {msg.meta.sources.slice(0, 2).join(", ")}
            </span>
          )}

          {msg.meta?.escalated && (
            <span style={{ fontSize: 10, color: "#d97706" }}>⚡ Escalado a Aranda</span>
          )}

          {msg.meta?.knowledgeGap && (
            <span style={{ fontSize: 10, color: "#7c3aed" }}>🧠 Brecha detectada</span>
          )}
        </div>
      </div>
    </div>
  );
}

function Ava({ color, size, children }) {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: color,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      {children}
    </div>
  );
}

function HBtn({ onClick, title, children }) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        background: "rgba(255,255,255,0.11)",
        border: "1px solid rgba(255,255,255,0.2)",
        color: "rgba(255,255,255,0.76)",
        width: 28,
        height: 28,
        borderRadius: 8,
        cursor: "pointer",
        fontSize: 14,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {children}
    </button>
  );
}

function Typing() {
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center", height: 14 }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: "#9ca3af",
            animation: `tDot 1.2s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
      <style>{`@keyframes tDot{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-5px)}}`}</style>
    </div>
  );
}
