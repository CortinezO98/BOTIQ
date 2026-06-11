/**
 * BOTIQ Chat Widget — Botón flotante embebible.
 * Se puede anclar a cualquier página web mediante un script tag.
 */

import { useState, useRef, useEffect } from "react";
import { MessageCircle, X, Send, Paperclip, Bot, User, AlertCircle, ChevronDown } from "lucide-react";
import { useChat } from "../../hooks/useChat";

const MODULE_LABELS = {
  employee: "Empleados",
  support_rag: "Base de Conocimiento",
  server_validation: "Servidores",
};

const MODULE_COLORS = {
  employee: "#3B82F6",
  support_rag: "#8B5CF6",
  server_validation: "#10B981",
};

export default function ChatWidget({ position = "bottom-right", primaryColor = "#1E3A5F" }) {
  const [isOpen, setIsOpen] = useState(false);
  const [inputText, setInputText] = useState("");
  const [imagePreview, setImagePreview] = useState(null);
  const [imageBase64, setImageBase64] = useState(null);
  const [imageMimeType, setImageMimeType] = useState(null);

  const { messages, loading, sendMessage, clearChat } = useChat();
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async () => {
    if (!inputText.trim() && !imageBase64) return;
    const text = inputText;
    setInputText("");
    setImagePreview(null);
    const img = imageBase64;
    const mime = imageMimeType;
    setImageBase64(null);
    setImageMimeType(null);
    await sendMessage(text, img, mime);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const result = event.target.result;
      const base64 = result.split(",")[1];
      setImageBase64(base64);
      setImageMimeType(file.type);
      setImagePreview(result);
    };
    reader.readAsDataURL(file);
  };

  const positionClass = {
    "bottom-right": { bottom: "24px", right: "24px" },
    "bottom-left": { bottom: "24px", left: "24px" },
  }[position] || { bottom: "24px", right: "24px" };

  return (
    <div style={{ position: "fixed", zIndex: 9999, ...positionClass }}>
      {/* Panel del chat */}
      {isOpen && (
        <div style={{
          width: "380px",
          height: "560px",
          background: "#ffffff",
          borderRadius: "16px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          marginBottom: "16px",
          border: "1px solid #e5e7eb",
        }}>
          {/* Header */}
          <div style={{
            background: primaryColor,
            padding: "16px 20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{
                width: "36px", height: "36px", borderRadius: "50%",
                background: "rgba(255,255,255,0.2)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Bot size={20} color="#fff" />
              </div>
              <div>
                <div style={{ color: "#fff", fontWeight: 700, fontSize: "15px" }}>BOTIQ</div>
                <div style={{ color: "rgba(255,255,255,0.7)", fontSize: "12px" }}>Asistente Corporativo</div>
              </div>
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              <button onClick={clearChat} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.7)", padding: "4px" }}>
                <ChevronDown size={18} />
              </button>
              <button onClick={() => setIsOpen(false)} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.7)", padding: "4px" }}>
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div style={{ flex: 1, overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
            {messages.length === 0 && (
              <div style={{ textAlign: "center", color: "#9CA3AF", fontSize: "14px", marginTop: "40px" }}>
                <Bot size={40} style={{ margin: "0 auto 12px", opacity: 0.3 }} />
                <p>¡Hola! Soy BOTIQ.</p>
                <p style={{ fontSize: "12px", marginTop: "4px" }}>¿En qué puedo ayudarte hoy?</p>
              </div>
            )}

            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} primaryColor={primaryColor} />
            ))}

            {loading && (
              <div style={{ display: "flex", gap: "8px", alignItems: "flex-start" }}>
                <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: primaryColor, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <Bot size={14} color="#fff" />
                </div>
                <div style={{ background: "#F3F4F6", borderRadius: "12px", padding: "10px 14px" }}>
                  <TypingIndicator />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Image preview */}
          {imagePreview && (
            <div style={{ padding: "8px 16px", background: "#F9FAFB", borderTop: "1px solid #E5E7EB" }}>
              <div style={{ position: "relative", display: "inline-block" }}>
                <img src={imagePreview} alt="preview" style={{ height: "60px", borderRadius: "8px", objectFit: "cover" }} />
                <button
                  onClick={() => { setImagePreview(null); setImageBase64(null); }}
                  style={{ position: "absolute", top: "-6px", right: "-6px", background: "#EF4444", border: "none", borderRadius: "50%", width: "18px", height: "18px", cursor: "pointer", color: "#fff", fontSize: "10px", display: "flex", alignItems: "center", justifyContent: "center" }}
                >
                  ×
                </button>
              </div>
            </div>
          )}

          {/* Input */}
          <div style={{ padding: "12px 16px", borderTop: "1px solid #E5E7EB", background: "#fff" }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: "8px" }}>
              <input ref={fileInputRef} type="file" accept="image/*" style={{ display: "none" }} onChange={handleImageUpload} />
              <button
                onClick={() => fileInputRef.current?.click()}
                style={{ background: "none", border: "none", cursor: "pointer", color: "#9CA3AF", padding: "8px", flexShrink: 0 }}
              >
                <Paperclip size={18} />
              </button>
              <textarea
                ref={textareaRef}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Escribe tu consulta..."
                rows={1}
                style={{
                  flex: 1, border: "1px solid #E5E7EB", borderRadius: "20px",
                  padding: "8px 14px", fontSize: "14px", resize: "none",
                  outline: "none", fontFamily: "inherit", maxHeight: "80px",
                  overflowY: "auto",
                }}
              />
              <button
                onClick={handleSend}
                disabled={loading || (!inputText.trim() && !imageBase64)}
                style={{
                  background: loading ? "#9CA3AF" : primaryColor,
                  border: "none", borderRadius: "50%",
                  width: "36px", height: "36px",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  cursor: loading ? "not-allowed" : "pointer", flexShrink: 0,
                }}
              >
                <Send size={16} color="#fff" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Botón flotante */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: "56px", height: "56px",
          background: primaryColor,
          border: "none", borderRadius: "50%",
          display: "flex", alignItems: "center", justifyContent: "center",
          cursor: "pointer",
          boxShadow: "0 4px 20px rgba(0,0,0,0.2)",
          transition: "transform 0.2s",
          marginLeft: "auto",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.1)")}
        onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
      >
        {isOpen ? <X size={24} color="#fff" /> : <MessageCircle size={24} color="#fff" />}
      </button>
    </div>
  );
}

function MessageBubble({ message, primaryColor }) {
  const isUser = message.role === "user";
  return (
    <div style={{ display: "flex", gap: "8px", alignItems: "flex-start", flexDirection: isUser ? "row-reverse" : "row" }}>
      <div style={{
        width: "28px", height: "28px", borderRadius: "50%",
        background: isUser ? "#E5E7EB" : primaryColor,
        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      }}>
        {isUser ? <User size={14} color="#6B7280" /> : <Bot size={14} color="#fff" />}
      </div>
      <div style={{ maxWidth: "75%" }}>
        <div style={{
          background: isUser ? primaryColor : "#F3F4F6",
          color: isUser ? "#fff" : "#111827",
          borderRadius: isUser ? "12px 4px 12px 12px" : "4px 12px 12px 12px",
          padding: "10px 14px", fontSize: "14px", lineHeight: "1.5",
          whiteSpace: "pre-wrap",
        }}>
          {message.content}
        </div>
        {message.meta?.sources?.length > 0 && (
          <div style={{ marginTop: "4px", fontSize: "11px", color: "#9CA3AF" }}>
            📚 Fuentes: {message.meta.sources.join(", ")}
          </div>
        )}
        {message.meta?.escalated && (
          <div style={{ marginTop: "4px", fontSize: "11px", color: "#F59E0B", display: "flex", alignItems: "center", gap: "4px" }}>
            <AlertCircle size={11} /> Escalado a Aranda
          </div>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
      {[0, 1, 2].map((i) => (
        <div key={i} style={{
          width: "6px", height: "6px", borderRadius: "50%", background: "#9CA3AF",
          animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
        }} />
      ))}
      <style>{`@keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-6px)} }`}</style>
    </div>
  );
}
