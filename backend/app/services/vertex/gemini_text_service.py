import time
from typing import Optional, List, Dict
from app.services.vertex.vertex_client import is_vertex_available
from app.core.config import settings

DEMO_RESPONSE = (
    "Estoy en modo demo. Para activar respuestas con IA configura "
    "GCP_PROJECT_ID y GOOGLE_APPLICATION_CREDENTIALS en el archivo .env."
)


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
        start = time.time()
        if not is_vertex_available():
            return {"text": DEMO_RESPONSE, "tokens_used": 0, "response_time_ms": (time.time()-start)*1000}
        try:
            from vertexai.generative_models import GenerativeModel, GenerationConfig
            m = model or settings.VERTEX_GEMINI_MODEL
            gm = GenerativeModel(m, system_instruction=system_instruction)
            cfg = GenerationConfig(temperature=temperature, max_output_tokens=max_output_tokens)
            history_fmt = []
            if history:
                for h in history:
                    history_fmt.append({"role": h["role"], "parts": [{"text": h["content"]}]})
            chat = gm.start_chat(history=history_fmt)
            resp = await chat.send_message_async(prompt, generation_config=cfg)
            return {
                "text": resp.text,
                "tokens_used": getattr(resp.usage_metadata, "total_token_count", None),
                "response_time_ms": (time.time()-start)*1000,
            }
        except Exception as e:
            print(f"Gemini error: {e}")
            return {"text": f"Error IA: {e}", "tokens_used": 0, "response_time_ms": (time.time()-start)*1000}


gemini_text_service = GeminiTextService()
