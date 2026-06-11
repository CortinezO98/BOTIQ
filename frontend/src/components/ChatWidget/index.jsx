import { useState, useRef, useEffect } from "react";
import { MessageCircle, X, Send, Paperclip, Bot, User, AlertTriangle, BookOpen, Server, RefreshCw } from "lucide-react";
import { useChat } from "../../hooks/useChat";

const MODULE_CONFIG = {
  employee:          { label: "Empleados",       color: "#3B82F6" },
  support_rag:       { label: "Base Conocimiento", color: "#8B5CF6" },
  server_validation: { label: "Servidores",       color: "#10B981" },
};

const PRIMARY = "#1E3A5F";

export default function ChatWidget({ position = "bottom-right", primaryColor = PRIMARY }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [imgPreview, setImgPreview] = useState(null);
  const [imgB64, setImgB64] = useState(null);
  const [imgMime, setImgMime] = useState(null);

  const { messages, loading, sendMessage, clearChat } = useChat();
  const bottomRef = useRef(null);
  const fileRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  const handleSend = async () => {
    if (!input.trim() && !imgB64) return;
    const t = input, b = imgB64, m = imgMime;
    setInput(""); setImgPreview(null); setImgB64(null); setImgMime(null);
    await sendMessage(t, b, m);
  };

  const handleKey = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } };

  const handleFile = (e) => {
    const f = e.target.files[0]; if (!f) return;
    const r = new FileReader();
    r.onload = (ev) => {
      setImgPreview(ev.target.result);
      setImgB64(ev.target.result.split(",")[1]);
      setImgMime(f.type);
    };
    r.readAsDataURL(f);
    e.target.value = "";
  };

  const posStyle = position === "bottom-left"
    ? { bottom: 24, left: 24 }
    : { bottom: 24, right: 24 };

  return (
    <div style={{ position: "fixed", zIndex: 9999, ...posStyle }}>
      {/* ── Panel del chat ── */}
      {open && (
        <div style={{
          width: 380, height: 580,
          background: "#fff", borderRadius: 16,
          boxShadow: "0 20px 60px rgba(0,0,0,0.18)",
          display: "flex", flexDirection: "column", overflow: "hidden",
          marginBottom: 14, border: "1px solid #E5E7EB",
          animation: "slideUp 0.2s ease",
        }}>
          {/* Header */}
          <div style={{ background: primaryColor, padding: "14px 18px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 36, height: 36, borderRadius: "50%", background: "rgba(255,255,255,0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Bot size={20} color="#fff" />
              </div>
              <div>
                <div style={{ color: "#fff", fontWeight: 700, fontSize: 15 }}>BOTIQ</div>
                <div style={{ color: "rgba(255,255,255,0.65)", fontSize: 11 }}>Asistente Corporativo IA</div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button onClick={clearChat} title="Limpiar chat"
                style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.6)", padding: 4, borderRadius: 4 }}>
                <RefreshCw size={15} />
              </button>
              <button onClick={() => setOpen(false)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.6)", padding: 4, borderRadius: 4 }}>
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div style={{ flex: 1, overflowY: "auto", padding: "14px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
            {messages.length === 0 && (
              <div style={{ textAlign: "center", color: "#9CA3AF", marginTop: 50 }}>
                <Bot size={44} style={{ margin: "0 auto 12px", opacity: 0.2 }} />
                <p style={{ fontWeight: 600, color: "#6B7280" }}>¡Hola! Soy BOTIQ</p>
                <p style={{ fontSize: 13, marginTop: 4 }}>¿En qué puedo ayudarte hoy?</p>
                <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 6 }}>
                  {["No puedo acceder al portal", "Error en Word/Excel", "¿Cómo solicito soporte?"].map(s => (
                    <button key={s} onClick={() => sendMessage(s)}
                      style={{ background: "#F3F4F6", border: "1px solid #E5E7EB", borderRadius: 20, padding: "6px 14px", fontSize: 12, cursor: "pointer", color: "#374151" }}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => <Bubble key={msg.id} msg={msg} primaryColor={primaryColor} />)}

            {loading && (
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <Avatar color={primaryColor}><Bot size={14} color="#fff" /></Avatar>
                <div style={{ background: "#F3F4F6", borderRadius: "4px 12px 12px 12px", padding: "10px 14px" }}>
                  <TypingDots />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Image preview */}
          {imgPreview && (
            <div style={{ padding: "6px 16px", background: "#F9FAFB", borderTop: "1px solid #E5E7EB" }}>
              <div style={{ position: "relative", display: "inline-block" }}>
                <img src={imgPreview} alt="preview" style={{ height: 56, borderRadius: 8, objectFit: "cover" }} />
                <button onClick={() => { setImgPreview(null); setImgB64(null); }}
                  style={{ position: "absolute", top: -6, right: -6, background: "#EF4444", border: "none", borderRadius: "50%", width: 18, height: 18, cursor: "pointer", color: "#fff", fontSize: 11, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  ×
                </button>
              </div>
            </div>
          )}

          {/* Input */}
          <div style={{ padding: "10px 14px", borderTop: "1px solid #E5E7EB", background: "#fff" }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
              <input ref={fileRef} type="file" accept="image/*" style={{ display: "none" }} onChange={handleFile} />
              <button onClick={() => fileRef.current?.click()} title="Adjuntar imagen"
                style={{ background: "none", border: "none", cursor: "pointer", color: "#9CA3AF", padding: 6, borderRadius: 6, flexShrink: 0 }}>
                <Paperclip size={18} />
              </button>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Escribe tu consulta..."
                rows={1}
                style={{
                  flex: 1, border: "1px solid #E5E7EB", borderRadius: 20,
                  padding: "8px 14px", fontSize: 14, resize: "none", outline: "none",
                  fontFamily: "inherit", maxHeight: 80, overflowY: "auto",
                  transition: "border-color 0.2s",
                }}
                onFocus={(e) => (e.target.style.borderColor = primaryColor)}
                onBlur={(e) => (e.target.style.borderColor = "#E5E7EB")}
              />
              <button
                onClick={handleSend}
                disabled={loading || (!input.trim() && !imgB64)}
                style={{
                  background: loading || (!input.trim() && !imgB64) ? "#D1D5DB" : primaryColor,
                  border: "none", borderRadius: "50%", width: 36, height: 36,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  cursor: loading || (!input.trim() && !imgB64) ? "not-allowed" : "pointer",
                  flexShrink: 0, transition: "background 0.2s",
                }}>
                <Send size={15} color="#fff" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Botón flotante ── */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: 56, height: 56, background: primaryColor,
          border: "none", borderRadius: "50%",
          display: "flex", alignItems: "center", justifyContent: "center",
          cursor: "pointer", boxShadow: "0 4px 20px rgba(0,0,0,0.25)",
          marginLeft: "auto", transition: "transform 0.2s, box-shadow 0.2s",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.transform = "scale(1.1)"; e.currentTarget.style.boxShadow = "0 6px 28px rgba(0,0,0,0.35)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.transform = "scale(1)"; e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,0,0,0.25)"; }}
      >
        {open ? <X size={22} color="#fff" /> : <MessageCircle size={22} color="#fff" />}
      </button>

      <style>{`
        @keyframes slideUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}

function Bubble({ msg, primaryColor }) {
  const isUser = msg.role === "user";
  const mod = MODULE_CONFIG[msg.meta?.module];
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexDirection: isUser ? "row-reverse" : "row" }}>
      <Avatar color={isUser ? "#E5E7EB" : primaryColor}>
        {isUser ? <User size={13} color="#6B7280" /> : <Bot size={13} color="#fff" />}
      </Avatar>
      <div style={{ maxWidth: "76%" }}>
        <div style={{
          background: isUser ? primaryColor : "#F3F4F6",
          color: isUser ? "#fff" : "#111827",
          borderRadius: isUser ? "12px 4px 12px 12px" : "4px 12px 12px 12px",
          padding: "9px 13px", fontSize: 14, lineHeight: 1.55, whiteSpace: "pre-wrap",
        }}>
          {msg.content}
        </div>
        {mod && (
          <div style={{ marginTop: 3, fontSize: 10, color: mod.color, display: "flex", alignItems: "center", gap: 3 }}>
            {msg.meta?.module === "support_rag" && <BookOpen size={10} />}
            {msg.meta?.module === "server_validation" && <Server size={10} />}
            {mod.label}
          </div>
        )}
        {msg.meta?.sources?.length > 0 && (
          <div style={{ marginTop: 2, fontSize: 10, color: "#9CA3AF" }}>
            📚 {msg.meta.sources.join(", ")}
          </div>
        )}
        {msg.meta?.escalated && (
          <div style={{ marginTop: 2, fontSize: 10, color: "#F59E0B", display: "flex", alignItems: "center", gap: 3 }}>
            <AlertTriangle size={10} /> Escalado a Aranda
          </div>
        )}
      </div>
    </div>
  );
}

function Avatar({ color, children }) {
  return (
    <div style={{ width: 28, height: 28, borderRadius: "50%", background: color, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
      {children}
    </div>
  );
}

function TypingDots() {
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center", height: 16 }}>
      {[0, 1, 2].map((i) => (
        <div key={i} style={{
          width: 6, height: 6, borderRadius: "50%", background: "#9CA3AF",
          animation: `dotBounce 1.2s ease-in-out ${i * 0.2}s infinite`,
        }} />
      ))}
      <style>{`@keyframes dotBounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-6px)}}`}</style>
    </div>
  );
}
