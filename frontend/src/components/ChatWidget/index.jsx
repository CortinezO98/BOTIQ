import { useEffect, useRef, useState } from "react";
import { useChat } from "../../hooks/useChat";
import { healthAPI, supportAPI } from "../../services/api";
import BotiqAvatar from "../Brand/BotiqAvatar";
import BotiqBotIcon from "../Brand/BotiqBotIcon";
import "./chat-widget.css";

const C = "#272163";
const CL = "#3a3490";

const MODULE_INFO = {
  employee: { label: "Empleado", icon: "👤", color: "#059669" },
  support_rag: { label: "Base Conocimiento", icon: "📚", color: "#7c3aed" },
  server_validation: { label: "Servidores", icon: "🖥️", color: "#0284c7" },
};

const QUICK_EMPLOYEE = [];
const QUICK_SUPPORT = [];

export default function ChatWidget({
  position = "bottom-right",
  primaryColor = C,
  embedded = false,
}) {
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
  const networkInputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (!open) return;

    supportAPI
      .status()
      .then((response) => setKbStatus(response.data))
      .catch(() => {});

    healthAPI
      .check()
      .then((response) =>
        setAiAvailable(response.data?.ai_available !== false),
      )
      .catch(() => setAiAvailable(true));
  }, [open]);

  const resetLocalFlow = async () => {
    if (session && messages.length > 1) {
      setShowSatisfaction(true);
      return;
    }

    await doReset();
  };

  const doReset = async () => {
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
    await doReset();
  };

  const configureProfile = async (profile) => {
    setProfileError("");
    setSelectedProfile(profile);

    try {
      await startSession({
        selected_profile: profile,
        network_username:
          profile === "support_engineer"
            ? networkUsername.trim()
            : undefined,
      });
    } catch (error) {
      setProfileError(error.message);
    }
  };

  const configureSupport = async () => {
    if (!networkUsername.trim()) {
      setProfileError(
        "Ingresa tu usuario de red para validar el perfil de soporte.",
      );
      networkInputRef.current?.focus();
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
      window.alert("La imagen no puede superar 5MB");
      return;
    }

    setImgFile(file);

    const reader = new FileReader();
    reader.onload = (loadEvent) =>
      setImgPreview(loadEvent.target.result);
    reader.readAsDataURL(file);

    event.target.value = "";
  };

  const pos =
    position === "bottom-left"
      ? { bottom: 22, left: 22 }
      : { bottom: 22, right: 22 };

  const fixedStyle = {
    ...pos,
    position: "fixed",
    zIndex: 2147483000,
    display: "flex",
    flexDirection: "column",
    alignItems:
      position === "bottom-left" ? "flex-start" : "flex-end",
    pointerEvents: "none",
  };

  const quickQuestions =
    session?.selected_profile === "support_engineer"
      ? QUICK_SUPPORT
      : QUICK_EMPLOYEE;

  const content = (
    <div
      className={
        embedded
          ? "botiq-chat-panel botiq-chat-panel--embedded"
          : "botiq-chat-panel animate__animated animate__fadeInUp"
      }
      style={{ "--chat-primary": primaryColor }}
    >
      <Header
        primaryColor={primaryColor}
        onReset={resetLocalFlow}
        onClose={() => setOpen(false)}
        showClose={!embedded}
      />

      {kbStatus &&
        !kbStatus.drive_configured &&
        messages.length === 0 && (
          <div className="botiq-chat-alert botiq-chat-alert--warning">
            ⚠️ Google Drive no conectado — modo FAQ básico activo.
          </div>
        )}

      {!aiAvailable && (
        <div className="botiq-chat-alert botiq-chat-alert--degraded">
          ⚠️ <strong>Modo degradado</strong> — la IA no está disponible y
          las respuestas pueden ser limitadas.
        </div>
      )}

      <div className="botiq-chat-content">
        {!session && (
          <ProfileSelector
            selectedProfile={selectedProfile}
            setSelectedProfile={setSelectedProfile}
            networkUsername={networkUsername}
            setNetworkUsername={setNetworkUsername}
            configureProfile={configureProfile}
            configureSupport={configureSupport}
            loading={loading}
            error={profileError}
            primaryColor={primaryColor}
            networkInputRef={networkInputRef}
          />
        )}

        {session && (
          <SessionBanner
            session={session}
            status={sessionStatus}
          />
        )}

        {session &&
          messages.map((msg) => (
            <Bubble
              key={msg.id}
              msg={msg}
              primaryColor={primaryColor}
              onFeedback={(rating) =>
                submitFeedback(msg.id, rating)
              }
            />
          ))}

        {session &&
          quickQuestions.length > 0 &&
          messages.length <= 1 &&
          !loading && (
            <div className="botiq-chat-quick-list">
              {quickQuestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => sendMessage(question)}
                  className="botiq-chat-quick-button"
                >
                  {question}
                </button>
              ))}
            </div>
          )}

        {loading && (
          <div className="botiq-chat-typing-row">
            <BotiqAvatar size={28} color={primaryColor} />
            <div className="botiq-chat-typing-bubble">
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
          onSkip={doReset}
        />
      )}

      {session && imgPreview && (
        <div className="botiq-chat-image-preview">
          <div>
            <img src={imgPreview} alt="Vista previa del archivo adjunto" />
            <button
              type="button"
              onClick={() => {
                setImgFile(null);
                setImgPreview(null);
              }}
              aria-label="Eliminar imagen adjunta"
            >
              ✕
            </button>
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
      {open && (
        <div style={{ pointerEvents: "auto" }}>
          {content}
        </div>
      )}

      <div className="botiq-chat-launcher-wrap">
        <span className="botiq-chat-launcher-label">
          {open ? "Cerrar asistente" : "Abrir BOTIQ"}
        </span>

        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className={`botiq-chat-float-button ${
            open ? "is-open" : ""
          }`}
          style={{
            "--chat-primary": primaryColor,
            pointerEvents: "auto",
          }}
          title={open ? "Cerrar BOTIQ" : "Abrir BOTIQ"}
          aria-label={open ? "Cerrar BOTIQ" : "Abrir BOTIQ"}
        >
          {open ? (
            <span className="botiq-chat-float-close" aria-hidden="true" />
          ) : (
            <>
              <BotiqBotIcon size={31} color={primaryColor} light />
              <span
                className="botiq-chat-float-status"
                aria-hidden="true"
              />
            </>
          )}
        </button>
      </div>
    </div>
  );
}

function Header({ primaryColor, onReset, onClose, showClose }) {
  return (
    <div
      className="botiq-chat-header"
      style={{
        background: `linear-gradient(135deg, ${primaryColor}, ${CL})`,
      }}
    >
      <div className="botiq-chat-header__identity">
        <BotiqAvatar size={40} color={primaryColor} online />

        <div>
          <div className="botiq-chat-header__title">BOTIQ</div>
          <div className="botiq-chat-header__subtitle">
            Asistente IA corporativo
          </div>
        </div>
      </div>

      <div className="botiq-chat-header__actions">
        <HeaderButton
          onClick={onReset}
          title="Nueva conversación"
          ariaLabel="Nueva conversación"
        >
          ↺
        </HeaderButton>

        {showClose && (
          <HeaderButton
            onClick={onClose}
            title="Cerrar"
            ariaLabel="Cerrar chat"
          >
            ✕
          </HeaderButton>
        )}
      </div>
    </div>
  );
}

function ProfileSelector({
  selectedProfile,
  setSelectedProfile,
  networkUsername,
  setNetworkUsername,
  configureProfile,
  configureSupport,
  loading,
  error,
  primaryColor,
  networkInputRef,
}) {
  return (
    <div className="botiq-profile-selector">
      <div className="botiq-profile-selector__avatar">
        <BotiqAvatar size={66} color={primaryColor} online />
      </div>

      <span className="botiq-profile-selector__eyebrow">
        Configuración inicial
      </span>

      <h2 className="botiq-profile-selector__title">
        Antes de iniciar
      </h2>

      <p className="botiq-profile-selector__description">
        Selecciona tu perfil para configurar el flujo conversacional,
        las fuentes de conocimiento y los controles de uso de IA.
      </p>

      <div className="botiq-profile-options">
        <button
          type="button"
          disabled={loading}
          onClick={() => configureProfile("employee")}
          className={`botiq-profile-card ${
            selectedProfile === "employee" ? "is-active" : ""
          }`}
        >
          <span className="botiq-profile-card__icon">👤</span>
          <strong>Empleado</strong>
          <small>FAQs, aplicativos y URLs</small>
        </button>

        <button
          type="button"
          disabled={loading}
          onClick={() => networkInputRef.current?.focus()}
          className={`botiq-profile-card ${
            selectedProfile === "support_engineer"
              ? "is-active"
              : ""
          }`}
        >
          <span className="botiq-profile-card__icon">🛠️</span>
          <strong>Ing. Soporte</strong>
          <small>RAG, PDFs y servidores</small>
        </button>
      </div>

      <div className="botiq-support-access">
        <label htmlFor="botiq-network-user">
          Usuario de red para soporte
        </label>

        <div className="botiq-support-access__input-wrap">
          <span aria-hidden="true">👤</span>
          <input
            id="botiq-network-user"
            ref={networkInputRef}
            value={networkUsername}
            onChange={(event) =>
              setNetworkUsername(event.target.value)
            }
            onFocus={() =>
              setSelectedProfile("support_engineer")
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                configureSupport();
              }
            }}
            placeholder="Ej. jose.cortez"
            autoComplete="username"
          />
        </div>

        <button
          type="button"
          disabled={loading}
          onClick={configureSupport}
          className="botiq-support-access__button"
        >
          {loading ? "Validando perfil..." : "Validar e iniciar como soporte"}
        </button>
      </div>

      <div className="botiq-profile-selector__notice">
        <span>🔒</span>
        <p>
          BOTIQ registra trazabilidad, limita preguntas por sesión y
          bloquea temas fuera del alcance corporativo.
        </p>
      </div>

      {error && (
        <div className="botiq-profile-selector__error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}

function SessionBanner({ session, status }) {
  const profile =
    session.selected_profile === "support_engineer"
      ? "Ingeniero de Soporte"
      : "Empleado";

  const used = session.question_count || 0;
  const max = session.max_questions || 0;
  const remaining = Math.max(max - used, 0);

  return (
    <div className="botiq-session-banner">
      <div>
        <strong>{profile}</strong>
        <span className={`status-${status}`}>{status}</span>
      </div>

      <p>
        Preguntas restantes: <b>{remaining}</b> de {max}
      </p>

      {session.ticket_eligible && (
        <div className="botiq-session-banner__notice is-warning">
          Ticket Aranda elegible como última instancia.
        </div>
      )}

      {session.aranda_ticket_id && (
        <div className="botiq-session-banner__notice is-success">
          Ticket: {session.aranda_ticket_id}
        </div>
      )}
    </div>
  );
}

function Composer({
  input,
  setInput,
  send,
  handleKey,
  fileRef,
  handleFile,
  loading,
  imgFile,
  disabled,
  primaryColor,
}) {
  const sendDisabled =
    disabled || loading || (!input.trim() && !imgFile);

  return (
    <div className="botiq-chat-composer">
      <input
        ref={fileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="botiq-chat-hidden-input"
        onChange={handleFile}
      />

      <button
        type="button"
        disabled={disabled}
        onClick={() => fileRef.current?.click()}
        title="Adjuntar imagen"
        aria-label="Adjuntar imagen"
        className="botiq-chat-attach-button"
      >
        📎
      </button>

      <textarea
        value={input}
        disabled={disabled}
        onChange={(event) => setInput(event.target.value)}
        onKeyDown={handleKey}
        placeholder={
          disabled
            ? "Sesión finalizada"
            : "Escribe tu consulta corporativa..."
        }
        rows={1}
      />

      <button
        type="button"
        onClick={send}
        disabled={sendDisabled}
        className="botiq-chat-send-button"
        style={{
          background: sendDisabled
            ? undefined
            : `linear-gradient(135deg, ${primaryColor}, ${CL})`,
        }}
        aria-label="Enviar mensaje"
      >
        ➤
      </button>
    </div>
  );
}

function Bubble({ msg, primaryColor, onFeedback }) {
  const isUser = msg.role === "user";
  const mod = MODULE_INFO[msg.meta?.module];
  const rated = msg.meta?.userRating;

  return (
    <div
      className={`botiq-chat-message-row ${
        isUser ? "is-user" : "is-bot"
      }`}
    >
      {isUser ? (
        <AvatarBubble>👤</AvatarBubble>
      ) : (
        <BotiqAvatar size={28} color={primaryColor} />
      )}

      <div className="botiq-chat-message">
        <div
          className={`botiq-chat-bubble-text ${
            isUser
              ? "is-user"
              : msg.meta?.isError
                ? "is-error"
                : msg.meta?.system
                  ? "is-system"
                  : "is-bot"
          }`}
          style={
            isUser
              ? {
                  background: `linear-gradient(135deg, ${primaryColor}, ${primaryColor}dd)`,
                }
              : undefined
          }
        >
          {msg.content}
        </div>

        <div className="botiq-chat-meta-row">
          {mod && !isUser && (
            <Meta color={mod.color}>
              {mod.icon} {mod.label}
            </Meta>
          )}

          {msg.meta?.questionCount !== undefined && (
            <Meta>
              {msg.meta.questionCount}/{msg.meta.maxQuestions} preguntas
            </Meta>
          )}

          {msg.meta?.applicationStatus && (
            <Meta color="#0284c7">🔎 estado consultado</Meta>
          )}

          {msg.meta?.sources?.length > 0 && (
            <Meta>
              📄 {msg.meta.sources.slice(0, 2).join(", ")}
            </Meta>
          )}

          {msg.meta?.knowledgeGap && (
            <Meta color="#7c3aed">🧠 brecha detectada</Meta>
          )}

          {msg.meta?.ticketEligible && (
            <Meta color="#d97706">🎫 ticket elegible</Meta>
          )}

          {msg.meta?.arandaTicketId && (
            <Meta color="#059669">
              Aranda: {msg.meta.arandaTicketId}
            </Meta>
          )}

          {msg.meta?.sessionStatus &&
            msg.meta.sessionStatus !== "active" && (
              <Meta color="#dc2626">Sesión finalizada</Meta>
            )}

          {!isUser && !msg.meta?.system && onFeedback && (
            <div className="botiq-chat-feedback">
              <button
                type="button"
                title="Útil"
                aria-label="Marcar respuesta como útil"
                onClick={() => onFeedback("up")}
                className={rated === "up" ? "is-selected-up" : ""}
              >
                👍
              </button>

              <button
                type="button"
                title="No útil"
                aria-label="Marcar respuesta como no útil"
                onClick={() => onFeedback("down")}
                className={
                  rated === "down" ? "is-selected-down" : ""
                }
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
    <div className="botiq-satisfaction-modal">
      <div className="botiq-satisfaction-modal__icon">⭐</div>

      <h2>¿Fue útil la atención?</h2>

      <p>Tu calificación ayuda a mejorar BOTIQ.</p>

      <div className="botiq-satisfaction-modal__options">
        {options.map((option) => (
          <button
            key={option.score}
            type="button"
            onClick={() => setSelected(option.score)}
            className={
              selected === option.score ? "is-selected" : ""
            }
            style={{
              "--chat-primary": primaryColor,
            }}
          >
            <span>{option.emoji}</span>
            {option.label}
          </button>
        ))}
      </div>

      <textarea
        value={comment}
        onChange={(event) => setComment(event.target.value)}
        placeholder="Comentario opcional..."
        rows={2}
      />

      <div className="botiq-satisfaction-modal__actions">
        <button type="button" onClick={onSkip}>
          Omitir
        </button>

        <button
          type="button"
          disabled={!selected}
          onClick={() =>
            onSubmit(selected, comment || null)
          }
          style={{
            background: selected
              ? `linear-gradient(135deg, ${primaryColor}, ${CL})`
              : undefined,
          }}
        >
          Enviar calificación
        </button>
      </div>
    </div>
  );
}

function HeaderButton({
  onClick,
  title,
  ariaLabel,
  children,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={ariaLabel}
      className="botiq-chat-header__button"
    >
      {children}
    </button>
  );
}

function Meta({ children, color = "var(--botiq-muted)" }) {
  return (
    <span className="botiq-chat-meta" style={{ color }}>
      {children}
    </span>
  );
}

function AvatarBubble({ children }) {
  return (
    <div className="botiq-chat-user-avatar">
      {children}
    </div>
  );
}

function Typing() {
  return (
    <div className="botiq-chat-typing">
      {[0, 1, 2].map((index) => (
        <span key={index} style={{ "--typing-delay": `${index * 0.2}s` }} />
      ))}
    </div>
  );
}
