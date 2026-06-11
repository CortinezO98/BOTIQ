import { useState, useRef, useEffect } from "react";
import { useChat } from "../../hooks/useChat";
import { supportAPI } from "../../services/api";

const C = "#272163";
const CL = "#3a3490";

const MODULE_INFO = {
  employee:          { label: "General",          icon: "👤", color: "#059669" },
  support_rag:       { label: "Base Conocimiento",icon: "📚", color: "#7c3aed" },
  server_validation: { label: "Servidores",       icon: "🖥️", color: "#0284c7" },
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
  const taRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  useEffect(() => {
    if (open && messages.length === 0) {
      supportAPI.status().then(r => setKbStatus(r.data)).catch(() => {});
    }
  }, [open]);

  const send = async () => {
    if (!input.trim() && !imgFile) return;
    const t = input, f = imgFile;
    setInput(""); setImgFile(null); setImgPreview(null);
    await sendMessage(t, f);
  };

  const handleKey = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };

  const handleFile = e => {
    const f = e.target.files[0]; if (!f) return;
    if (f.size > 5 * 1024 * 1024) { alert("Imagen máx. 5MB"); return; }
    setImgFile(f);
    const r = new FileReader();
    r.onload = ev => setImgPreview(ev.target.result);
    r.readAsDataURL(f);
    e.target.value = "";
  };

  const pos = position === "bottom-left" ? { bottom: 24, left: 24 } : { bottom: 24, right: 24 };

  return (
    <div style={{ position: "fixed", zIndex: 9999, ...pos }}>
      {open && (
        <div style={{
          width: 390, height: 600,
          background: "#fff", borderRadius: 18,
          boxShadow: "0 24px 64px rgba(39,33,99,0.22)",
          display: "flex", flexDirection: "column", overflow: "hidden",
          marginBottom: 14, border: `1px solid ${C}22`,
          animation: "botiqSlide 0.25s ease",
        }}>
          {/* Header */}
          <div style={{
            background: `linear-gradient(135deg, ${C}, ${CL})`,
            padding: "14px 18px",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                width: 38, height: 38, borderRadius: "50%",
                background: "rgba(255,255,255,0.15)",
                border: "2px solid rgba(255,255,255,0.25)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <svg width="20" height="20" viewBox="0 0 40 40" fill="none">
                  <path d="M12 20 L20 12 L28 20 L20 28 Z" fill="rgba(255,255,255,0.3)" stroke="#fff" strokeWidth="1.5"/>
                  <circle cx="20" cy="20" r="4" fill="#fff"/>
                </svg>
              </div>
              <div>
                <div style={{ color: "#fff", fontWeight: 700, fontSize: 15 }}>BOTIQ</div>
                <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: "50%",
                    background: "#4ade80",
                    boxShadow: "0 0 6px #4ade80",
                    display: "inline-block",
                  }} />
                  <span style={{ color: "rgba(255,255,255,0.65)", fontSize: 11 }}>
                    Asistente IA disponible
                  </span>
                </div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 4 }}>
              <HBtn onClick={clearChat} title="Nueva conversación">↺</HBtn>
              <HBtn onClick={() => setOpen(false)} title="Cerrar">✕</HBtn>
            </div>
          </div>

          {/* KB status banner */}
          {kbStatus && !kbStatus.drive_configured && messages.length === 0 && (
            <div style={{
              background: "#fef3c7", borderBottom: "1px solid #fde68a",
              padding: "8px 16px", fontSize: 11, color: "#92400e",
              display: "flex", alignItems: "center", gap: 6,
            }}>
              ⚠️ Google Drive no conectado — Modo FAQ básico activo
            </div>
          )}

          {/* Messages */}
          <div style={{
            flex: 1, overflowY: "auto", padding: "14px 16px",
            display: "flex", flexDirection: "column", gap: 12,
          }}>
            {messages.length === 0 && (
              <div style={{ textAlign: "center", paddingTop: 20 }}>
                <div style={{
                  width: 56, height: 56, background: `${C}12`, borderRadius: "50%",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  margin: "0 auto 14px",
                }}>
                  <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
                    <path d="M12 20 L20 12 L28 20 L20 28 Z" fill={`${C}40`} stroke={C} strokeWidth="2"/>
                    <circle cx="20" cy="20" r="4" fill={C}/>
                  </svg>
                </div>
                <p style={{ fontWeight: 600, color: C, fontSize: 15, marginBottom: 4 }}>
                  Hola, soy BOTIQ
                </p>
                <p style={{ color: "#6b6b8a", fontSize: 12, marginBottom: 16 }}>
                  ¿En qué puedo ayudarte hoy?
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  {QUICK_QUESTIONS.map(q => (
                    <button key={q} onClick={() => sendMessage(q)} style={{
                      background: `${C}08`, border: `1px solid ${C}25`,
                      borderRadius: 20, padding: "7px 14px", fontSize: 12,
                      cursor: "pointer", color: C, fontWeight: 500,
                      transition: "all 0.2s",
                    }}
                      onMouseEnter={e => { e.currentTarget.style.background = `${C}15`; e.currentTarget.style.borderColor = `${C}50`; }}
                      onMouseLeave={e => { e.currentTarget.style.background = `${C}08`; e.currentTarget.style.borderColor = `${C}25`; }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map(msg => <Bubble key={msg.id} msg={msg} primaryColor={primaryColor} />)}

            {loading && (
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <Ava color={primaryColor} size={28}>
                  <svg width="14" height="14" viewBox="0 0 40 40" fill="none">
                    <path d="M12 20 L20 12 L28 20 L20 28 Z" fill="rgba(255,255,255,0.4)" stroke="#fff" strokeWidth="2"/>
                    <circle cx="20" cy="20" r="4" fill="#fff"/>
                  </svg>
                </Ava>
                <div style={{ background: "#f5f5fa", borderRadius: "4px 12px 12px 12px", padding: "10px 14px" }}>
                  <Typing />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Img preview */}
          {imgPreview && (
            <div style={{ padding: "6px 14px", background: "#f9f9fc", borderTop: `1px solid ${C}15` }}>
              <div style={{ position: "relative", display: "inline-block" }}>
                <img src={imgPreview} alt="" style={{ height: 54, borderRadius: 8, objectFit: "cover", border: `2px solid ${C}30` }} />
                <button onClick={() => { setImgFile(null); setImgPreview(null); }} style={{
                  position: "absolute", top: -7, right: -7,
                  background: "#dc2626", border: "none", borderRadius: "50%",
                  width: 19, height: 19, cursor: "pointer", color: "#fff",
                  fontSize: 11, display: "flex", alignItems: "center", justifyContent: "center",
                }}>✕</button>
              </div>
            </div>
          )}

          {/* Input */}
          <div style={{ padding: "10px 14px", borderTop: `1px solid ${C}15`, background: "#fff" }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 7 }}>
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp"
                style={{ display: "none" }} onChange={handleFile} />
              <button onClick={() => fileRef.current?.click()} title="Adjuntar imagen" style={{
                background: "none", border: "none", cursor: "pointer",
                color: "#9CA3AF", padding: 6, flexShrink: 0, fontSize: 18,
                transition: "color 0.2s",
              }}
                onMouseEnter={e => e.currentTarget.style.color = C}
                onMouseLeave={e => e.currentTarget.style.color = "#9CA3AF"}
              >📎</button>
              <textarea
                ref={taRef} value={input}
                onChange={e => setInput(e.target.value)} onKeyDown={handleKey}
                placeholder="Escribe tu consulta..."
                rows={1}
                style={{
                  flex: 1, border: `1.5px solid ${C}20`, borderRadius: 18,
                  padding: "9px 13px", fontSize: 13, resize: "none", outline: "none",
                  fontFamily: "inherit", maxHeight: 80, overflowY: "auto",
                  background: "#fafafa", transition: "border-color 0.2s, box-shadow 0.2s",
                }}
                onFocus={e => { e.target.style.borderColor = C; e.target.style.boxShadow = `0 0 0 3px ${C}12`; e.target.style.background = "#fff"; }}
                onBlur={e => { e.target.style.borderColor = `${C}20`; e.target.style.boxShadow = "none"; e.target.style.background = "#fafafa"; }}
              />
              <button onClick={send} disabled={loading || (!input.trim() && !imgFile)} style={{
                background: loading || (!input.trim() && !imgFile) ? "#d1d5db" : `linear-gradient(135deg, ${C}, ${CL})`,
                border: "none", borderRadius: "50%", width: 36, height: 36,
                display: "flex", alignItems: "center", justifyContent: "center",
                cursor: loading || (!input.trim() && !imgFile) ? "not-allowed" : "pointer",
                flexShrink: 0, transition: "all 0.2s", fontSize: 15,
                boxShadow: loading || (!input.trim() && !imgFile) ? "none" : `0 2px 8px ${C}50`,
              }}>▶</button>
            </div>
          </div>
        </div>
      )}

      {/* Botón flotante */}
      <button onClick={() => setOpen(v => !v)} style={{
        width: 56, height: 56,
        background: `linear-gradient(135deg, ${C}, ${CL})`,
        border: "none", borderRadius: "50%",
        display: "flex", alignItems: "center", justifyContent: "center",
        cursor: "pointer", marginLeft: "auto",
        boxShadow: `0 4px 20px ${C}55`,
        transition: "transform 0.2s, box-shadow 0.2s",
      }}
        onMouseEnter={e => { e.currentTarget.style.transform = "scale(1.1)"; e.currentTarget.style.boxShadow = `0 6px 28px ${C}70`; }}
        onMouseLeave={e => { e.currentTarget.style.transform = "scale(1)"; e.currentTarget.style.boxShadow = `0 4px 20px ${C}55`; }}
      >
        {open
          ? <span style={{ color: "#fff", fontSize: 20 }}>✕</span>
          : (
            <svg width="24" height="24" viewBox="0 0 40 40" fill="none">
              <path d="M12 20 L20 12 L28 20 L20 28 Z" fill="rgba(255,255,255,0.3)" stroke="#fff" strokeWidth="2"/>
              <circle cx="20" cy="20" r="4" fill="#fff"/>
              <path d="M20 8 L20 12 M20 28 L20 32 M8 20 L12 20 M28 20 L32 20" stroke="#fff" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          )
        }
      </button>
      <style>{`
        @keyframes botiqSlide { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:translateY(0); } }
      `}</style>
    </div>
  );
}

function Bubble({ msg, primaryColor }) {
  const isUser = msg.role === "user";
  const mod = MODULE_INFO[msg.meta?.module];
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexDirection: isUser ? "row-reverse" : "row" }}>
      <Ava color={isUser ? "#e2e1f0" : primaryColor} size={28}>
        {isUser
          ? <span style={{ fontSize: 12 }}>👤</span>
          : <svg width="13" height="13" viewBox="0 0 40 40" fill="none">
              <path d="M12 20 L20 12 L28 20 L20 28 Z" fill="rgba(255,255,255,0.4)" stroke="#fff" strokeWidth="2"/>
              <circle cx="20" cy="20" r="4" fill="#fff"/>
            </svg>
        }
      </Ava>
      <div style={{ maxWidth: "78%" }}>
        <div style={{
          background: isUser
            ? `linear-gradient(135deg, ${primaryColor}, ${primaryColor}dd)`
            : msg.meta?.isError ? "#fef2f2" : "#f5f5fa",
          color: isUser ? "#fff" : msg.meta?.isError ? "#dc2626" : "#1a1a2e",
          borderRadius: isUser ? "14px 4px 14px 14px" : "4px 14px 14px 14px",
          padding: "10px 14px", fontSize: 13, lineHeight: 1.6, whiteSpace: "pre-wrap",
          boxShadow: isUser ? `0 2px 8px ${primaryColor}30` : "0 1px 3px rgba(0,0,0,0.06)",
        }}>
          {msg.content}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>
          {mod && !isUser && (
            <span style={{ fontSize: 10, color: mod.color, display: "flex", alignItems: "center", gap: 2 }}>
              {mod.icon} {mod.label}
            </span>
          )}
          {msg.meta?.sources?.length > 0 && (
            <span style={{ fontSize: 10, color: "#6b6b8a" }}>📄 {msg.meta.sources.slice(0,2).join(", ")}</span>
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
    <div style={{
      width: size, height: size, borderRadius: "50%", background: color,
      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
    }}>
      {children}
    </div>
  );
}

function HBtn({ onClick, title, children }) {
  return (
    <button onClick={onClick} title={title} style={{
      background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.2)",
      color: "rgba(255,255,255,0.7)", width: 28, height: 28, borderRadius: 7,
      cursor: "pointer", fontSize: 14,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      {children}
    </button>
  );
}

function Typing() {
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center", height: 14 }}>
      {[0,1,2].map(i => (
        <div key={i} style={{
          width: 5, height: 5, borderRadius: "50%", background: "#9CA3AF",
          animation: `tDot 1.2s ease-in-out ${i*0.2}s infinite`,
        }} />
      ))}
      <style>{`@keyframes tDot{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-5px)}}`}</style>
    </div>
  );
}
