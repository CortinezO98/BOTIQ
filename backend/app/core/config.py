from functools import lru_cache
from typing import Any, Dict, List
import json
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings

# Valor por defecto de desarrollo. Se usa también para detectar si alguien
# olvidó sobreescribir SECRET_KEY en un .env de producción real.
_DEV_SECRET_KEY = "dev-secret-change-in-production-32chars!!"


def _normalize_widget_origin(value: str) -> str:
    """Normaliza origins configurados y falla al iniciar si son inválidos."""
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()

    if scheme not in {"http", "https"} or not hostname:
        raise ValueError(
            f"Origin inválido en WIDGET_PORTALS_JSON: {raw!r}."
        )
    if parsed.username or parsed.password:
        raise ValueError(
            f"El origin {raw!r} no puede contener credenciales."
        )
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError(
            f"El origin {raw!r} no puede contener ruta, query o fragmento."
        )

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"Puerto inválido en el origin {raw!r}.") from exc

    if port and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        return f"{scheme}://{hostname}:{port}"
    return f"{scheme}://{hostname}"


class Settings(BaseSettings):
    APP_NAME: str = "BOTIQ"
    APP_VERSION: str = "1.17.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    APP_TIMEZONE: str = "America/Bogota"

    DATABASE_URL: str = "postgresql://botiq_user:botiq_pass@db:5432/botiq_db"

    SECRET_KEY: str = _DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ── Sesión por cookie httpOnly + refresh token ──────────────────────────
    # El access token JWT sigue viviendo también en el body de /auth/login
    # (compatibilidad con Swagger/Postman/scripts), pero el navegador ya no
    # lo guarda en localStorage: usa estas cookies httpOnly automáticamente.
    ACCESS_TOKEN_COOKIE_NAME: str = "botiq_access_token"
    REFRESH_TOKEN_COOKIE_NAME: str = "botiq_refresh_token"
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # Ventana en la que un refresh token recién rotado todavía se acepta.
    # Absorbe ráfagas de peticiones concurrentes (varias pestañas, varias
    # llamadas paralelas del frontend) que llegan con la cookie vieja antes
    # de que el navegador termine de aplicar la nueva. Sin esto, la primera
    # petición en llegar rota el token con éxito y todas las demás quedan
    # rechazadas en cascada, aunque la sesión sea legítima.
    REFRESH_TOKEN_GRACE_SECONDS: int = 15

    # ── MFA (TOTP) ───────────────────────────────────────────────────────
    # Opt-in por ahora (no forzado): cada admin decide activarlo desde su
    # cuenta. MFA_CHALLENGE_TOKEN_EXPIRE_MINUTES es la ventana para completar
    # /auth/mfa/verify después de un login con password correcto.
    MFA_ISSUER_NAME: str = "BOTIQ"
    MFA_CHALLENGE_TOKEN_EXPIRE_MINUTES: int = 5
    MFA_VERIFY_RATE_LIMIT: str = "5/minute"

    GCP_PROJECT_ID: str = ""
    GCP_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    VERTEX_FAST_MODEL: str = "gemini-2.5-flash"
    VERTEX_REASONING_MODEL: str = "gemini-2.5-pro"
    VERTEX_MULTIMODAL_MODEL: str = "gemini-2.5-flash"
    VERTEX_EMBEDDING_MODEL: str = "text-multilingual-embedding-002"

    @property
    def VERTEX_GEMINI_MODEL(self) -> str:
        return self.VERTEX_FAST_MODEL

    @property
    def VERTEX_VISION_MODEL(self) -> str:
        return self.VERTEX_MULTIMODAL_MODEL

    # Controles de IA / tokens.
    # Se reducen por defecto para evitar consumos altos en Vertex.
    RAG_TOP_K: int = 4
    RAG_MIN_CONFIDENCE: float = 0.72
    MAX_OUTPUT_TOKENS: int = 700
    VERTEX_TIMEOUT_SECONDS: int = 30

    # Optimización de RAG: menos chunks y contexto más corto.
    RAG_MAX_CHUNKS_TO_PROMPT: int = 4
    RAG_MAX_CONTEXT_CHARS: int = 5000
    RAG_CHUNK_SIZE_WORDS: int = 280
    RAG_ANSWER_MAX_OUTPUT_TOKENS: int = 800
    WEB_ANSWER_MAX_OUTPUT_TOKENS: int = 700

    # Evita gasto en Gemini para clasificar intención cuando bastan reglas.
    INTENT_CLASSIFIER_USE_GEMINI: bool = False

    # Si es consulta general de Excel/Word/Outlook/etc. se omite RAG interno.
    EMPLOYEE_GENERAL_TECH_SKIP_RAG: bool = True

    # Búsqueda web controlada: solo fallback para soporte técnico general, nunca para datos internos.
    WEB_SEARCH_ENABLED: bool = False
    WEB_SEARCH_PROVIDER: str = "google_custom_search"
    WEB_SEARCH_API_URL: str = ""
    WEB_SEARCH_API_KEY: str = ""
    WEB_SEARCH_CX: str = ""
    WEB_SEARCH_TIMEOUT_SECONDS: int = 8
    WEB_SEARCH_MAX_RESULTS: int = 5
    WEB_SEARCH_DAILY_LIMIT: int = 100
    WEB_KNOWLEDGE_AUTO_REGISTER: bool = True
    WEB_KNOWLEDGE_APPROVAL_REQUIRED: bool = True
    WEB_KNOWLEDGE_APPROVED_MIN_SCORE: int = 72

    # Último recurso para preguntas de ofimática general (Excel/Word/Windows/
    # navegador) cuando FAQ, RAG y búsqueda web no resolvieron nada. Gemini
    # responde con su propio conocimiento, dejando claro que NO es política
    # interna de IQ. Nunca se usa para preguntas internas/mixtas (eso
    # seguiría yendo a "no encontré información" para no inventar sobre
    # aplicativos/portales internos que el modelo no conoce).
    GENERAL_AI_FALLBACK_ENABLED: bool = True
    # Aumentado de 500 a 800: las respuestas de paso a paso para impresoras,
    # Excel, etc. se cortaban a mitad de frase con 500 tokens.
    GENERAL_AI_ANSWER_MAX_OUTPUT_TOKENS: int = 800

    DOCUMENT_AI_PROCESSOR_ID: str = ""
    DOCUMENT_AI_LOCATION: str = "us"

    GDRIVE_FOLDER_ID: str = ""
    # Múltiples carpetas raíz separadas por coma. Cada una se recorre de forma
    # recursiva. Útil cuando hay carpetas en "Compartido conmigo" con distintos
    # propietarios. GDRIVE_FOLDER_ID (singular) se mantiene por compatibilidad.
    GDRIVE_FOLDER_IDS: str = ""
    GCS_BUCKET_NAME: str = "botiq-images-bucket"

    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "botiq_knowledge_base"

    # Base de conocimiento de SERVIDORES (memoria/RAM y estado), totalmente
    # separada de la base de conocimiento de soporte: carpeta de Drive propia
    # y colección propia en ChromaDB, para que la búsqueda semántica de una
    # no traiga resultados de la otra.
    GDRIVE_SERVERS_FOLDER_ID: str = ""
    GDRIVE_SERVERS_FOLDER_IDS: str = ""

    CHROMA_SERVERS_COLLECTION_NAME: str = "botiq_servers_knowledge_base"

    # Archivos sueltos de Drive (sin carpeta contenedora) para la base de
    # conocimiento de SERVIDORES. Útil cuando el archivo (ej. la hoja de
    # memoria/RAM) no vive en ninguna carpeta que valga la pena compartir
    # completa -- se apunta directo al archivo por su ID.
    GDRIVE_SERVERS_FILE_ID: str = ""
    GDRIVE_SERVERS_FILE_IDS: str = ""

    # gid de la pestaña específica dentro del archivo de Google Sheets que
    # contiene la tabla de servidores (memoria/RAM/disco/estado). Necesario
    # porque el export genérico de Drive a CSV siempre trae la PRIMERA
    # pestaña, sin importar cuál esté configurada como GDRIVE_SERVERS_FILE_ID
    # -- si la tabla vive en otra pestaña, hay que decirle explícitamente
    # cuál leer. Se obtiene del parámetro ?gid=NUMERO en la URL del Sheet.
    # Vacío = usa el comportamiento viejo (export CSV de la primera pestaña).
    GDRIVE_SERVERS_SHEET_GID: str = ""

    # Sincronización automática e indicadores de salud para la KB de
    # servidores. El scheduler ejecuta sync incremental, no reindexación
    # completa: si el hash del Sheet no cambió, no genera embeddings nuevos.
    SERVERS_KB_SYNC_INTERVAL_MINUTES: int = 10
    SERVERS_KB_SYNC_ON_STARTUP: bool = True
    SERVERS_KB_STARTUP_DELAY_SECONDS: int = 5
    SERVERS_KB_SNAPSHOT_CACHE_SECONDS: int = 60
    SERVERS_KB_STALE_AFTER_MINUTES: int = 45
    SERVERS_KB_CPU_ALERT_PCT: float = 80.0
    SERVERS_KB_RAM_ALERT_PCT: float = 85.0
    SERVERS_KB_DISK_ALERT_PCT: float = 90.0

    # API externa de estados / disponibilidad de aplicativos.
    # Esta API es insumo interno del bot, no se expone directamente al usuario.
    APPLICATION_STATUS_API_URL: str = ""
    APPLICATION_STATUS_API_KEY: str = ""
    APPLICATION_STATUS_TIMEOUT_SECONDS: int = 10

    # Compatibilidad con el módulo antiguo de servidores.
    SERVER_DASHBOARD_API_URL: str = ""
    SERVER_DASHBOARD_API_KEY: str = ""

    # Integración Aranda.
    # ── Integración Aranda SERVICE DESK (ASDK) ──────────────────────────────
    # El API real de ASDK NO usa una API key estática: se autentica con
    # usuario/contraseña contra /user/login, que devuelve un sessionId (token)
    # de sesión. Ese token se manda como header "Authorization: {token}" (sin
    # prefijo "Bearer") en cada llamada posterior, y expira -- hay que
    # renovarlo (/session/renew) o volver a loguearse si una llamada falla
    # por sesión inválida. Ver app/services/aranda_service.py.
    #
    # Si ARANDA_BASE_URL está vacío, BOTIQ no crea ticket real y deja el caso
    # marcado como elegible ("pending_configuration").
    ARANDA_BASE_URL: str = ""
    ARANDA_API_VERSION: str = "v8.6"
    ARANDA_USERNAME: str = ""
    ARANDA_PASSWORD: str = ""

    # Campos obligatorios para crear un caso (item/add) que no tienen un
    # valor dinámico natural desde la conversación de BOTIQ -- se configuran
    # una vez según cómo esté armado el proyecto de Aranda del cliente.
    ARANDA_AUTHOR_ID: str = ""       # Usuario (de Aranda) que queda como autor de los casos creados por BOTIQ.
    ARANDA_GROUP_ID: str = ""        # Grupo de especialistas que atiende los casos.
    ARANDA_SLA_ID: str = ""          # SLA aplicado a los casos creados por BOTIQ.
    ARANDA_PROJECT_ID: str = ""
    ARANDA_CATEGORY_ID: str = ""
    ARANDA_SERVICE_ID: str = ""
    ARANDA_REGISTRY_TYPE_ID: str = ""  # Medio de registro (ej. "Web", "Chatbot" si existe esa opción en el proyecto).
    ARANDA_ITEM_TYPE: int = 1        # 1=Incidente, 2=Problema, 3=Cambio, 4=Requerimiento de servicio.

    ARANDA_TIMEOUT_SECONDS: int = 15

    # Controles de consumo y seguridad conversacional.
    MAX_QUESTIONS_PER_SESSION: int = 8
    MAX_OUT_OF_SCOPE_PER_SESSION: int = 1
    MAX_MESSAGE_LENGTH: int = 1200
    MIN_RESOLUTION_ATTEMPTS_BEFORE_TICKET: int = 2
    REQUIRE_SUPPORT_NETWORK_VALIDATION: bool = True
    SUPPORT_ALLOWED_EMAIL_DOMAINS: str = "iq-online.com"

    # Dominios permitidos para auto-registro público en /auth/register.
    # Vacío = sin restricción (NO recomendado en producción). Antes de este
    # cambio, /auth/register no validaba dominio: cualquiera con la URL
    # podía crear una cuenta "employee" y consultar al bot.
    REGISTRATION_ALLOWED_EMAIL_DOMAINS: str = "iq-online.com"

    BUSINESS_SCOPE_KEYWORDS: str = (
        "portal,sistema,aplicacion,aplicación,aplicativo,app,url,pagina,página,ip,"
        "correo,outlook,excel,word,teams,vpn,contraseña,password,login,acceso,"
        "servidor,server,base de conocimiento,documentación,documentacion,"
        "procedimiento,incidente,soporte,aranda,ticket,red,firewall,certificado,"
        "ssl,backup,memoria,cpu,disco,latencia,caido,caído,no responde,error"
    )

    OUT_OF_SCOPE_KEYWORDS: str = (
        "chiste,novia,novio,apuesta,casino,política,politica,religión,religion,"
        "sexo,droga,drogas,futbol,fútbol,receta,cocina,pelicula,película,"
        "tarea escolar,poema,cancion,canción,instagram,tiktok,horoscopo,horóscopo"
    )

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:5180,http://localhost:5190,http://localhost:3000"


    # ── Widget embebible seguro para portales externos ─────────────────────
    # El widget recomendado se carga dentro de un iframe alojado por BOTIQ.
    # Cada portal obtiene un JWT efímero mediante un intercambio backend a
    # backend; la clave del portal NUNCA se entrega al navegador.
    WIDGET_ENABLED: bool = False
    WIDGET_PUBLIC_URL: str = "http://localhost:5180"
    WIDGET_TOKEN_EXPIRE_MINUTES: int = 10
    WIDGET_TOKEN_ISSUER: str = "botiq"
    WIDGET_TOKEN_AUDIENCE: str = "botiq-widget"
    WIDGET_TOKEN_RATE_LIMIT: str = "30/minute"
    WIDGET_AUTO_PROVISION_USERS: bool = True

    # JSON de portales autorizados. Formato:
    # [
    #   {
    #     "id": "portal-icetex",
    #     "secret": "secreto-aleatorio-minimo-32-caracteres",
    #     "origins": ["https://portal.example.com"],
    #     "email_domains": ["iq-online.com"],
    #     "auto_provision": true
    #   }
    # ]
    #
    # También acepta un objeto por id:
    # {"portal-icetex": {"secret": "...", "origins": [...]}}
    WIDGET_PORTALS_JSON: str = "[]"

    # ── Rate limiting ──────────────────────────────────────────────────────────
    # Límites por IP. Formato: "N/period" (slowapi/limits).
    # En producción se recomienda bajar LOGIN_RATE_LIMIT a "5/minute".
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT: str = "10/minute"      # /auth/login y /auth/register
    CHAT_RATE_LIMIT: str = "30/minute"       # /chat/message
    API_RATE_LIMIT: str = "120/minute"       # resto de endpoints autenticados


    def get_widget_portals(self) -> List[Dict[str, Any]]:
        """Devuelve la configuración normalizada de portales embebibles."""
        raw = (self.WIDGET_PORTALS_JSON or "[]").strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "WIDGET_PORTALS_JSON no contiene JSON válido."
            ) from exc

        if isinstance(parsed, dict):
            items = []
            for portal_id, value in parsed.items():
                if not isinstance(value, dict):
                    raise ValueError(
                        "Cada portal de WIDGET_PORTALS_JSON debe ser un objeto."
                    )
                items.append({"id": portal_id, **value})
        elif isinstance(parsed, list):
            items = parsed
        else:
            raise ValueError(
                "WIDGET_PORTALS_JSON debe ser una lista o un objeto."
            )

        normalized: List[Dict[str, Any]] = []
        seen_ids = set()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(
                    "Cada portal de WIDGET_PORTALS_JSON debe ser un objeto."
                )

            portal_id = str(item.get("id") or "").strip()
            secret = str(item.get("secret") or "").strip()
            origins = [
                _normalize_widget_origin(origin)
                for origin in (item.get("origins") or [])
                if str(origin).strip()
            ]
            domains = [
                str(domain).strip().lower()
                for domain in (item.get("email_domains") or [])
                if str(domain).strip()
            ]

            if not portal_id:
                raise ValueError("Cada portal debe tener un id.")
            if not all(
                char.isalnum() or char in {"-", "_", "."}
                for char in portal_id
            ) or len(portal_id) > 64:
                raise ValueError(
                    "El id del portal solo admite letras, números, punto, "
                    "guion y guion bajo, con máximo 64 caracteres."
                )
            if portal_id in seen_ids:
                raise ValueError(
                    f"Portal duplicado en WIDGET_PORTALS_JSON: {portal_id}"
                )
            if not secret:
                raise ValueError(
                    f"El portal {portal_id} no tiene secret configurado."
                )
            if not origins:
                raise ValueError(
                    f"El portal {portal_id} debe declarar al menos un origin."
                )
            if any(origin == "*" for origin in origins):
                raise ValueError(
                    f"El portal {portal_id} no puede usar origin comodín '*'."
                )

            seen_ids.add(portal_id)
            normalized.append(
                {
                    "id": portal_id,
                    "secret": secret,
                    "origins": origins,
                    "email_domains": domains,
                    "auto_provision": bool(
                        item.get(
                            "auto_provision",
                            self.WIDGET_AUTO_PROVISION_USERS,
                        )
                    ),
                }
            )

        return normalized

    def get_allowed_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    def get_gdrive_folder_ids(self) -> List[str]:
        """
        Lista de carpetas raíz de Drive a indexar (sin duplicados, en orden).
        Combina GDRIVE_FOLDER_ID (singular, compat) y GDRIVE_FOLDER_IDS (lista).
        """
        ids: List[str] = []
        if self.GDRIVE_FOLDER_ID.strip():
            ids.append(self.GDRIVE_FOLDER_ID.strip())
        for raw in self.GDRIVE_FOLDER_IDS.split(","):
            fid = raw.strip()
            if fid and fid not in ids:
                ids.append(fid)
        return ids

    def get_servers_folder_ids(self) -> List[str]:
        """
        Lista de carpetas raíz de Drive a indexar para la base de conocimiento
        de SERVIDORES (memoria/RAM), separada de la de soporte general.
        """
        ids: List[str] = []
        if self.GDRIVE_SERVERS_FOLDER_ID.strip():
            ids.append(self.GDRIVE_SERVERS_FOLDER_ID.strip())
        for raw in self.GDRIVE_SERVERS_FOLDER_IDS.split(","):
            fid = raw.strip()
            if fid and fid not in ids:
                ids.append(fid)
        return ids

    def get_servers_file_ids(self) -> List[str]:
        """
        Lista de archivos sueltos de Drive (sin carpeta) a indexar para la
        base de conocimiento de SERVIDORES. Se combinan con
        get_servers_folder_ids(): un archivo puede venir de una carpeta
        recorrida recursivamente, de esta lista directa, o de ambas fuentes
        a la vez (deduplicado por file_id en gdrive_service).
        """
        ids: List[str] = []
        if self.GDRIVE_SERVERS_FILE_ID.strip():
            ids.append(self.GDRIVE_SERVERS_FILE_ID.strip())
        for raw in self.GDRIVE_SERVERS_FILE_IDS.split(","):
            fid = raw.strip()
            if fid and fid not in ids:
                ids.append(fid)
        return ids

    def get_support_allowed_domains(self) -> List[str]:
        return [d.strip().lower() for d in self.SUPPORT_ALLOWED_EMAIL_DOMAINS.split(",") if d.strip()]

    def get_registration_allowed_domains(self) -> List[str]:
        return [d.strip().lower() for d in self.REGISTRATION_ALLOWED_EMAIL_DOMAINS.split(",") if d.strip()]

    def get_business_keywords(self) -> List[str]:
        return [k.strip().lower() for k in self.BUSINESS_SCOPE_KEYWORDS.split(",") if k.strip()]

    def get_out_of_scope_keywords(self) -> List[str]:
        return [k.strip().lower() for k in self.OUT_OF_SCOPE_KEYWORDS.split(",") if k.strip()]

    @model_validator(mode="after")
    def _validate_production_safety(self) -> "Settings":
        """
        Bloquea el arranque si ENVIRONMENT=production pero la configuración
        todavía tiene valores de desarrollo peligrosos. Esto evita que un
        .env.prod mal copiado (o nunca sobreescrito) llegue a producción
        con la SECRET_KEY pública del repo o con DEBUG=True.

        Si esto revienta el arranque en tu entorno, es intencional: significa
        que backend/.env.prod todavía no tiene SECRET_KEY propio o DEBUG=false.
        """
        if self.ENVIRONMENT.lower() == "production":
            problems: List[str] = []
            if self.SECRET_KEY == _DEV_SECRET_KEY or len(self.SECRET_KEY) < 32:
                problems.append(
                    "SECRET_KEY sigue siendo el valor de desarrollo o es demasiado corto "
                    "(mínimo 32 caracteres). Genera uno con: "
                    "python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            if self.DEBUG:
                problems.append("DEBUG=true en ENVIRONMENT=production. Debe ser false.")

            if self.WIDGET_ENABLED:
                if not self.WIDGET_PUBLIC_URL.lower().startswith("https://"):
                    problems.append(
                        "WIDGET_PUBLIC_URL debe usar HTTPS en producción."
                    )
                try:
                    widget_portals = self.get_widget_portals()
                except ValueError as exc:
                    problems.append(str(exc))
                    widget_portals = []

                if not widget_portals:
                    problems.append(
                        "WIDGET_ENABLED=true pero WIDGET_PORTALS_JSON está vacío."
                    )

                for portal in widget_portals:
                    if len(portal["secret"]) < 32:
                        problems.append(
                            f"El secret del portal {portal['id']} debe tener "
                            "al menos 32 caracteres aleatorios."
                        )
                    for origin in portal["origins"]:
                        if not origin.lower().startswith("https://"):
                            problems.append(
                                f"El origin {origin} del portal {portal['id']} "
                                "debe usar HTTPS en producción."
                            )

            if problems:
                raise ValueError(
                    "Configuración insegura para producción:\n- " + "\n- ".join(problems)
                )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
