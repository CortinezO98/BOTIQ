import { useState, useRef, useEffect } from "react";
import { MessageCircle, X, Send, Paperclip, Bot, User, AlertTriangle,
  BookOpen, Server, RefreshCw, Brain } from "lucide-react";
import { useChat } from "../../hooks/useChat";

const MODULE_CONFIG = {
  employee:          { label: "Empleados",         color: "#3B82F6" },
  support_rag:       { label: "Base Conocimiento", color: "#8B5CF6" },
  server_validation: { label: "Servidores",        color: "#10B981" },
};
const PRIMARY = "#1E3A5F";

export default function ChatWidget({ position = "bottom-right", primaryColor = PRIMARY }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [imageFile, setImageFile] = useState(null);
  const [imgPreview, setImgPreview] = useState(null);

  const { messages, loading, sendMessage, clearChat } = useChat();
  const bottomRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  const handleSend = async () => {
    if (!input.trim() && !imageFile) return;
    const t = input, f = imageFile;
    setInput(""); setImageFile(null); setImgPreview(null);
    await sendMessage(t, f);
  };

  const handleKey = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } };

  const handleFile = (e) => {
    const f = e.target.files[0]; if (!f) return;
    // Validar tamaño en frontend también
    if (f.size > 5 * 1024 * 1024) {
      alert("La imagen no puede superar 5MB"); return;
    }
    setImageFile(f);
    const reader = new FileReader();
    reader.onload = (ev) => setImgPreview(ev.target.result);
    reader.readAsDataURL(f);
    e.target.value = "";
  };

  const posStyle = position === "bottom-left" ? { bottom: 24, left: 24 } : { bottom: 24, right: 24 };

  return (
    <div style={{ position: "fixed", zIndex: 9999, ...posStyle }}>
      {open && (
        <div style={{ width: 380, height: 590, background: "#fff", borderRadius: 16,
          boxShadow: "0 20px 60px rgba(0,0,0,0.18)", display: "flex", flexDirection: "column",
          overflow: "hidden", marginBottom: 14, border: "1px solid #E5E7EB",
          animation: "slideUp 0.2s ease" }}>

          {/* Header */}
          <div style={{ background: primaryColor, padding: "13px 18px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 34, height: 34, borderRadius: "50%", background: "rgba(255,255,255,0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Bot size={18} color="#fff" />
              </div>
              <div>
                <div style={{ color: "#fff", fontWeight: 700, fontSize: 14 }}>BOTIQ</div>
                <div style={{ color: "rgba(255,255,255,0.6)", fontSize: 10 }}>Asistente Corporativo IA</div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 4 }}>
              <Btn onClick={clearChat} title="Nueva conversación"><RefreshCw size={14} /></Btn>
              <Btn onClick={() => setOpen(false)} title="Cerrar"><X size={16} /></Btn>
            </div>
          </div>

          {/* Messages */}
          <div style={{ flex: 1, overflowY: "auto", padding: "14px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
            {messages.length === 0 && (
              <div style={{ textAlign: "center", color: "#9CA3AF", marginTop: 40 }}>
                <Bot size={42} style={{ margin: "0 auto 12px", opacity: 0.2 }} />
                <p style={{ fontWeight: 600, color: "#6B7280", fontSize: 15 }}>¡Hola! Soy BOTIQ</p>
                <p style={{ fontSize: 12, marginTop: 4 }}>¿En qué puedo ayudarte?</p>
                <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 6 }}>
                  {["No puedo acceder al portal", "Error en Word/Excel", "¿Cómo solicito soporte?"].map((s) => (
                    <button key={s} onClick={() => sendMessage(s)}
                      style={{ background: "#F3F4F6", border: "1px solid #E5E7EB", borderRadius: 20,
                        padding: "6px 14px", fontSize: 12, cursor: "pointer", color: "#374151" }}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => <Bubble key={msg.id} msg={msg} primaryColor={primaryColor} />)}

            {loading && (
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <Ava color={primaryColor}><Bot size={13} color="#fff" /></Ava>
                <div style={{ background: "#F3F4F6", borderRadius: "4px 12px 12px 12px", padding: "10px 14px" }}>
                  <TypingDots />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Image preview */}
          {imgPreview && (
            <div style={{ padding: "6px 14px", background: "#F9FAFB", borderTop: "1px solid #E5E7EB" }}>
              <div style={{ position: "relative", display: "inline-block" }}>
                <img src={imgPreview} alt="preview" style={{ height: 52, borderRadius: 7, objectFit: "cover" }} />
                <button onClick={() => { setImageFile(null); setImgPreview(null); }}
                  style={{ position: "absolute", top: -6, right: -6, background: "#EF4444", border: "none",
                    borderRadius: "50%", width: 18, height: 18, cursor: "pointer", color: "#fff", fontSize: 11,
                    display: "flex", alignItems: "center", justifyContent: "center" }}>×</button>
              </div>
            </div>
          )}

          {/* Input */}
          <div style={{ padding: "10px 14px", borderTop: "1px solid #E5E7EB" }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 6 }}>
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp"
                style={{ display: "none" }} onChange={handleFile} />
              <button onClick={() => fileRef.current?.click()} title="Adjuntar imagen"
                style={{ background: "none", border: "none", cursor: "pointer", color: "#9CA3AF", padding: 6, flexShrink: 0 }}>
                <Paperclip size={17} />
              </button>
              <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKey}
                placeholder="Escribe tu consulta..." rows={1}
                style={{ flex: 1, border: "1px solid #E5E7EB", borderRadius: 18, padding: "8px 13px",
                  fontSize: 13, resize: "none", outline: "none", fontFamily: "inherit",
                  maxHeight: 75, overflowY: "auto" }}
                onFocus={(e) => (e.target.style.borderColor = primaryColor)}
                onBlur={(e) => (e.target.style.borderColor = "#E5E7EB")} />
              <button onClick={handleSend} disabled={loading || (!input.trim() && !imageFile)}
                style={{ background: loading || (!input.trim() && !imageFile) ? "#D1D5DB" : primaryColor,
                  border: "none", borderRadius: "50%", width: 34, height: 34,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  cursor: loading || (!input.trim() && !imageFile) ? "not-allowed" : "pointer", flexShrink: 0 }}>
                <Send size={14} color="#fff" />
              </button>
            </div>
          </div>
        </div>
      )}

      <button onClick={() => setOpen((v) => !v)}
        style={{ width: 54, height: 54, background: primaryColor, border: "none", borderRadius: "50%",
          display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer",
          boxShadow: "0 4px 20px rgba(0,0,0,0.25)", marginLeft: "auto", transition: "transform 0.2s" }}
        onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.08)")}
        onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}>
        {open ? <X size={21} color="#fff" /> : <MessageCircle size={21} color="#fff" />}
      </button>
      <style>{`@keyframes slideUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}`}</style>
    </div>
  );
}

function Bubble({ msg, primaryColor }) {
  const isUser = msg.role === "user";
  const mod = MODULE_CONFIG[msg.meta?.module];
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexDirection: isUser ? "row-reverse" : "row" }}>
      <Ava color={isUser ? "#E5E7EB" : primaryColor}>
        {isUser ? <User size={12} color="#6B7280" /> : <Bot size={12} color="#fff" />}
      </Ava>
      <div style={{ maxWidth: "77%" }}>
        <div style={{ background: isUser ? primaryColor : msg.meta?.isError ? "#FEF2F2" : "#F3F4F6",
          color: isUser ? "#fff" : msg.meta?.isError ? "#DC2626" : "#111827",
          borderRadius: isUser ? "12px 4px 12px 12px" : "4px 12px 12px 12px",
          padding: "9px 13px", fontSize: 13, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>
          {msg.content}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 3 }}>
          {mod && (
            <span style={{ fontSize: 10, color: mod.color, display: "flex", alignItems: "center", gap: 2 }}>
              {msg.meta?.module === "support_rag" && <BookOpen size={9} />}
              {msg.meta?.module === "server_validation" && <Server size={9} />}
              {mod.label}
            </span>
          )}
          {msg.meta?.sources?.length > 0 && (
            <span style={{ fontSize: 10, color: "#9CA3AF" }}>📚 {msg.meta.sources.slice(0, 2).join(", ")}</span>
          )}
          {msg.meta?.escalated && (
            <span style={{ fontSize: 10, color: "#F59E0B", display: "flex", alignItems: "center", gap: 2 }}>
              <AlertTriangle size={9} /> Escalado a Aranda
            </span>
          )}
          {msg.meta?.knowledgeGap && (
            <span style={{ fontSize: 10, color: "#8B5CF6", display: "flex", alignItems: "center", gap: 2 }}>
              <Brain size={9} /> Brecha de conocimiento detectada
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function Ava({ color, children }) {
  return (
    <div style={{ width: 27, height: 27, borderRadius: "50%", background: color,
      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
      {children}
    </div>
  );
}

function Btn({ onClick, title, children }) {
  return (
    <button onClick={onClick} title={title}
      style={{ background: "none", border: "none", cursor: "pointer",
        color: "rgba(255,255,255,0.65)", padding: 4, borderRadius: 4,
        display: "flex", alignItems: "center", justifyContent: "center" }}>
      {children}
    </button>
  );
}

function TypingDots() {
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center", height: 15 }}>
      {[0, 1, 2].map((i) => (
        <div key={i} style={{ width: 5, height: 5, borderRadius: "50%", background: "#9CA3AF",
          animation: `db 1.2s ease-in-out ${i * 0.2}s infinite` }} />
      ))}
      <style>{`@keyframes db{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-5px)}}`}</style>
    </div>
  );
}
