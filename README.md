# 🤖 BOTIQ — Corporate Intelligent Chatbot

> Plataforma de chatbot corporativo con IA basada en Vertex AI (Google Cloud), RAG sobre Google Drive, validación de servidores y dashboard de métricas.

---

## 📋 Tabla de Contenidos

- [Arquitectura](#arquitectura)
- [Módulos](#módulos)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Variables de Entorno](#variables-de-entorno)
- [Ejecutar el Proyecto](#ejecutar-el-proyecto)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [API Endpoints](#api-endpoints)
- [Roles y Seguridad](#roles-y-seguridad)
- [Despliegue](#despliegue)

---

## 🏛️ Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    GOOGLE CLOUD PROJECT                  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              VERTEX AI                          │   │
│  │  Gemini Pro · Gemini Vision · Embeddings        │   │
│  │  Vector Search · Document AI · Cloud Vision     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────┐    ┌─────────────────────────────┐   │
│  │ Google Drive │    │    Cloud Storage (GCS)      │   │
│  │  (Docs RAG)  │    │  (Imágenes, archivos temp)  │   │
│  └──────────────┘    └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
              │                    │
              ▼                    ▼
    ┌─────────────────┐   ┌──────────────────┐
    │  FastAPI Backend│   │  React Frontend  │
    │  Python 3.11    │   │  Vite + Tailwind │
    └─────────────────┘   └──────────────────┘
              │
              ▼
    ┌─────────────────┐
    │   PostgreSQL    │
    │   (Métricas,    │
    │   Usuarios,     │
    │   Conversacion) │
    └─────────────────┘
```

---

## 🧩 Módulos

| Módulo | Descripción | Roles |
|--------|-------------|-------|
| **Empleados** | FAQ + Gemini para preguntas frecuentes corporativas | Todos |
| **Ingeniero de Soporte** | RAG sobre base de conocimiento en Google Drive | Ing. Soporte + Admin |
| **Validación de Servidores** | Consulta API del tablero + análisis con Gemini | Bot interno (todos ven resultado) |
| **Dashboard** | Métricas, consultas frecuentes, estado de servidores | Admin |

---

## ⚙️ Requisitos

- Python 3.11+
- Node.js 20+
- Docker + Docker Compose
- Cuenta Google Cloud con Vertex AI habilitado
- PostgreSQL 15+

---

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_ORG/BOTIQ.git
cd BOTIQ
```

### 2. Configurar variables de entorno

```bash
cp backend/.env.example backend/.env
# Editar backend/.env con tus credenciales
```

### 3. Levantar con Docker Compose

```bash
docker-compose up --build
```

### 4. Ejecutar migraciones

```bash
docker-compose exec backend alembic upgrade head
```

---

## 🔑 Variables de Entorno

Ver [backend/.env.example](backend/.env.example) para la lista completa.

---

## ▶️ Ejecutar el Proyecto

```bash
# Desarrollo local
docker-compose up

# Solo backend
cd backend && uvicorn app.main:app --reload --port 8000

# Solo frontend
cd frontend && npm run dev
```

- **Backend API:** http://localhost:8000
- **Swagger Docs:** http://localhost:8000/docs
- **Frontend:** http://localhost:5173

---

## 📁 Estructura del Proyecto

```
BOTIQ/
├── backend/          # FastAPI + Python
├── frontend/         # React + Vite
├── docker-compose.yml
└── .github/workflows # CI/CD
```

---

## 🔐 Roles y Seguridad

| Rol | Acceso |
|-----|--------|
| `employee` | Chat general, FAQ, resultado de servidores |
| `support_engineer` | + Base de conocimiento RAG |
| `admin` | + Dashboard de métricas, gestión de FAQs |

---

## 📡 API Endpoints

| Método | Ruta | Descripción | Rol |
|--------|------|-------------|-----|
| POST | `/api/v1/auth/login` | Autenticación | Público |
| POST | `/api/v1/auth/register` | Registro | Público |
| POST | `/api/v1/chat/message` | Enviar mensaje | Todos |
| GET | `/api/v1/dashboard/metrics` | Métricas generales | Admin |
| GET | `/api/v1/servers/status` | Estado de servidores | Ing. Soporte+ |
| POST | `/api/v1/support/query` | Consulta RAG | Ing. Soporte+ |

---

## 🚢 Despliegue

Ver [docs/deployment.md](docs/deployment.md) para instrucciones completas de despliegue en producción.

---

## 📖 Referencias

- [SWEBOK v4](https://www.computer.org/education/bodies-of-knowledge/software-engineering)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Google Drive API](https://developers.google.com/drive)
