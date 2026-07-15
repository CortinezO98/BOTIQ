import { useCallback, useRef, useState } from "react";
import { chatAPI } from "../services/api";

function normalizeError(error, fallback = "Error procesando solicitud.") {
  const detail = error.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(", ");
  return detail || error.message || fallback;
}

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [session, setSession] = useState(null);
  const [sessionStatus, setSessionStatus] = useState("idle");
  const [loading, setLoading] = useState(false);
  const sid = useRef(null);

  const add = (role, content, meta = {}) => {
    const item = {
      id: crypto.randomUUID(),
      role,
      content,
      meta,
      ts: new Date(),
    };
    setMessages((prev) => [...prev, item]);
    return item;
  };

  const startSession = useCallback(async ({ selected_profile, network_username }) => {
    setLoading(true);
    try {
      const { data } = await chatAPI.startSession({ selected_profile, network_username });
      sid.current = data.session_id;
      setSession(data);
      setSessionStatus("active");
      setMessages([]);
      add("assistant", data.welcome_message, {
        system: true,
        selectedProfile: data.selected_profile,
      });
      return data;
    } catch (error) {
      const msg = normalizeError(error, "No fue posible iniciar la sesión.");
      add("assistant", msg, { isError: true });
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const sendMessage = useCallback(async (text, imageFile = null) => {
    if (!session || !sid.current) {
      add("assistant", "Primero selecciona si eres Empleado o Ingeniero de Soporte.", { isError: true });
      return;
    }

    if (!text.trim() && !imageFile) return;

    add("user", text, { imageFile });
    setLoading(true);

    try {
      const { data } = await chatAPI.sendMessage(text, sid.current, imageFile);

      setSessionStatus(data.session_status || "active");

      if (session) {
        setSession((prev) => ({
          ...prev,
          question_count: data.question_count,
          max_questions: data.max_questions,
          ticket_eligible: data.ticket_eligible,
          aranda_ticket_id: data.aranda_ticket_id,
        }));
      }

      add("assistant", data.response, {
        module: data.module_used,
        sources: data.sources,
        escalated: data.escalated_to_aranda,
        hasImage: data.has_image_analysis,
        knowledgeGap: data.knowledge_gap,
        applicationStatus: data.application_status,
        ticketEligible: data.ticket_eligible,
        arandaTicketId: data.aranda_ticket_id,
        sessionStatus: data.session_status,
        endedReason: data.ended_reason,
        questionCount: data.question_count,
        maxQuestions: data.max_questions,
      });
    } catch (error) {
      add("assistant", normalizeError(error), { isError: true });
    } finally {
      setLoading(false);
    }
  }, [session]);

  const clearChat = useCallback(async () => {
    if (sid.current) {
      try {
        await chatAPI.endSession(sid.current);
      } catch {
        // Ignorar error de cierre.
      }
    }

    setMessages([]);
    setSession(null);
    setSessionStatus("idle");
    sid.current = null;
  }, []);

  const submitFeedback = useCallback(async (messageId, rating, comment = null) => {
    try {
      await chatAPI.submitFeedback(messageId, rating, comment);
      // Actualizar el estado local del mensaje con el rating
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId ? { ...m, meta: { ...m.meta, userRating: rating } } : m
        )
      );
    } catch (error) {
      console.error("Error enviando feedback:", error);
    }
  }, []);

  const submitSatisfaction = useCallback(async (score, comment = null) => {
    if (!sid.current) return;
    try {
      await chatAPI.submitSatisfaction(sid.current, score, comment);
    } catch (error) {
      console.error("Error enviando satisfacción:", error);
    }
  }, []);

  const loadConversationMessages = useCallback(async (conversationId) => {
    setLoading(true);
    try {
      const { data } = await chatAPI.conversationMessages(conversationId);
      const mapped = data.map((msg) => ({
        id: msg.id,
        role: msg.role === "assistant" || msg.role === "system" ? "assistant" : "user",
        content: msg.content,
        meta: {
          system: msg.role === "system",
          ...msg.metadata_,
        },
        ts: new Date(msg.created_at),
      }));
      setMessages(mapped);
      return mapped;
    } finally {
      setLoading(false);
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
    loadConversationMessages,
    submitFeedback,
    submitSatisfaction,
  };
}