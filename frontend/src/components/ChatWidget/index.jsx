import { useEffect, useRef, useState } from "react";
import { useChat } from "../../hooks/useChat";
import { healthAPI, supportAPI } from "../../services/api";
import BotiqAvatar from "../Brand/BotiqAvatar";
import BotiqBotIcon from "../Brand/BotiqBotIcon";

const C = "#272163";
const CL = "#3a3490";

const MODULE_INFO = {
  employee: { label: "Empleado", icon: "👤", color: "#059669" },
  support_rag: { label: "Base Conocimiento", icon: "📚", color: "#7c3aed" },
  server_validation: { label: "Servidores", icon: "🖥️", color: "#0284c7" },
};

// Fuente real de cada respuesta (audit UX: "Chip de color distinto por
// fuente"). Viene de ChatMessageResponse.answer_source (respuesta en vivo)
// o de Message.metadata_.answer_source (historial cargado) — ver
// _determine_answer_source() en chat.py.
const ANSWER_SOURCE_INFO = {
  faq: { label: "FAQ", icon: "❓", variant: "success" },
  rag: { label: "Base de conocimiento", icon: "📚", variant: "info" },
  matrix: { label: "Matriz interna", icon: "🗂️", variant: "info" },
  web_approved: { label: "Web aprobado", icon: "✅", variant: "success" },
  web_pending: { label: "Web (pendiente aprobación)", icon: "🌐", variant: "warning" },
  general_ai: { label: "IA general", icon: "🤖", variant: "purple" },
};

const QUICK_EMPLOYEE = [];

const QUICK_SUPPORT = [];

export default function ChatWidget({ position = "bottom-right", primaryColor = C, embedded = false }) {
  const [open, setOpen] = useState(embedded);
  const [input, setInput] = useState("");
  const [imgFile, setImgFile] = useState(null);
  const [imgPreview, setImgPreview] = useState(null);
  const [kbStatus, setKbStatus] = useState(null);
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [networkUsername, setNetworkUsername] = useState("");
  const [profileError, setProfileError] = useState("");
  const [showSatisfaction, setShowSatisfaction] = useState(false);
  const [aiAvailable, setAiAvailable] = useState(true);

  const {
    messages,
    loading,
    session,
    sessionStatus,
    startSession,
    sendMessage,
    clearChat,
    submitFeedback,
    submitSatisfaction,
  } = useChat();

  const bottomRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (open) {
      supportAPI.status().then((r) => setKbStatus(r.data)).catch(() => {});
      // Verificar disponibilidad de Vertex AI. Antes esto era
      // fetch("/health") -- una URL relativa que apuntaba al origen del
      // frontend, no al backend, así que este chequeo nunca funcionó de
      // verdad (ver healthAPI.check() en services/api.js).
      healthAPI
        .check()
        .then((r) => setAiAvailable(r.data.ai_available !== false))
        .catch(() => setAiAvailable(true)); // asumir disponible si falla el check
    }
  }, [open]);

  const resetLocalFlow = async () => {
    // Si hay una sesión activa con mensajes, mostrar encuesta de satisfacción primero
    if (session && messages.length > 1) {
      setShowSatisfaction(true);
      return;
    }
    await _doReset();
  };

  const _doReset = async () => {
    await clearChat();
    setSelectedProfile(null);
    setNetworkUsername("");
    setProfileError("");
    setInput("");
    setImgFile(null);
    setImgPreview(null);
    setShowSatisfaction(false);
  };

  const handleSatisfaction = async (score, comment) => {
    await submitSatisfaction(score, comment);
    await _doReset();
  };

  const configureProfile = async (profile) => {
    setProfileError("");
    setSelectedProfile(profile);
    try {
      await startSession({
        selected_profile: profile,
        network_username: profile === "support_engineer" ? networkUsername.trim() : undefined,
      });
    } catch (error) {
      setProfileError(error.message);
    }
  };

  const configureSupport = async () => {
    if (!networkUsername.trim()) {
      setProfileError("Ingresa tu usuario de red para validar el perfil de soporte.");
      return;
    }
    await configureProfile("support_engineer");
  };

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

  const pos = position === "bottom-left" ? { bottom: 22, left: 22 } : { bottom: 22, right: 22 };
  const fixedStyle = {
    ...pos,
    position: "fixed",
    zIndex: 2147483000,
    display: "flex",
    flexDirection: "column",
    alignItems: position === "bottom-left" ? "flex-start" : "flex-end",
    pointerEvents: "none",
  };
  const quickQuestions = session?.selected_profile === "support_engineer" ? QUICK_SUPPORT : QUICK_EMPLOYEE;

  const content = (
    <div
      className={embedded ? "botiq-chat-panel botiq-chat-panel--embedded" : "botiq-chat-panel animate__animated animate__fadeInUp"}
      style={{
        width: embedded ? "100%" : "min(420px, calc(100vw - 24px))",
        height: embedded ? "calc(100vh - 58px)" : "min(660px, calc(100vh - 108px))",
        background: "var(--botiq-card-bg)",
        borderRadius: embedded ? 0 : 20,
        boxShadow: embedded ? "none" : "0 24px 72px rgba(39,33,99,0.26)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        marginBottom: embedded ? 0 : 14,
        border: embedded ? "none" : `1px solid ${primaryColor}22`,
        animation: embedded ? "none" : "botiqSlide 0.25s ease",
      }}
    >
      <Header
        primaryColor={primaryColor}
        onReset={resetLocalFlow}
        onClose={() => setOpen(false)}
        showClose={!embedded}
      />

      {kbStatus && !kbStatus.drive_configured && messages.length === 0 && (
        <div style={warningBanner}>
          ⚠️ Google Drive no conectado — modo FAQ básico activo.
        </div>
      )}

      {!aiAvailable && (
        <div
          className="botiq-clay-chip botiq-clay-chip--warning botiq-clay-chip--inset botiq-clay-badge-pulse"
          style={{ margin: "8px 12px 0", alignSelf: "flex-start" }}
          title="Vertex AI no está disponible en este momento. BOTIQ sigue respondiendo con FAQs y base de conocimiento, pero sin generación de IA."
        >
          🟡 Modo degradado — respuestas básicas
        </div>
      )}

      <div className="botiq-chat-content">
        {!session && (
          <ProfileSelector
            selectedProfile={selectedProfile}
            networkUsername={networkUsername}
            setNetworkUsername={setNetworkUsername}
            configureProfile={configureProfile}
            configureSupport={configureSupport}
            loading={loading}
            error={profileError}
            primaryColor={primaryColor}
          />
        )}

        {session && <SessionBanner session={session} status={sessionStatus} />}

        {session && messages.map((msg) => (
          <Bubble
            key={msg.id}
            msg={msg}
            primaryColor={primaryColor}
            onFeedback={(rating) => submitFeedback(msg.id, rating)}
          />
        ))}

        {session && quickQuestions.length > 0 && messages.length <= 1 && !loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            {quickQuestions.map((question) => (
              <button key={question} onClick={() => sendMessage(question)} style={quickBtn(primaryColor)}>
                {question}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            <BotiqAvatar size={28} color={primaryColor} />
            <div style={{ background: "var(--botiq-surface)", borderRadius: "4px 12px 12px 12px", padding: "10px 14px" }}>
              <Typing />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {showSatisfaction && (
        <SatisfactionModal
          primaryColor={primaryColor}
          onSubmit={handleSatisfaction}
          onSkip={_doReset}
        />
      )}

      {session && imgPreview && (
        <div style={{ padding: "6px 14px", background: "#f9f9fc", borderTop: `1px solid ${primaryColor}15` }}>
          <div style={{ position: "relative", display: "inline-block" }}>
            <img src={imgPreview} alt="" style={{ height: 54, borderRadius: 8, objectFit: "cover", border: `2px solid ${primaryColor}30` }} />
            <button onClick={() => { setImgFile(null); setImgPreview(null); }} style={closeImageBtn}>✕</button>
          </div>
        </div>
      )}

      {session && (
        <Composer
          input={input}
          setInput={setInput}
          send={send}
          handleKey={handleKey}
          fileRef={fileRef}
          handleFile={handleFile}
          loading={loading}
          imgFile={imgFile}
          disabled={sessionStatus !== "active"}
          primaryColor={primaryColor}
        />
      )}
    </div>
  );

  if (embedded) return content;

  return (
    <div className="botiq-chat-fixed" style={fixedStyle}>
      {open && <div style={{ pointerEvents: "auto" }}>{content}</div>}

      <button
        onClick={() => setOpen((value) => !value)}
        className="botiq-chat-float-button" style={{ ...floatBtn(primaryColor), pointerEvents: "auto" }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = "scale(1.08)";
          e.currentTarget.style.boxShadow = `0 7px 30px ${primaryColor}75`;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = "scale(1)";
          e.currentTarget.style.boxShadow = `0 5px 24px ${primaryColor}60`;
        }}
        title={open ? "Cerrar BOTIQ" : "Abrir BOTIQ"}
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

function Header({ primaryColor, onReset, onClose, showClose }) {
  return (
    <div style={{ background: `linear-gradient(135deg, ${primaryColor}, ${CL})`, padding: "14px 18px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <BotiqAvatar size={40} color={primaryColor} online />
        <div>
          <div style={{ color: "#fff", fontWeight: 800, fontSize: 15 }}>BOTIQ</div>
          <div style={{ color: "rgba(255,255,255,0.68)", fontSize: 11 }}>Asistente IA corporativo</div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 5 }}>
        <HBtn onClick={onReset} title="Nueva conversación">↺</HBtn>
        {showClose && <HBtn onClick={onClose} title="Cerrar">✕</HBtn>}
      </div>
    </div>
  );
}

function ProfileSelector({
  selectedProfile,
  networkUsername,
  setNetworkUsername,
  configureProfile,
  configureSupport,
  loading,
  error,
  primaryColor,
}) {
  return (
    <div style={{ textAlign: "center", padding: "22px 6px" }}>
      <div style={{ display: "flex", justifyContent: "center", marginBottom: 14 }}>
        <BotiqAvatar size={64} color={primaryColor} online />
      </div>

      <p style={{ fontWeight: 800, color: primaryColor, fontSize: 16, marginBottom: 6 }}>
        Antes de iniciar
      </p>

      <p style={{ color: "var(--botiq-muted)", fontSize: 12, marginBottom: 16, lineHeight: 1.6 }}>
        Indícame tu perfil para configurar el flujo conversacional, las fuentes de conocimiento y los controles de uso de IA.
      </p>

      <div className="botiq-profile-options">
        <button disabled={loading} onClick={() => configureProfile("employee")} style={profileBtn(primaryColor, selectedProfile === "employee")}>
          👤<br />Empleado
          <span style={profileSub}>FAQs, aplicativos, URLs</span>
        </button>
        <button disabled={loading} onClick={() => document.querySelector('input[placeholder="ej: jose.cortez"]')?.focus()} style={profileBtn(primaryColor, selectedProfile === "support_engineer")}>
          🛠️<br />Ing. Soporte
          <span style={profileSub}>RAG, PDFs, servidores</span>
        </button>
      </div>

      <div style={{ marginTop: 14, textAlign: "left" }}>
        <label style={{ fontSize: 11, color: "#374151", fontWeight: 700 }}>
          Usuario de red para soporte
        </label>
        <input
          value={networkUsername}
          onChange={(e) => setNetworkUsername(e.target.value)}
          placeholder="ej: jose.cortez"
          style={{ width: "100%", marginTop: 6, border: `1px solid ${primaryColor}25`, borderRadius: 10, padding: "9px 11px", outline: "none", fontSize: 13 }}
        />
        <button disabled={loading} onClick={configureSupport} style={{ marginTop: 10, width: "100%", background: `linear-gradient(135deg, ${primaryColor}, #3a3490)`, color: "#fff", border: "none", borderRadius: 10, padding: "10px 12px", cursor: loading ? "not-allowed" : "pointer", fontWeight: 800 }}>
          Validar e iniciar como soporte
        </button>
      </div>

      <div style={{ marginTop: 14, fontSize: 11, color: "var(--botiq-muted)", lineHeight: 1.5 }}>
        BOTIQ registra logs de conversación, limita preguntas por sesión y bloquea temas fuera del negocio.
      </div>

      {error && (
        <div style={{ marginTop: 12, background: "#fef2f2", color: "#991b1b", border: "1px solid #fecaca", borderRadius: 10, padding: 10, fontSize: 12 }}>
          {error}
        </div>
      )}
    </div>
  );
}

function SessionBanner({ session, status }) {
  const profile = session.selected_profile === "support_engineer" ? "Ingeniero de Soporte" : "Empleado";
  const color = status === "active" ? "#059669" : status === "blocked" ? "#dc2626" : "var(--botiq-muted)";
  const used = session.question_count || 0;
  const max = session.max_questions || 0;
  const remaining = Math.max(max - used, 0);

  return (
    <div style={{ background: "var(--botiq-surface)", border: "1px solid var(--botiq-border)", borderRadius: 12, padding: 10, fontSize: 11, color: "#374151" }}>
      <strong>{profile}</strong> · Estado: <span style={{ color, fontWeight: 800 }}>{status}</span> · Restantes: {remaining}/{max}
      {session.ticket_eligible && (
        <div style={{ marginTop: 6, color: "#d97706", fontWeight: 800 }}>
          Ticket Aranda elegible como última instancia.
        </div>
      )}
      {session.aranda_ticket_id && (
        <div style={{ marginTop: 6, color: "#059669", fontWeight: 800 }}>
          Ticket: {session.aranda_ticket_id}
        </div>
      )}
    </div>
  );
}

function Composer({ input, setInput, send, handleKey, fileRef, handleFile, loading, imgFile, disabled, primaryColor }) {
  return (
    <div style={{ padding: "10px 14px", borderTop: `1px solid ${primaryColor}15`, background: "var(--botiq-card-bg)" }}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 7 }}>
        <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" style={{ display: "none" }} onChange={handleFile} />

        <button disabled={disabled} onClick={() => fileRef.current?.click()} title="Adjuntar imagen" style={{ background: "none", border: "none", cursor: disabled ? "not-allowed" : "pointer", color: "#9ca3af", padding: 6, fontSize: 18 }}>
          📎
        </button>

        <textarea
          value={input}
          disabled={disabled}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder={disabled ? "Sesión finalizada" : "Escribe tu consulta corporativa..."}
          rows={1}
          style={{ flex: 1, border: `1.5px solid ${primaryColor}20`, borderRadius: 18, padding: "9px 13px", fontSize: 13, resize: "none", outline: "none", maxHeight: 80, background: disabled ? "var(--botiq-surface)" : "#fafafa" }}
        />

        <button
          onClick={send}
          disabled={disabled || loading || (!input.trim() && !imgFile)}
          style={{
            background: disabled || loading || (!input.trim() && !imgFile) ? "#d1d5db" : `linear-gradient(135deg, ${primaryColor}, #3a3490)`,
            border: "none",
            borderRadius: "50%",
            width: 36,
            height: 36,
            cursor: disabled || loading || (!input.trim() && !imgFile) ? "not-allowed" : "pointer",
            color: "#fff",
          }}
        >
          ▶
        </button>
      </div>
    </div>
  );
}

function Bubble({ msg, primaryColor, onFeedback }) {
  const isUser = msg.role === "user";
  const mod = MODULE_INFO[msg.meta?.module];
  const answerSourceInfo = ANSWER_SOURCE_INFO[msg.meta?.answerSource];
  const rated = msg.meta?.userRating;

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexDirection: isUser ? "row-reverse" : "row" }}>
      {isUser ? <Ava color="var(--botiq-border)" size={28}>👤</Ava> : <BotiqAvatar size={28} color={primaryColor} />}

      <div style={{ maxWidth: "78%" }}>
        <div
          className="botiq-chat-bubble-text"
          style={{
            background: isUser ? `linear-gradient(135deg, ${primaryColor}, ${primaryColor}dd)` : msg.meta?.isError ? "#fef2f2" : msg.meta?.system ? "#eef2ff" : "var(--botiq-surface)",
            color: isUser ? "#fff" : msg.meta?.isError ? "#dc2626" : "var(--botiq-text)",
            borderRadius: isUser ? "14px 4px 14px 14px" : "4px 14px 14px 14px",
            padding: "10px 14px",
            fontSize: 13,
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
          }}
        >
          {msg.content}
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4, alignItems: "center" }}>
          {answerSourceInfo && !isUser && (
            <span className={`botiq-clay-chip botiq-clay-chip--${answerSourceInfo.variant}`}>
              {answerSourceInfo.icon} {answerSourceInfo.label}
            </span>
          )}
          {mod && !isUser && <Meta color={mod.color}>{mod.icon} {mod.label}</Meta>}
          {msg.meta?.questionCount !== undefined && <Meta>{msg.meta.questionCount}/{msg.meta.maxQuestions} preguntas</Meta>}
          {msg.meta?.applicationStatus && <Meta color="#0284c7">🔎 estado consultado</Meta>}
          {msg.meta?.sources?.length > 0 && <Meta>📄 {msg.meta.sources.slice(0, 2).join(", ")}</Meta>}
          {msg.meta?.knowledgeGap && <Meta color="#7c3aed">🧠 brecha detectada</Meta>}
          {msg.meta?.ticketEligible && <Meta color="#d97706">🎫 ticket elegible</Meta>}
          {msg.meta?.arandaTicketId && <Meta color="#059669">Aranda: {msg.meta.arandaTicketId}</Meta>}
          {msg.meta?.sessionStatus && msg.meta.sessionStatus !== "active" && <Meta color="#dc2626">Sesión finalizada</Meta>}

          {/* Botones 👍/👎 — solo en mensajes del asistente no-sistema */}
          {!isUser && !msg.meta?.system && onFeedback && (
            <div style={{ display: "flex", gap: 3, marginLeft: "auto" }}>
              <button
                title="Útil"
                onClick={() => onFeedback("up")}
                style={{
                  background: rated === "up" ? "#d1fae5" : "transparent",
                  border: `1px solid ${rated === "up" ? "#059669" : "#e5e7eb"}`,
                  borderRadius: 6,
                  padding: "2px 6px",
                  cursor: "pointer",
                  fontSize: 13,
                  color: rated === "up" ? "#059669" : "#9ca3af",
                  lineHeight: 1,
                }}
              >
                👍
              </button>
              <button
                title="No útil"
                onClick={() => onFeedback("down")}
                style={{
                  background: rated === "down" ? "#fee2e2" : "transparent",
                  border: `1px solid ${rated === "down" ? "#dc2626" : "#e5e7eb"}`,
                  borderRadius: 6,
                  padding: "2px 6px",
                  cursor: "pointer",
                  fontSize: 13,
                  color: rated === "down" ? "#dc2626" : "#9ca3af",
                  lineHeight: 1,
                }}
              >
                👎
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


function SatisfactionModal({ primaryColor, onSubmit, onSkip }) {
  const [selected, setSelected] = useState(null);
  const [comment, setComment] = useState("");

  const options = [
    { score: 1, emoji: "✅", label: "Sí, resolvió mi problema" },
    { score: 2, emoji: "⚠️", label: "Parcialmente" },
    { score: 3, emoji: "❌", label: "No resolvió" },
  ];

  return (
    <div style={{
      position: "absolute", inset: 0,
      background: "rgba(255,255,255,0.96)",
      backdropFilter: "blur(4px)",
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      padding: 24, zIndex: 10, gap: 12,
      borderRadius: "inherit",
    }}>
      <div style={{ fontSize: 28 }}>⭐</div>
      <p style={{ fontWeight: 800, fontSize: 15, color: primaryColor, textAlign: "center", margin: 0 }}>
        ¿Fue útil la atención?
      </p>
      <p style={{ fontSize: 12, color: "var(--botiq-muted)", textAlign: "center", margin: 0 }}>
        Tu calificación ayuda a mejorar BOTIQ
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
        {options.map((opt) => (
          <button
            key={opt.score}
            onClick={() => setSelected(opt.score)}
            style={{
              border: `1.5px solid ${selected === opt.score ? primaryColor : "#e5e7eb"}`,
              borderRadius: 10,
              padding: "10px 14px",
              background: selected === opt.score ? `${primaryColor}12` : "var(--botiq-card-bg)",
              color: selected === opt.score ? primaryColor : "#374151",
              cursor: "pointer",
              fontWeight: selected === opt.score ? 700 : 400,
              fontSize: 13,
              textAlign: "left",
              display: "flex", alignItems: "center", gap: 8,
            }}
          >
            <span>{opt.emoji}</span> {opt.label}
          </button>
        ))}
      </div>

      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Comentario opcional..."
        rows={2}
        style={{
          width: "100%", border: "1px solid #e5e7eb", borderRadius: 8,
          padding: "8px 10px", fontSize: 12, resize: "none", outline: "none",
          boxSizing: "border-box",
        }}
      />

      <div style={{ display: "flex", gap: 8, width: "100%" }}>
        <button
          onClick={onSkip}
          style={{
            flex: 1, border: "1px solid #e5e7eb", borderRadius: 8,
            padding: "9px 0", background: "var(--botiq-card-bg)", color: "var(--botiq-muted)",
            cursor: "pointer", fontSize: 13,
          }}
        >
          Omitir
        </button>
        <button
          disabled={!selected}
          onClick={() => onSubmit(selected, comment || null)}
          style={{
            flex: 2, borderRadius: 8, border: "none",
            padding: "9px 0",
            background: selected ? `linear-gradient(135deg, ${primaryColor}, #3a3490)` : "#d1d5db",
            color: "#fff", cursor: selected ? "pointer" : "not-allowed",
            fontWeight: 700, fontSize: 13,
          }}
        >
          Enviar calificación
        </button>
      </div>
    </div>
  );
}

function Meta({ children, color = "var(--botiq-muted)" }) {
  return <span style={{ fontSize: 10, color }}>{children}</span>;
}

function Ava({ color, size, children }) {
  return <div style={{ width: size, height: size, borderRadius: "50%", background: color, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 12 }}>{children}</div>;
}

function HBtn({ onClick, title, children }) {
  return <button onClick={onClick} title={title} style={{ background: "rgba(255,255,255,0.11)", border: "1px solid rgba(255,255,255,0.2)", color: "rgba(255,255,255,0.76)", width: 28, height: 28, borderRadius: 8, cursor: "pointer" }}>{children}</button>;
}

function Typing() {
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center", height: 14 }}>
      {[0, 1, 2].map((i) => <div key={i} style={{ width: 5, height: 5, borderRadius: "50%", background: "#9ca3af", animation: `tDot 1.2s ease-in-out ${i * 0.2}s infinite` }} />)}
      <style>{`@keyframes tDot{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-5px)}}`}</style>
    </div>
  );
}

function quickBtn(primaryColor) {
  return {
    background: `${primaryColor}08`,
    border: `1px solid ${primaryColor}25`,
    borderRadius: 20,
    padding: "7px 14px",
    fontSize: 12,
    cursor: "pointer",
    color: primaryColor,
    fontWeight: 600,
  };
}

function profileBtn(primaryColor, active) {
  return {
    background: active ? `${primaryColor}18` : "var(--botiq-surface)",
    color: primaryColor,
    border: `1px solid ${active ? primaryColor : "var(--botiq-border)"}`,
    borderRadius: 14,
    padding: "14px 8px",
    cursor: "pointer",
    fontWeight: 800,
    fontSize: 12,
    lineHeight: 1.7,
    display: "flex",
    flexDirection: "column",
    gap: 4,
    alignItems: "center",
  };
}

function floatBtn(primaryColor) {
  return {
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
  };
}

const warningBanner = {
  background: "#fef3c7",
  borderBottom: "1px solid #fde68a",
  padding: "8px 16px",
  fontSize: 11,
  color: "#92400e",
};

const profileSub = {
  fontSize: 10,
  color: "var(--botiq-muted)",
  fontWeight: 650,
};

const closeImageBtn = {
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
};


