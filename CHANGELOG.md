# Changelog — BOTIQ

Todos los cambios notables de este proyecto están documentados aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).
Versionamiento basado en [SemVer](https://semver.org/lang/es/).

---

## [1.10.0] — 2026-07-15

MFA (TOTP) para rol admin — frontend completo (QR de enrolamiento, código en login, panel de Seguridad). Cierra el ítem "MFA para admin" del backlog de seguridad de la auditoría.

### Agregado
- **`pages/SecurityPage.jsx`** (`/dashboard/security`, nuevo link "🔒 Seguridad" en el navbar de admin): enrolar MFA con QR + código manual, confirmar activación, desactivar (pide password + código).
- **`LoginPage.jsx`**: segundo paso de verificación cuando el backend devuelve `mfa_required` — input de código de 6 dígitos, sin tocar el diseño existente del formulario de email/contraseña.
- `authAPI` en `services/api.js`: `mfaVerify`, `mfaSetup`, `mfaConfirm`, `mfaDisable`.
- `useAuth()`: nuevo método `verifyMfa(challengeToken, code)` para completar el login en dos pasos.
- **`hooks/useAuth.test.jsx`**: test de regresión para el bug de estado desincronizado (ver Corregido) — confirma que `login()` en un componente se refleja de inmediato en otro componente que también usa `useAuth()`.

### Corregido
- **Bug crítico, afectaba a todos los usuarios, no solo MFA**: `App.jsx` seguía leyendo `localStorage.getItem("botiq_user")` directamente en el componente `Guard`, en vez de usar `useAuth()`. Desde la migración a cookies httpOnly (1.6.0), nada volvía a escribir esa clave en `localStorage` — cualquier sesión nueva (o cualquier navegador/perfil sin caché vieja) quedaba en loop de redirect a `/login`, aunque el backend diera cookies de sesión válidas. Es probable que este bug ya estuviera activo en producción desde 1.6.0 y las verificaciones anteriores solo "funcionaran" por una entrada de `localStorage` vieja, previa a esa migración, que nunca se limpió.
- **`useAuth()` no compartía estado entre componentes**: `Navbar`, `ChatPage` y `LoginPage` llamaban `useAuth()` cada uno por separado, cada uno con su propio `useState` interno — un `login()` hecho desde `LoginPage` no lo veían los demás. Convertido a `AuthProvider` + Context (`hooks/useAuth.jsx`, antes `.js`): una sola fuente de verdad de sesión para toda la app.
- `hooks/useAuth.js` renombrado a `useAuth.jsx`: el archivo ahora devuelve JSX (`<AuthContext.Provider>`) y con extensión `.js` Vite no lo parsea correctamente.

### Notas de auditoría
- MFA sigue siendo opt-in (backend, ver 1.9.0). El frontend no fuerza el enrolamiento — cada admin lo activa desde Seguridad cuando quiera.
- Los dos bugs de sesión corregidos acá (`Guard` con `localStorage` muerto, `useAuth` sin Context) no eran parte del alcance original de "MFA frontend" — aparecieron al revisar `App.jsx`/`Navbar.jsx` antes de agregar la pantalla de Seguridad. Vale la pena una revisión manual del resto del frontend en busca de patrones similares (componentes que asumen datos que ya no existen tras alguna migración anterior).

---

## [1.9.0] — 2026-07-15

MFA (TOTP) para rol admin — backend completo. Opt-in por ahora, cada admin lo activa desde su cuenta.

### Agregado
- **Tabla `users` extendida** (migración `20260715_0009`): `mfa_enabled`, `mfa_secret_encrypted` (nunca en texto plano — cifrado con Fernet derivado de `SECRET_KEY`), `mfa_enrolled_at`.
- **`app/core/mfa.py`**: cifrado/descifrado del secreto TOTP, generación de secreto + QR (`pyotp` + `qrcode[pil]`), verificación de códigos de 6 dígitos con tolerancia de reloj de ±30s.
- **Enrolamiento en dos pasos**: `POST /auth/mfa/setup` (genera secreto + QR, no activa MFA todavía) → `POST /auth/mfa/confirm` (requiere un código válido para recién ahí activarlo). Evita quedar en un estado "medio configurado" si el usuario nunca llega a escanear el QR.
- **Login con desafío**: si el usuario tiene MFA activo, `POST /auth/login` ya no entrega sesión directamente — devuelve `{mfa_required: true, mfa_challenge_token}` (token de 5 min, sin cookies de sesión). `POST /auth/mfa/verify` con el código completa el login real.
- **`POST /auth/mfa/disable`**: requiere password Y código TOTP vigente (ninguno de los dos solos alcanza).
- `REGISTRATION_ALLOWED_EMAIL_DOMAINS`... *(ya existía, sin cambios)*.
- **5 tests de integración** (`tests/integration/test_mfa_flow.py`), validados contra Postgres real con códigos TOTP generados de verdad (no mockeados): enrolamiento completo, código incorrecto rechazado, disable con ambos factores, y una regresión de seguridad específica (ver Corregido).
- `pytest-env` agregado a `requirements.txt`: la sección `env =` de `pytest.ini` existía desde antes pero nunca se aplicaba (plugin ausente) — los tests corrían con la configuración real del contenedor en vez de la de test. Ahora `RATE_LIMIT_ENABLED=false` y el resto de esa sección se aplican de verdad.

### Corregido
- **Bug de seguridad real, no hipotético**: el token de desafío MFA (emitido tras password correcto, antes de pedir el segundo factor) podía usarse directamente como `Authorization: Bearer` en cualquier endpoint protegido — es decir, alguien con solo la contraseña se saltaba el segundo factor por completo. `decode_token()` ahora rechaza explícitamente cualquier token con `purpose=mfa_challenge`. No afecta sesiones ya emitidas (esas no llevan ese claim). Encontrado por un test escrito específicamente para esta regresión de diseño, no detectado durante el desarrollo inicial.

### Notas de auditoría
- MFA queda **opt-in**, no forzado: cada admin decide activarlo desde su cuenta. Si se quiere volver obligatorio para el rol admin más adelante, hace falta un flag de configuración adicional y una pantalla de "enrolamiento forzado" en el primer login — no implementado todavía.
- Pendiente: frontend (pantalla de enrolamiento con QR, input de código de 6 dígitos en login, opción de apagar MFA en configuración de cuenta).
- Deuda de infraestructura de testing detectada de paso: los tests corren contra la base de datos real de desarrollo (`db:5432/botiq_db`), no contra una base aislada — a diferencia de CI, que sí usa un Postgres efímero. Mejora pendiente, no urgente.

---

## [1.8.0] — 2026-07-15

Primeras pruebas de frontend con `vitest`, y ESLint funcionando de verdad por primera vez en el proyecto.

### Agregado
- **`vitest` + `@testing-library/react` + `jsdom`** en `frontend/`. Scripts `npm run test` (una sola pasada, usado en CI) y `npm run test:watch` (desarrollo).
- **3 tests de regresión**: `hooks/useChat.test.js`, `components/ChatWidget/index.test.jsx`, `components/Dashboard/index.test.jsx` — verifican que cada componente se monta sin `ReferenceError`. Validados contra el bug real de la versión 1.5.0 (hooks de React sin importar): corridos contra las versiones rotas antes de esta entrada, fallan con el mismo error que se veía en el navegador; contra las versiones corregidas, pasan.
- **Configuración de ESLint** (clave `eslintConfig` en `package.json`, no un `.eslintrc.cjs` separado — el proyecto no tenía ninguna config de ESLint hasta ahora, y un archivo `.eslintrc.cjs` resultó estar excluido por `.dockerignore`, invisible para el contenedor). Incluye `eslint-plugin-react-hooks`, que faltaba a pesar de que 3 páginas ya tenían comentarios `eslint-disable-next-line react-hooks/exhaustive-deps` para una regla que no existía sin el plugin.
- CI: el job `frontend-tests` ahora corre `npm run test` (antes solo hacía lint + build, sin ejecutar ningún test).

### Corregido
- `Dashboard/index.jsx`: eliminada una línea muerta (`responsiveStyle = document.createElement ? null : null`, no hacía nada) y agregado el mismo comentario `eslint-disable` de `exhaustive-deps` que ya usaban `ConversationLogsPage`/`FaqsPage`/`ReportsPage` para el mismo patrón (efecto que llama a `load()` intencionalmente sin todas las dependencias).
- `LoginPage.jsx`: el `catch {}` vacío del login ahora tiene un comentario explicando que el estado de error ya lo expone `useAuth` — mismo comportamiento, solo deja de ser un bloque vacío sin explicación.
- `UsersPage.jsx`: eliminada la constante `ROLE_LABELS`, sin uso — el `<select>` de cambio de rol ya tenía las etiquetas escritas directamente en las opciones (código muerto de una refactorización anterior).

### Notas de auditoría
- Ninguno de los 3 fixes de código muerto cambia comportamiento visible; son limpieza encontrada al activar ESLint por primera vez sobre código que nunca se había lintado.
- Pendiente: MFA para rol `admin`, CSP en `nginx.conf`, plan de actualización de dependencias con vulnerabilidades conocidas de salto de versión mayor (`Pillow`, `aiohttp`, `pypdf`, `protobuf`, `starlette`).

---

## [1.7.0] — 2026-07-14

Continuación del backlog de Fase 1: pruebas de sesión, cierre de `/auth/register`, y primeras dependencias actualizadas por seguridad.

### Agregado
- **Pruebas de integración** (`tests/integration/test_auth_session.py`): cubren cookies httpOnly en login, `/auth/me` vía cookie sin header, rotación de refresh token (el usado queda inválido), `/auth/refresh` sin cookie → 401, `/auth/logout`, y login case-insensitive. Cierra la deuda dejada en 1.6.0.
- `REGISTRATION_ALLOWED_EMAIL_DOMAINS` en `config.py` (default `iq-online.com`): `/auth/register` ahora rechaza con 403 cualquier dominio fuera de la lista. Antes cualquiera con la URL podía autoregistrarse como `employee`.
- CI: `pip-audit` bloqueante para las dependencias ya auditadas (`python-dotenv`, `pytest`, `pytest-asyncio`); el resto de `requirements.txt` se sigue reportando sin bloquear, pendiente de un plan de actualización mayor (`Pillow`, `aiohttp`, `pypdf`, `protobuf`, `starlette`, `ecdsa` — todos requieren saltos de versión mayor con pruebas de compatibilidad propias).

### Cambiado
- `requirements.txt`: `python-dotenv` 1.0.1→1.2.2, `pytest` 8.2.0→9.0.3, `pytest-asyncio` 0.23.7→1.4.0 (vulnerabilidades reportadas por `pip-audit`, verificadas sin romper nada antes de subir).
- `pytest.ini`: `asyncio_default_fixture_loop_scope` y `asyncio_default_test_loop_scope` en `session`, reemplazando el fixture `event_loop` manual de `tests/conftest.py`.
- `.github/workflows/ci.yml`: se eliminó un `pip install pytest pytest-asyncio httpx pytest-cov` sin versión fija que pisaba silenciosamente los pines de `requirements.txt` en cada corrida de CI.

### Corregido
- **Regresión introducida por el bump de `pytest-asyncio`**: el fixture `event_loop(scope="session")` de `tests/conftest.py` dejó de ser respetado por `pytest-asyncio` 1.x. Cada test pasó a correr en un event loop nuevo, pero el pool de conexiones async de SQLAlchemy (creado una sola vez a nivel de módulo) quedaba con conexiones anclabas al loop del primer test, causando `RuntimeError: ... attached to a different loop` en tests que reutilizaban una conexión pooleada de un test anterior. Reproducido con Postgres real antes de corregir; solucionado configurando el scope de sesión directamente en `pytest.ini` en vez de sobreescribir el fixture.

### Notas de auditoría
- Pendiente: plan de actualización para `Pillow`, `aiohttp`, `pypdf`, `protobuf` y `starlette` (saltos de versión mayor, requieren pruebas de compatibilidad — `pypdf` en particular puede afectar `document_ai_service.py`). `ecdsa` no tiene fix disponible todavía (dependencia transitiva).

---

## [1.6.0] — 2026-07-14

Migración de sesión: JWT en `localStorage` → cookies `httpOnly` + refresh token con rotación (backlog de seguridad de la auditoría SWEBOK, Fase 1 — Alta prioridad).

### Agregado
- **Tabla `refresh_tokens`** (migración `20260714_0008`): guarda el hash SHA-256 del refresh token (nunca el valor real), con `expires_at`, `revoked_at` y `user_agent` para trazabilidad básica. Permite revocar sesiones individuales sin tocar el `SECRET_KEY` global.
- **`POST /auth/refresh`**: renueva la sesión leyendo el refresh token de la cookie httpOnly. Rotación en cada llamada — el token usado se revoca y se emite uno nuevo, así un refresh token robado deja de servir apenas el dueño real lo use.
- **`POST /auth/logout`**: revoca el refresh token activo en base de datos y limpia ambas cookies.
- **Cookies `httpOnly`** en `/auth/login`: `botiq_access_token` (misma duración que el JWT, `path=/`) y `botiq_refresh_token` (30 días, restringida a `path=/api/v1/auth` para que no viaje en cada request de la API). `Secure` se activa solo en producción (nginx sirve HTTPS real); `SameSite=Lax` alcanza porque `localhost:5180` → `localhost:8002` es cross-*origin* pero mismo *site*.
- `app/core/security.py`: `generate_refresh_token()` (token opaco de alta entropía, no JWT) y `hash_refresh_token()`.
- `app/core/config.py`: `ACCESS_TOKEN_COOKIE_NAME`, `REFRESH_TOKEN_COOKIE_NAME`, `REFRESH_TOKEN_EXPIRE_DAYS` (default 30).
- **Interceptor de renovación silenciosa** en `frontend/src/services/api.js`: ante un 401, intenta `/auth/refresh` una vez y reintenta la petición original antes de dar la sesión por expirada.

### Cambiado
- `app/api/deps.py`: `get_current_user` ahora acepta el token por header `Authorization: Bearer` **o** por cookie httpOnly (en ese orden), sin romper compatibilidad con Swagger/Postman/scripts que ya usaban el header.
- `app/api/v1/routes/auth.py`: `/login` sigue devolviendo `access_token` en el body (compatibilidad), pero además setea las cookies de sesión. `/login` y `/register` ahora comparan el email de forma case-insensitive (`func.lower`) en vez de asumir que ya está normalizado en la base.
- `frontend/src/hooks/useAuth.js`: ya no guarda token ni usuario en `localStorage`. La sesión se valida contra `/auth/me` en cada carga de página (cookie httpOnly viaja sola). `logout()` ahora es async y llama a `/auth/logout` antes de limpiar el estado local.
- `frontend/src/services/api.js`: cliente axios con `withCredentials: true` (necesario para que el navegador mande/reciba las cookies en llamadas cross-origin `:5180` → `:8002`).

### Notas de auditoría
- Pendiente: pruebas de integración para `/auth/refresh` y `/auth/logout` (hoy solo hay verificación manual). Agregar en el sprint de testing de Fase 1.
- No se implementó límite de sesiones concurrentes por usuario ni un endpoint de "cerrar todas mis sesiones" — queda como mejora de Fase 2 si se necesita.

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