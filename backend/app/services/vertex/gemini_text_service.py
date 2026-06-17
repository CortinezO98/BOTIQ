import time
from typing import Dict, List, Optional

from app.core.config import settings
from app.services.vertex.vertex_client import is_vertex_available

DEMO_RESPONSE = (
    "Estoy en modo demo. Para activar respuestas con IA configura "
    "GCP_PROJECT_ID y GOOGLE_APPLICATION_CREDENTIALS en el archivo .env."
)


def _safe_text_from_response(resp) -> str:
    """Extrae texto aunque Vertex marque finish_reason distinto de STOP."""
    try:
        text = getattr(resp, "text", None)
        if text:
            return str(text).strip()
    except Exception:
        pass

    try:
        parts = []
        for cand in getattr(resp, "candidates", []) or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", []) or []:
                txt = getattr(part, "text", None)
                if txt:
                    parts.append(txt)
        return "\n".join(parts).strip()
    except Exception:
        return ""


def _finish_reason(resp) -> str:
    try:
        candidates = getattr(resp, "candidates", []) or []
        if candidates:
            return str(getattr(candidates[0], "finish_reason", ""))
    except Exception:
        pass
    return ""


class GeminiTextService:
    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        temperature: float = 0.3,
        max_output_tokens: int = 1024,
        model: Optional[str] = None,
    ) -> Dict:
        """
        Generación robusta con Vertex/Gemini.

        Corrección importante:
        - Vertex puede devolver finish_reason=2 (MAX_TOKENS) o respuestas incompletas.
        - La librería lanza excepción al leer resp.text si start_chat valida la respuesta.
        - Usamos response_validation=False y extraemos texto de candidates/parts.
        - Nunca se devuelve el error crudo al usuario; el chat puede activar fallback web.
        """
        start = time.time()
        if not is_vertex_available():
            return {
                "text": DEMO_RESPONSE,
                "tokens_used": 0,
                "response_time_ms": (time.time() - start) * 1000,
                "success": False,
                "finish_reason": "demo",
            }

        try:
            from vertexai.generative_models import GenerativeModel, GenerationConfig

            selected_model = model or settings.VERTEX_GEMINI_MODEL
            gm = GenerativeModel(selected_model, system_instruction=system_instruction)
            cfg = GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens or settings.MAX_OUTPUT_TOKENS,
            )

            history_fmt = []
            if history:
                for h in history:
                    role = h.get("role") or "user"
                    content = h.get("content") or ""
                    if content:
                        history_fmt.append({"role": role, "parts": [{"text": content}]})

            chat = gm.start_chat(history=history_fmt, response_validation=False)
            resp = await chat.send_message_async(prompt, generation_config=cfg)

            text = _safe_text_from_response(resp)
            finish = _finish_reason(resp)
            tokens = getattr(getattr(resp, "usage_metadata", None), "total_token_count", None)

            if not text:
                return {
                    "text": "No pude generar una respuesta completa con IA en este momento.",
                    "tokens_used": tokens or 0,
                    "response_time_ms": (time.time() - start) * 1000,
                    "success": False,
                    "finish_reason": finish or "empty_response",
                }

            return {
                "text": text,
                "tokens_used": tokens,
                "response_time_ms": (time.time() - start) * 1000,
                "success": True,
                "finish_reason": finish,
            }
        except Exception as exc:  # noqa: BLE001
            print(f"Gemini error: {exc}")
            return {
                "text": "No pude generar una respuesta con IA en este momento.",
                "tokens_used": 0,
                "response_time_ms": (time.time() - start) * 1000,
                "success": False,
                "finish_reason": "exception",
                "error": str(exc),
            }


gemini_text_service = GeminiTextService()


