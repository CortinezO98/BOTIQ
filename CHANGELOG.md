# Changelog — BOTIQ

Todos los cambios notables de este proyecto están documentados aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).
Versionamiento basado en [SemVer](https://semver.org/lang/es/).

---

## [1.5.0] — 2026-07-14

Cierre del primer sprint de estabilización técnica (Fase 1 de la auditoría SWEBOK).

### Corregido
- **Crash de `useChat.js` en runtime**: el hook usaba `useState`, `useCallback` y `useRef` sin importarlos de `react`. Afectaba a `ChatWidget` completo (`Uncaught ReferenceError: useState is not defined`).
- **Crash de `ChatWidget/index.jsx` en runtime**: mismo patrón — `useState`, `useEffect` y `useRef` usados sin importar. Además tenía una llave de cierre duplicada (`}}`) al final de `SatisfactionModal` que producía un error de sintaxis.
- **Crash de `Dashboard/index.jsx` en runtime**: mismo patrón — `useState`, `useEffect` y `useMemo` usados sin importar (`Uncaught ReferenceError: useMemo is not defined`).
- **`feedback.py` e `incidents.py` no estaban registrados** en `api/v1/__init__.py`: los botones de feedback 👍/👎 y la encuesta de satisfacción del frontend (`useChat.js: submitFeedback`, `submitSatisfaction`) fallaban con 404 porque el router nunca se montó. Ahora `feedback.router` se monta bajo `/chat` (coincide con lo que ya llama `api.js`) e `incidents.router` se monta bajo `/admin` y `/dashboard` (según su propio diseño original: aprobación de respuestas de IA general y alertas de incidentes masivos).
- **`LOGIN_RATE_LIMIT` y `CHAT_RATE_LIMIT` definidos pero nunca aplicados**: solo el límite global `API_RATE_LIMIT` (120/min) protegía `/auth/login`. Ahora `@limiter.limit(settings.LOGIN_RATE_LIMIT)` se aplica explícitamente en `/auth/login` y `/auth/register` (10/min).
- **Comparación de email inconsistente entre mayúsculas/minúsculas**: `admin.create_user` normalizaba el email a minúsculas pero `auth.register` y `auth.login` no. Ahora ambos usan `func.lower(User.email)` en la comparación, sin depender de que los emails ya existentes en la base estén guardados en minúsculas.
- **Sin validación de configuración insegura en producción**: no existía nada que impidiera arrancar con `ENVIRONMENT=production` usando el `SECRET_KEY` de desarrollo (público en el repo) o con `DEBUG=true`. Ahora `Settings` tiene un `@model_validator` que bloquea el arranque en ese caso.

### Cambiado
- `app/core/rate_limit.py` (nuevo): la instancia de `Limiter` de slowapi se extrajo de `main.py` a su propio módulo para poder importarla desde `auth.py` (y futuras routes) sin generar un import circular.
- `main.py`: ahora importa `limiter` desde `app.core.rate_limit` en vez de definirlo inline. Sin cambio de comportamiento.

### Notas de auditoría
- Se revisó todo `frontend/src/**/*.{js,jsx}` en busca del mismo patrón de hooks de React sin importar. Solo los 3 archivos listados arriba tenían el problema; el resto está correcto.
- Pendiente para el próximo sprint: JWT en `localStorage` sin refresh token (Fase 1 — Alta), `/auth/register` público sin restricción de dominio (Fase 1 — Alta), CI con `ruff`/`bandit`/`pip-audit` corriendo con `|| true` (no bloquean merges), 0 pruebas de frontend configuradas.

---

## [1.4.0] — 2026-07-02

### Agregado
- **Logging estructurado** (`app/core/logging_config.py`): reemplaza todos los `print()` por logs con formato legible en desarrollo y JSON en producción. Incluye campos `module`, `latency_ms`, `tokens_used`, `sources` en cada evento relevante.
- **Rate limiting** con `slowapi`: límite configurable por IP en todos los endpoints (default `120/minute`). Variables en `.env`: `RATE_LIMIT_ENABLED`, `LOGIN_RATE_LIMIT` (default `10/minute`), `CHAT_RATE_LIMIT` (default `30/minute`).
- **Respaldo de IA general** (`app/services/general_assistant_service.py`): último eslabón de la cadena de respuesta para preguntas de ofimática/tecnología general (Excel, Word, impresoras, Windows, etc.) cuando no hay FAQ, RAG, ni resultados de búsqueda web. Nunca se activa para preguntas internas de IQ.
- **Continuidad conversacional** en `routing_policy_service`: parámetro `previous_intent_family` permite que mensajes cortos de seguimiento ("GUIAME", "continúa", "no funcionó") hereden la clasificación del turno anterior.
- **Pruebas de regresión críticas** en `tests/unit/`: `test_conversation_flow.py`, `test_application_matrix.py`, `test_routing_policy.py`, `test_rag_service.py`, `test_application_status.py`.
- **CI mejorado** (`.github/workflows/ci.yml`): agrega jobs de `ruff` (linter), `mypy` (type check inicial), `bandit` (SAST), `pip-audit` (dependencias), `pytest-cov` con umbral mínimo del 30%.
- Campo `GENERAL_AI_ANSWER_MAX_OUTPUT_TOKENS` en `config.py` (default `800`).
- Campo `RATE_LIMIT_ENABLED`, `LOGIN_RATE_LIMIT`, `CHAT_RATE_LIMIT`, `API_RATE_LIMIT` en `config.py`.

### Corregido
- **Falso positivo de matriz de aplicaciones**: naive substring matching con umbral 50 marcaba `found=True` para mensajes largos sin relación con ningún aplicativo. Corregido con regex de límites de palabra (`\b`) y umbral subido a 80.
- **"lentitud" clasificaba como `app_down`**: palabras `lento`/`lentitud` removidas de `DOWN_KW` en `conversation_flow_service`. Un mensaje sobre lentitud del PC ya no exige nombre de aplicativo/URL.
- **`_demo_lookup` usaba pregunta completa como nombre de servicio**: mensajes largos sin URL/IP ahora retornan `found=False`. Solo textos ≤40 chars se aceptan como posible nombre de aplicativo.
- **Crash de Gemini por historial mal formado**: `gemini_text_service` ahora construye objetos `Content`/`Part` reales (no diccionarios) para `start_chat`, evitando `AttributeError: history must be a list of Content objects`.
- **Pérdida de contexto en seguimientos cortos**: `_build_retrieval_query` en `support_rag_service` enriquece queries ≤60 chars con el último mensaje del usuario antes de buscar en ChromaDB.
- **"gracias" consumía ~1800 tokens**: mensajes de cortesía/cierre cortos ahora retornan `direct_response` sin llamar a Gemini ni RAG.
- **Fuga de `[Fuente: ...]`** en respuestas al usuario: `_strip_leaked_context_markers()` limpia etiquetas internas del prompt antes de mostrar la respuesta.
- **Respuesta truncada del respaldo general**: `GENERAL_AI_ANSWER_MAX_OUTPUT_TOKENS` subido de 500 a 800 para evitar cortes a mitad de frase.
- **`auth.py` crasheaba con `limiter.check()`**: `slowapi` no expone ese método — el rate limiting ya funciona vía `default_limits` en `main.py`.

### Cambiado
- `main.py`: usa `logging_config.setup_logging()` en lifespan en vez de `print()`.
- `vertex_client.py`: usa `logger.info/warning/error` en vez de `print()`.
- `gemini_text_service.py`: usa `logger.warning/error` en vez de `print()`.
- `support_rag/service.py`: usa `logger.*` en todos los puntos de indexación y generación de respuesta.
- Sistema de contexto de enrutamiento: `chat.py` guarda el `intent_family` del turno actual en `conversation.metadata_["routing"]` para que el turno siguiente lo herede.

---

## [1.3.0] — 2026-06-17

### Agregado
- **RAG incremental** con SHA-256 y tabla `knowledge_documents` (migración `20260617_0003`): omite documentos sin cambios, limpia de ChromaDB los eliminados de Drive.
- **Historial conversacional en RAG**: `chat.py` carga los últimos 6 turnos y los pasa a `support_rag_service.generate_response()`.
- **Búsqueda web controlada**: Google Custom Search como fallback para ofimática general. Variables `WEB_SEARCH_ENABLED`, `WEB_SEARCH_API_KEY`, `WEB_SEARCH_CX`.
- **Web knowledge cache**: respuestas web quedan pendientes de aprobación admin; si se aprueban, se reutilizan sin búsqueda.
- **Dashboard de reportes** (`/dashboard/reports`) con Recharts y 4 opciones de exportación CSV.
- **Logs de conversación** (`/dashboard/conversation-logs`) con KPI cards, filtros de fecha, modal de detalle con resumen automático.
- **Matriz de aplicaciones**: tabla `application_matrix` y servicio `application_matrix_service`.
- **Validación de usuario de red** para ingenieros de soporte con `SUPPORT_ALLOWED_EMAIL_DOMAINS`.
- Soporte `.xlsx`/`.xls` vía `openpyxl` en el pipeline de indexación.
- Traversal recursivo BFS de subcarpetas de Google Drive.
- Multi-root Drive vía `GDRIVE_FOLDER_IDS` (comma-separated).

### Corregido
- ChromaDB fijado a `0.5.0`, NumPy a `1.26.4` (incompatibilidad con NumPy 2.x).
- Cadena de migraciones Alembic rota; columna `escalated_to_aranda` añadida.

---

## [1.2.0] — 2026-06-11

### Agregado
- Roles `employee`, `support_engineer`, `admin` con control de acceso por módulo.
- Módulos: Employee Bot (FAQ + Gemini), Support RAG (Drive + ChromaDB), Server Monitor.
- Dashboard administrativo con métricas de tokens, conversaciones y brechas de conocimiento.
- Gestión de usuarios, FAQs, auditoría y control de sesiones.
- Integración con Google Drive Service Account para indexación de documentos.
- Preparación para integración con Aranda (ticket creation flow).
- Docker Compose para desarrollo y producción con Nginx.
- CI inicial en GitHub Actions.
- Autenticación JWT con bcrypt.

---

## Tipos de cambio

- `Agregado` — nuevas funcionalidades.
- `Cambiado` — cambios en funcionalidades existentes.
- `Corregido` — corrección de bugs.
- `Eliminado` — funcionalidades removidas.
- `Seguridad` — vulnerabilidades corregidas.