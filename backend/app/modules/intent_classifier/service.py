"""
Clasificador de intents híbrido para BOTIQ.
Nivel 1: reglas por palabras clave (rápido, sin tokens)
Nivel 2: Gemini si hay ambigüedad (preciso, consume tokens)

Retorna siempre el módulo correcto + confianza.
"""
from dataclasses import dataclass
from typing import Optional
from app.models.conversation import ModuleType


# ── Palabras clave por módulo ─────────────────────────────────────────────────

SERVER_KEYWORDS = {
    "servidor", "server", "caído", "caido", "down", "memoria",
    "cpu", "disco", "infraestructura", "máquina", "ambiente",
    "productivo", "latencia", "lento", "no responde", "caerse",
    "reiniciar", "reinicio", "uptime", "disponibilidad",
    "ping", "tiempo respuesta", "carga del sistema",
}

EMPLOYEE_KEYWORDS = {
    "portal", "acceso", "contraseña", "password", "login",
    "error en word", "error en excel", "error en outlook",
    "no puedo abrir", "no puedo entrar", "no puedo acceder",
    "correo", "email", "impresora", "vpn", "wifi",
    "instalar", "desinstalar", "actualizar",
}

SUPPORT_RAG_KEYWORDS = {
    "documentación", "procedimiento", "proceso", "cómo se hace",
    "configurar", "configuración", "manual", "guía",
    "base de datos", "tabla", "query", "script",
    "firewall", "red", "ldap", "directorio activo",
    "certificado", "ssl", "backup", "respaldo",
}

# Umbral mínimo de score para usar keywords sin Gemini
KEYWORD_CONFIDENCE_THRESHOLD = 2


@dataclass
class IntentResult:
    module: ModuleType
    confidence: float
    method: str  # "keyword" | "gemini" | "fallback"
    reason: Optional[str] = None


class IntentClassifierService:
    """
    Clasificador de intents para ingenieros de soporte y admins.
    Los empleados siempre van a ModuleType.EMPLOYEE (manejado en chat.py).
    """

    async def classify(self, message: str) -> IntentResult:
        """
        Clasifica el intent del mensaje.
        Primero intenta con keywords, luego con Gemini si hay ambigüedad.
        """
        msg_lower = message.lower()

        # ── Nivel 1: Keywords rápidos ────────────────────────────────────────
        server_score = sum(1 for kw in SERVER_KEYWORDS if kw in msg_lower)
        rag_score = sum(1 for kw in SUPPORT_RAG_KEYWORDS if kw in msg_lower)
        employee_score = sum(1 for kw in EMPLOYEE_KEYWORDS if kw in msg_lower)

        max_score = max(server_score, rag_score, employee_score)

        # Si hay una señal clara por keywords
        if max_score >= KEYWORD_CONFIDENCE_THRESHOLD:
            if server_score == max_score:
                return IntentResult(
                    module=ModuleType.SERVER_VALIDATION,
                    confidence=min(0.95, 0.6 + server_score * 0.1),
                    method="keyword",
                    reason=f"Detectadas {server_score} palabras clave de servidores",
                )
            elif rag_score == max_score:
                return IntentResult(
                    module=ModuleType.SUPPORT_RAG,
                    confidence=min(0.95, 0.6 + rag_score * 0.1),
                    method="keyword",
                    reason=f"Detectadas {rag_score} palabras clave de base de conocimiento",
                )
            else:
                return IntentResult(
                    module=ModuleType.EMPLOYEE,
                    confidence=min(0.95, 0.6 + employee_score * 0.1),
                    method="keyword",
                    reason=f"Detectadas {employee_score} palabras clave de empleado",
                )

        # ── Nivel 2: Gemini para mensajes ambiguos ───────────────────────────
        try:
            return await self._classify_with_gemini(message)
        except Exception as e:
            print(f"IntentClassifier Gemini error: {e}")
            # Fallback: RAG para ingenieros de soporte
            return IntentResult(
                module=ModuleType.SUPPORT_RAG,
                confidence=0.4,
                method="fallback",
                reason="No se pudo clasificar, usando RAG por defecto",
            )

    async def _classify_with_gemini(self, message: str) -> IntentResult:
        """Usa Gemini para clasificar mensajes ambiguos."""
        from app.services.vertex.gemini_text_service import gemini_text_service

        CLASSIFIER_PROMPT = """Clasifica este mensaje de soporte técnico en uno de estos módulos:

- SERVER_VALIDATION: Preguntas sobre estado de servidores, infraestructura, rendimiento, caídas
- SUPPORT_RAG: Consultas técnicas que requieren buscar en documentación o base de conocimiento
- EMPLOYEE: Problemas básicos de usuario: acceso, contraseñas, aplicaciones de oficina

Responde SOLO con este JSON, sin explicación ni markdown:
{"module": "SERVER_VALIDATION"|"SUPPORT_RAG"|"EMPLOYEE", "confidence": 0.0-1.0, "reason": "explicación breve"}

Mensaje a clasificar: """

        result = await gemini_text_service.generate(
            prompt=CLASSIFIER_PROMPT + message,
            temperature=0.1,
            max_output_tokens=100,
        )

        import json
        try:
            # Limpiar posible markdown
            text = result["text"].strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(text)

            module_map = {
                "SERVER_VALIDATION": ModuleType.SERVER_VALIDATION,
                "SUPPORT_RAG":       ModuleType.SUPPORT_RAG,
                "EMPLOYEE":          ModuleType.EMPLOYEE,
            }

            module = module_map.get(data.get("module", "SUPPORT_RAG"), ModuleType.SUPPORT_RAG)
            confidence = float(data.get("confidence", 0.7))
            reason = data.get("reason", "Clasificado por Gemini")

            return IntentResult(
                module=module,
                confidence=confidence,
                method="gemini",
                reason=reason,
            )

        except (json.JSONDecodeError, KeyError, ValueError):
            return IntentResult(
                module=ModuleType.SUPPORT_RAG,
                confidence=0.5,
                method="gemini_fallback",
                reason="Respuesta de Gemini no parseable",
            )


intent_classifier_service = IntentClassifierService()
