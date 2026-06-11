# BOTIQ — Documento de Arquitectura Técnica
**Versión:** 1.0.0 | **Referencia:** SWEBOK v4

---

## 1. Visión General del Sistema

BOTIQ es una plataforma de chatbot corporativo inteligente que integra tres módulos especializados, todos respaldados por Vertex AI de Google Cloud, con procesamiento multimodal (texto + imágenes).

---

## 2. Decisiones de Arquitectura (ADRs)

### ADR-001: FastAPI sobre Flask/Django
**Decisión:** FastAPI  
**Justificación:** Soporte nativo async/await para llamadas a Vertex AI, validación automática con Pydantic, documentación OpenAPI autogenerada, mejor rendimiento bajo carga concurrente.

### ADR-002: ChromaDB local + Vertex AI Vector Search
**Decisión:** ChromaDB en desarrollo, migrar a Vertex AI Vector Search en producción  
**Justificación:** ChromaDB reduce costos en desarrollo y permite iteración rápida. Vertex AI Vector Search escala a millones de documentos en producción.

### ADR-003: PostgreSQL para logs y métricas
**Decisión:** PostgreSQL con JSONB  
**Justificación:** JSONB permite almacenar metadatos flexibles de mensajes (fuentes RAG, scores de confianza) sin migrations frecuentes, manteniendo la capacidad de indexar y consultar.

### ADR-004: JWT sin refresh tokens (v1.0)
**Decisión:** JWT con expiración de 8 horas  
**Justificación:** Para v1.0 en red corporativa es suficiente. En v2.0 se implementará refresh token para sesiones más largas.

---

## 3. Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENTE                                  │
│                                                                  │
│  ┌───────────────────┐    ┌────────────────────────────────┐    │
│  │  React Widget     │    │     React Dashboard            │    │
│  │  (Botón flotante) │    │     (Solo Admin)               │    │
│  └─────────┬─────────┘    └──────────────┬─────────────────┘    │
│            │ HTTP/REST                   │ HTTP/REST            │
└────────────┼─────────────────────────────┼─────────────────────┘
             │                             │
             ▼                             ▼
┌────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                              │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Auth Layer  │  │  API Router  │  │  Middleware           │  │
│  │  JWT + RBAC  │  │  /api/v1/    │  │  CORS, Logging       │  │
│  └──────────────┘  └──────┬───────┘  └──────────────────────┘  │
│                           │                                     │
│           ┌───────────────┼───────────────┐                    │
│           ▼               ▼               ▼                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │  Employee   │  │  Support    │  │  Server     │           │
│  │  Module     │  │  RAG Module │  │  Monitor    │           │
│  │  (FAQ +     │  │  (GDrive +  │  │  (API +     │           │
│  │  Gemini)    │  │  Embeddings │  │  Gemini)    │           │
│  │             │  │  + ChromaDB)│  │             │           │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘           │
│         │                │                │                    │
└─────────┼────────────────┼────────────────┼────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GOOGLE CLOUD                                  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    VERTEX AI                             │   │
│  │  Gemini Pro · Gemini Vision · Embeddings · Document AI  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────┐    ┌────────────────────────────────┐    │
│  │   Google Drive   │    │    Cloud Storage (GCS)         │    │
│  │   (Base RAG)     │    │    (Imágenes temporales)       │    │
│  └──────────────────┘    └────────────────────────────────┘    │
│                                                                  │
│  ┌──────────────────┐    ┌────────────────────────────────┐    │
│  │   Cloud Vision   │    │    IAM & Service Accounts      │    │
│  │   (OCR)          │    │    (Seguridad)                 │    │
│  └──────────────────┘    └────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PERSISTENCIA LOCAL                            │
│                                                                  │
│  ┌──────────────────────┐    ┌────────────────────────────┐    │
│  │     PostgreSQL       │    │        ChromaDB            │    │
│  │  Users, Messages,    │    │   Embeddings del RAG       │    │
│  │  Conversations,      │    │   (Base de conocimiento)   │    │
│  │  FAQs, ServerLogs    │    │                            │    │
│  └──────────────────────┘    └────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  API EXTERNA (Tablero de Servidores)             │
│               Solo acceso interno desde el bot                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Modelo de Datos

### Entidades principales

```
User ──────────────── Conversation ──── Message
  │                        │
  │ rol: employee           │ módulo: employee | support_rag | server_validation
  │      support_engineer   │ escalado_a_aranda: bool
  │      admin              │
  │                    Message
  │                        │ role: user | assistant
  │                        │ has_image: bool
  │                        │ tokens_used: float
  │                        │ response_time_ms: float
  │
FAQ                   ServerLog
  │                        │
  │ question               │ server_name
  │ answer                 │ status: up | down | degraded
  │ hit_count              │ cpu_usage, memory_usage
  │ category               │ is_healthy
```

---

## 5. Flujos de Seguridad

### Autenticación
```
POST /api/v1/auth/login
    → Verificar email + bcrypt hash
    → Generar JWT (sub=user_id, role=rol, exp=8h)
    → Retornar token

Requests subsiguientes:
    Header: Authorization: Bearer <JWT>
    → Decodificar JWT
    → Verificar usuario activo en BD
    → Verificar rol mínimo para el endpoint
    → Continuar o 403
```

### Acceso al módulo de servidores
```
Usuario pregunta → Bot detecta keywords de servidor
    → Bot llama internamente a API del tablero (con API key propia)
    → Bot analiza con Gemini
    → Usuario recibe análisis en lenguaje natural
    → Usuario NUNCA accede directamente a la API del tablero
```

---

## 6. Consideraciones de Calidad (SWEBOK v4)

### Mantenibilidad
- Separación clara de capas (API, Módulos, Servicios, Modelos)
- Un módulo no conoce la implementación interna de otro
- Configuración centralizada en `config.py`

### Confiabilidad
- Try/catch en todas las llamadas externas (Vertex AI, APIs)
- Fallback graceful si Vertex AI no responde
- Health check endpoint `/health`

### Seguridad
- Credenciales nunca en código, siempre en `.env`
- `.gitignore` incluye `credentials/` y `.env`
- Roles verificados en capa de dependencias, no en lógica de negocio
- Passwords con bcrypt (salt rounds automático)

### Trazabilidad
- Cada mensaje guarda `tokens_used` y `response_time_ms`
- `conversation_id` permite reconstruir todo el contexto
- `module` permite métricas por tipo de consulta

---

## 7. Versionamiento de API

La API se versiona en la URL: `/api/v1/`

Al introducir cambios breaking:
1. Crear `/api/v2/` manteniendo `/api/v1/` activo
2. Deprecar `/api/v1/` con header `Deprecation: true`
3. Eliminar `/api/v1/` después de período de migración
