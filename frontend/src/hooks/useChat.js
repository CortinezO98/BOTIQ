/**
 * Hook para gestionar el estado del chat.
 */

import { useState, useCallback, useRef } from "react";
import { chatAPI } from "../services/api";
import { v4 as uuidv4 } from "crypto";

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => uuidv4());

  const addMessage = (role, content, meta = {}) => {
    setMessages((prev) => [
      ...prev,
      { id: uuidv4(), role, content, meta, timestamp: new Date() },
    ]);
  };

  const sendMessage = useCallback(
    async (text, imageBase64 = null, imageMimeType = null) => {
      if (!text.trim() && !imageBase64) return;

      addMessage("user", text);
      setLoading(true);

      try {
        const payload = {
          message: text,
          session_id: sessionId,
          ...(imageBase64 && { image_base64: imageBase64, image_mime_type: imageMimeType }),
        };

        const response = await chatAPI.sendMessage(payload);
        const data = response.data;

        addMessage("assistant", data.response, {
          module: data.module_used,
          sources: data.sources,
          escalated: data.escalated_to_aranda,
          hasImageAnalysis: data.has_image_analysis,
        });
      } catch (err) {
        addMessage("assistant", "Lo siento, ocurrió un error al procesar tu solicitud. Inténtalo de nuevo.", {
          isError: true,
        });
      } finally {
        setLoading(false);
      }
    },
    [sessionId]
  );

  const clearChat = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, loading, sendMessage, clearChat, sessionId };
}
