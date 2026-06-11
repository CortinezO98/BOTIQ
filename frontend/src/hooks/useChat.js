import { useState, useCallback, useRef } from "react";
import { chatAPI } from "../services/api";

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const sid = useRef(crypto.randomUUID());

  const add = (role, content, meta = {}) =>
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role, content, meta, ts: new Date() }]);

  const sendMessage = useCallback(async (text, imageFile = null) => {
    if (!text.trim() && !imageFile) return;
    add("user", text, { imageFile });
    setLoading(true);
    try {
      const { data } = await chatAPI.sendMessage(text, sid.current, imageFile);
      add("assistant", data.response, {
        module: data.module_used, sources: data.sources,
        escalated: data.escalated_to_aranda, hasImage: data.has_image_analysis,
        knowledgeGap: data.knowledge_gap,
      });
    } catch (e) {
      const d = e.response?.data?.detail;
      add("assistant", Array.isArray(d) ? d.map(x=>x.msg).join(", ") : d || "Error procesando consulta.", { isError: true });
    } finally { setLoading(false); }
  }, []);

  const clearChat = useCallback(async () => {
    try { await chatAPI.endSession(sid.current); } catch {}
    setMessages([]); sid.current = crypto.randomUUID();
  }, []);

  return { messages, loading, sendMessage, clearChat };
}
