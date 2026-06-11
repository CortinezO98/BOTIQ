from dataclasses import dataclass
from typing import Optional
from app.models.conversation import ModuleType

SERVER_KW = {"servidor","server","caído","caido","down","memoria","cpu","disco","infraestructura",
             "máquina","ambiente","productivo","latencia","lento","no responde","uptime","ping"}
SUPPORT_KW = {"documentación","procedimiento","proceso","configurar","configuración","manual",
              "firewall","red","ldap","directorio activo","certificado","ssl","backup","respaldo",
              "base de datos","query","script","cómo se hace"}
EMPLOYEE_KW = {"portal","acceso","contraseña","password","login","error en word","error en excel",
               "error en outlook","no puedo abrir","no puedo entrar","correo","impresora","vpn",
               "instalar","desinstalar","actualizar","teams"}


@dataclass
class IntentResult:
    module: ModuleType
    confidence: float
    method: str
    reason: Optional[str] = None


class IntentClassifierService:

    async def classify(self, message: str) -> IntentResult:
        msg = message.lower()
        srv = sum(1 for kw in SERVER_KW if kw in msg)
        rag = sum(1 for kw in SUPPORT_KW if kw in msg)
        emp = sum(1 for kw in EMPLOYEE_KW if kw in msg)
        best = max(srv, rag, emp)

        if best >= 2:
            if srv == best:
                return IntentResult(ModuleType.SERVER_VALIDATION, min(0.95, 0.6+srv*0.1), "keyword", f"{srv} keywords de servidor")
            elif rag == best:
                return IntentResult(ModuleType.SUPPORT_RAG, min(0.95, 0.6+rag*0.1), "keyword", f"{rag} keywords de base de conocimiento")
            else:
                return IntentResult(ModuleType.EMPLOYEE, min(0.95, 0.6+emp*0.1), "keyword", f"{emp} keywords de empleado")

        try:
            return await self._gemini_classify(message)
        except Exception as e:
            return IntentResult(ModuleType.SUPPORT_RAG, 0.4, "fallback", f"Error clasificando: {e}")

    async def _gemini_classify(self, message: str) -> IntentResult:
        from app.services.vertex.gemini_text_service import gemini_text_service
        import json
        prompt = (
            'Clasifica este mensaje en: SERVER_VALIDATION, SUPPORT_RAG o EMPLOYEE.\n'
            'Responde SOLO JSON: {"module":"...","confidence":0.0-1.0,"reason":"..."}\n'
            f'Mensaje: {message}'
        )
        result = await gemini_text_service.generate(prompt=prompt, temperature=0.1, max_output_tokens=80)
        try:
            text = result["text"].strip().replace("```json","").replace("```","").strip()
            data = json.loads(text)
            mod_map = {"SERVER_VALIDATION": ModuleType.SERVER_VALIDATION,
                       "SUPPORT_RAG": ModuleType.SUPPORT_RAG, "EMPLOYEE": ModuleType.EMPLOYEE}
            return IntentResult(
                module=mod_map.get(data.get("module","SUPPORT_RAG"), ModuleType.SUPPORT_RAG),
                confidence=float(data.get("confidence", 0.7)),
                method="gemini", reason=data.get("reason",""),
            )
        except Exception:
            return IntentResult(ModuleType.SUPPORT_RAG, 0.5, "gemini_fallback")


intent_classifier_service = IntentClassifierService()
