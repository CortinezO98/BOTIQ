from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import asyncio
import time

import httpx

from app.core.config import settings
from app.models.conversation import Conversation
from app.models.user import User


class ArandaAuthError(Exception):
    """El login contra ASDK falló (usuario/contraseña inválidos, o el servicio no responde)."""


def _to_field_value(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """ASDK espera casi todos los cuerpos de petición como un arreglo
    [{"Field": "...", "Value": ...}, ...], no como un objeto JSON plano."""
    return [{"Field": k, "Value": v} for k, v in data.items() if v is not None]


def _from_field_value(data: Any) -> Dict[str, Any]:
    """Convierte la respuesta field-value de ASDK a un dict {Field: Value}.
    Si la respuesta ya viene como objeto plano (algunos endpoints GET lo
    hacen, ej. consulta de caso), la devuelve tal cual."""
    if isinstance(data, list):
        return {item.get("Field"): item.get("Value") for item in data if isinstance(item, dict) and "Field" in item}
    if isinstance(data, dict):
        return data
    return {}


class ArandaService:
    """
    Servicio de integración con Aranda SERVICE DESK (ASDK), API v8.6.

    A diferencia de un API REST genérico, ASDK NO usa una API key estática:
    - Autenticación por sesión: POST /user/login con usuario/contraseña
      devuelve un sessionId (token) que se manda como header
      "Authorization: {token}" (SIN prefijo "Bearer") en cada llamada
      posterior.
    - El token expira. En vez de intentar rastrear el tiempo exacto de
      expiración (no documentado), este servicio detecta un fallo de
      autenticación (401 o mensaje InvalidToken/InvalidSessionId) y
      relogueá automáticamente UNA vez antes de reintentar la petición
      original -- mismo patrón que el interceptor de refresh en el
      frontend (services/api.js).
    - Casi todos los cuerpos de petición son arreglos field-value, no
      objetos JSON planos (ver _to_field_value/_from_field_value).

    BOTIQ solo debe crear tickets como última instancia, después de:
    1. Validar alcance del negocio.
    2. Revisar FAQs/base de conocimiento.
    3. Consultar estado de URL/IP/aplicativo si aplica.
    4. Agotar las validaciones mínimas configuradas.
    """

    def __init__(self):
        self._session_token: Optional[str] = None
        self._session_user_id: Optional[str] = None
        # Evita logins concurrentes duplicados si dos casos se crean casi al
        # mismo tiempo y ninguno tiene sesión todavía todavía (mismo
        # problema, mismo tipo de solución, que la condición de carrera de
        # rotación de refresh token que se corrigió en el backend de auth).
        self._session_lock = asyncio.Lock()

    def is_configured(self) -> bool:
        return bool(
            settings.ARANDA_BASE_URL
            and settings.ARANDA_USERNAME
            and settings.ARANDA_PASSWORD
            and settings.ARANDA_AUTHOR_ID
            and settings.ARANDA_GROUP_ID
            and settings.ARANDA_SLA_ID
            and settings.ARANDA_PROJECT_ID
            and settings.ARANDA_CATEGORY_ID
            and settings.ARANDA_SERVICE_ID
            and settings.ARANDA_REGISTRY_TYPE_ID
        )

    def get_missing_config(self) -> List[str]:
        """Para diagnóstico: qué variables de entorno faltan si is_configured() es False."""
        required = {
            "ARANDA_BASE_URL": settings.ARANDA_BASE_URL,
            "ARANDA_USERNAME": settings.ARANDA_USERNAME,
            "ARANDA_PASSWORD": settings.ARANDA_PASSWORD,
            "ARANDA_AUTHOR_ID": settings.ARANDA_AUTHOR_ID,
            "ARANDA_GROUP_ID": settings.ARANDA_GROUP_ID,
            "ARANDA_SLA_ID": settings.ARANDA_SLA_ID,
            "ARANDA_PROJECT_ID": settings.ARANDA_PROJECT_ID,
            "ARANDA_CATEGORY_ID": settings.ARANDA_CATEGORY_ID,
            "ARANDA_SERVICE_ID": settings.ARANDA_SERVICE_ID,
            "ARANDA_REGISTRY_TYPE_ID": settings.ARANDA_REGISTRY_TYPE_ID,
        }
        return [name for name, value in required.items() if not value]

    def _base_url(self) -> str:
        return f"{settings.ARANDA_BASE_URL.rstrip('/')}/api/{settings.ARANDA_API_VERSION}"

    async def _login(self, client: httpx.AsyncClient) -> None:
        body = _to_field_value({"username": settings.ARANDA_USERNAME, "password": settings.ARANDA_PASSWORD})
        response = await client.post(f"{self._base_url()}/user/login", json=body)

        if response.status_code != 200:
            raise ArandaAuthError(f"Login Aranda falló ({response.status_code}): {response.text[:300]}")

        data = _from_field_value(response.json())
        token = data.get("sessionId")
        user_id = data.get("userId")
        if not token:
            raise ArandaAuthError("Login Aranda respondió 200 pero sin sessionId en el cuerpo.")

        self._session_token = str(token)
        self._session_user_id = str(user_id) if user_id is not None else None

    async def _ensure_session(self, client: httpx.AsyncClient) -> str:
        if self._session_token:
            return self._session_token
        async with self._session_lock:
            # Otra tarea concurrente pudo haber logueado mientras esperábamos el lock.
            if not self._session_token:
                await self._login(client)
        return self._session_token

    def _is_auth_error(self, response: httpx.Response) -> bool:
        if response.status_code == 401:
            return True
        if response.status_code == 400:
            # ASDK devuelve 400 (no 401) para token inválido en varios endpoints.
            return "InvalidToken" in response.text or "InvalidSessionId" in response.text
        return False

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        json_body: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        _retried: bool = False,
    ) -> httpx.Response:
        token = await self._ensure_session(client)
        headers = {"Content-Type": "application/json", "Authorization": token}

        response = await client.request(
            method, f"{self._base_url()}{path}", json=json_body, params=params, headers=headers
        )

        if self._is_auth_error(response) and not _retried:
            # Token vencido o inválido: descartar sesión cacheada y reintentar UNA vez.
            self._session_token = None
            self._session_user_id = None
            return await self._request(client, method, path, json_body, params, _retried=True)

        return response

    async def create_ticket(
        self,
        conversation: Conversation,
        current_user: User,
        subject: str,
        description: str,
        application_status: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            demo_id = f"BOTIQ-PENDING-{str(conversation.id)[:8]}"
            missing = self.get_missing_config()
            return {
                "created": False,
                "pending_configuration": True,
                "ticket_id": demo_id,
                "status": "pending_aranda_configuration",
                "message": (
                    "Aranda no está configurado. El caso queda marcado como elegible para ticket. "
                    f"Falta configurar: {', '.join(missing)}."
                ),
            }

        case_fields = {
            "AuthorId": int(settings.ARANDA_AUTHOR_ID),
            "CategoryId": int(settings.ARANDA_CATEGORY_ID),
            "Description": description,
            "GroupId": int(settings.ARANDA_GROUP_ID),
            "ServiceId": int(settings.ARANDA_SERVICE_ID),
            "Subject": subject[:180],
            "SlaId": int(settings.ARANDA_SLA_ID),
            "ProjectId": int(settings.ARANDA_PROJECT_ID),
            "RegistryTypeId": int(settings.ARANDA_REGISTRY_TYPE_ID),
        }

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=settings.ARANDA_TIMEOUT_SECONDS) as client:
                response = await self._request(
                    client,
                    "POST",
                    f"/item/add/{settings.ARANDA_ITEM_TYPE}",
                    json_body=_to_field_value(case_fields),
                )

            if response.status_code != 200:
                return {
                    "created": False,
                    "ticket_id": None,
                    "status": "error",
                    "message": f"Aranda respondió {response.status_code} al crear el caso: {response.text[:300]}",
                }

            data = _from_field_value(response.json())
            result_ok = str(data.get("result", "")).lower() == "true"
            composed_id = data.get("composedItemId")
            item_id = data.get("itemId")
            ticket_id = str(composed_id or item_id or "")

            if not result_ok or not ticket_id:
                return {
                    "created": False,
                    "ticket_id": None,
                    "status": "error",
                    "raw": data,
                    "message": f"Aranda no confirmó la creación del caso: {data}",
                }

            return {
                "created": True,
                "ticket_id": ticket_id,
                "item_id": item_id,
                "status": "created",
                "raw": data,
                "response_time_ms": round((time.time() - start) * 1000, 2),
                "message": f"Ticket creado correctamente en Aranda: {ticket_id}",
            }
        except ArandaAuthError as exc:
            return {
                "created": False,
                "ticket_id": None,
                "status": "error",
                "message": f"No fue posible autenticar contra Aranda: {exc}",
            }
        except Exception as exc:
            return {
                "created": False,
                "ticket_id": None,
                "status": "error",
                "message": f"No fue posible crear el ticket en Aranda: {exc}",
            }

    async def get_case(self, item_id: str, item_type: Optional[int] = None, level: int = 2) -> Dict[str, Any]:
        """
        Consulta el detalle de un caso ya creado (GET /item/{id}/{itemType}/{userId}).
        No se usa todavía desde chat.py -- queda disponible para una futura
        funcionalidad de "consultar estado de mi ticket".
        """
        if not self.is_configured():
            return {"found": False, "message": "Aranda no está configurado."}

        effective_item_type = item_type if item_type is not None else settings.ARANDA_ITEM_TYPE

        try:
            async with httpx.AsyncClient(timeout=settings.ARANDA_TIMEOUT_SECONDS) as client:
                await self._ensure_session(client)
                user_id = self._session_user_id
                response = await self._request(
                    client,
                    "GET",
                    f"/item/{item_id}/{effective_item_type}/{user_id}",
                    params={"level": level},
                )

            if response.status_code != 200:
                return {"found": False, "message": f"Aranda respondió {response.status_code}: {response.text[:300]}"}

            return {"found": True, "case": response.json()}
        except Exception as exc:
            return {"found": False, "message": f"No fue posible consultar el caso en Aranda: {exc}"}

    def build_ticket_description(self, conversation: Conversation, last_user_message: str) -> str:
        return (
            "Caso generado desde BOTIQ.\n\n"
            f"Usuario perfil seleccionado: {conversation.selected_profile}\n"
            f"Sesión: {conversation.session_id}\n"
            f"Conversación: {conversation.id}\n"
            f"Preguntas realizadas: {conversation.question_count}\n"
            f"Intentos de solución: {conversation.resolution_attempts}\n"
            f"URL detectada: {conversation.detected_url or 'No registrada'}\n"
            f"IP detectada: {conversation.detected_ip or 'No registrada'}\n"
            f"Estado aplicativo: {conversation.application_status_snapshot or 'No disponible'}\n\n"
            f"Última solicitud del usuario:\n{last_user_message}"
        )

    def mark_ticket_result(self, conversation: Conversation, result: Dict[str, Any]):
        if result.get("ticket_id"):
            conversation.aranda_ticket_id = str(result["ticket_id"])
        conversation.aranda_ticket_status = str(result.get("status") or "")
        conversation.aranda_ticket_created_at = datetime.now(timezone.utc)
        conversation.escalated_to_aranda = bool(result.get("created"))


aranda_service = ArandaService()