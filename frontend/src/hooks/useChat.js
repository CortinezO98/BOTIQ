import { useState, useCallback, useRef } from "react";
import { chatAPI } from "../services/api";

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sessionStatus, setSessionStatus] = useState("not_started");
  const sid = useRef(null);

  const add = (role, content, meta = {}) =>
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role, content, meta, ts: new Date() },
    ]);

  const startSession = useCallback(async ({ selected_profile, network_username }) => {
    setLoading(true);
    try {
      const { data } = await chatAPI.startSession({ selected_profile, network_username: network_username || null });
      sid.current = data.session_id;
      setSession(data);
      setSessionStatus("active");
      setMessages([
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.welcome_message,
          meta: { module: data.module_used, selectedProfile: data.selected_profile, system: true },
          ts: new Date(),
        },
      ]);
      return data;
    } catch (e) {
      const msg = e.response?.data?.detail || "No fue posible iniciar la sesión";
      add("assistant", msg, { isError: true });
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const sendMessage = useCallback(async (text, imageFile = null) => {
    if (!text.trim() && !imageFile) return;

    if (!sid.current) {
      add("assistant", "Primero debes seleccionar si eres Empleado o Ingeniero de Soporte.", { isError: true });
      return;
    }

    if (sessionStatus !== "active") {
      add("assistant", "Esta sesión ya fue finalizada. Inicia una nueva conversación para continuar.", { isError: true });
      return;
    }

    add("user", text, { imageFile });
    setLoading(true);

    try {
      const { data } = await chatAPI.sendMessage(text, sid.current, imageFile);
      add("assistant", data.response, {
        module: data.module_used,
        sources: data.sources,
        escalated: data.escalated_to_aranda,
        hasImage: data.has_image_analysis,
        knowledgeGap: data.knowledge_gap,
        questionCount: data.question_count,
        maxQuestions: data.max_questions,
        sessionStatus: data.session_status,
        endedReason: data.ended_reason,
      });
      setSessionStatus(data.session_status || "active");
      if (data.session_status !== "active") sid.current = null;
      return data;
    } catch (e) {
      const d = e.response?.data?.detail;
      add("assistant", Array.isArray(d) ? d.map((x) => x.msg).join(", ") : d || "Error procesando consulta.", { isError: true });
    } finally {
      setLoading(false);
    }
  }, [sessionStatus]);

  const clearChat = useCallback(async () => {
    try {
      if (sid.current) await chatAPI.endSession(sid.current);
    } catch {}
    setMessages([]);
    setSession(null);
    setSessionStatus("not_started");
    sid.current = null;
  }, []);

  const loadConversation = useCallback(async (conversation) => {
    try {
      const { data } = await chatAPI.conversationMessages(conversation.id);
      sid.current = conversation.session_id;
      setSession({
        session_id: conversation.session_id,
        conversation_id: conversation.id,
        selected_profile: conversation.selected_profile,
        module_used: conversation.module,
        max_questions: conversation.question_count,
      });
      setSessionStatus(conversation.session_status || "ended");
      setMessages(
        data.map((m) => ({
          id: m.id,
          role: m.role === "assistant" || m.role === "system" ? "assistant" : "user",
          content: m.content,
          meta: { module: conversation.module, system: m.role === "system" },
          ts: new Date(m.created_at),
        }))
      );
    } catch {
      add("assistant", "No fue posible cargar el historial de esta conversación.", { isError: true });
    }
  }, []);

  return {
    messages,
    loading,
    session,
    sessionStatus,
    startSession,
    sendMessage,
    clearChat,
    loadConversation,
  };
}
