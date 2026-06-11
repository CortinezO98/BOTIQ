import { useState, useCallback } from "react";
import { chatAPI } from "../services/api";

let _sessionId = null;
function getSessionId() {
  if (!_sessionId) _sessionId = crypto.randomUUID();
  return _sessionId;
}

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const addMsg = (role, content, meta = {}) =>
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role, content, meta, ts: new Date() }]);

  const sendMessage = useCallback(async (text, imageBase64 = null, imageMimeType = null) => {
    if (!text.trim() && !imageBase64) return;
    addMsg("user", text);
    setLoading(true);
    try {
      const { data } = await chatAPI.sendMessage({
        message: text,
        session_id: getSessionId(),
        ...(imageBase64 && { image_base64: imageBase64, image_mime_type: imageMimeType }),
      });
      addMsg("assistant", data.response, {
        module: data.module_used,
        sources: data.sources,
        escalated: data.escalated_to_aranda,
        hasImage: data.has_image_analysis,
      });
    } catch (err) {
      const msg = err.response?.data?.detail || "Error al procesar tu consulta. Intenta de nuevo.";
      addMsg("assistant", msg, { isError: true });
    } finally { setLoading(false); }
  }, []);

  const clearChat = useCallback(() => {
    setMessages([]);
    _sessionId = null;
  }, []);

  return { messages, loading, sendMessage, clearChat };
}
