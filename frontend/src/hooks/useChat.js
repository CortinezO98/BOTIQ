import { useState, useCallback, useRef } from "react";
import { chatAPI } from "../services/api";

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const sessionIdRef = useRef(crypto.randomUUID());

  const addMsg = (role, content, meta = {}) =>
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role, content, meta, ts: new Date() }]);

  const sendMessage = useCallback(async (text, imageFile = null) => {
    if (!text.trim() && !imageFile) return;
    addMsg("user", text, { imageFile });
    setLoading(true);
    try {
      const { data } = await chatAPI.sendMessage(text, sessionIdRef.current, imageFile);
      addMsg("assistant", data.response, {
        module: data.module_used,
        sources: data.sources,
        escalated: data.escalated_to_aranda,
        hasImage: data.has_image_analysis,
        knowledgeGap: data.knowledge_gap,
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg).join(", ")
        : detail || "Error procesando tu consulta. Intenta de nuevo.";
      addMsg("assistant", msg, { isError: true });
    } finally { setLoading(false); }
  }, []);

  const clearChat = useCallback(async () => {
    // Cerrar sesión en el backend
    try { await chatAPI.endSession(sessionIdRef.current); } catch {}
    setMessages([]);
    sessionIdRef.current = crypto.randomUUID();
  }, []);

  return { messages, loading, sendMessage, clearChat, sessionId: sessionIdRef.current };
}
