# 🤖 BOTIQ — Corporate Intelligent Chatbot

BOTIQ es un chatbot corporativo con FastAPI, React, PostgreSQL, ChromaDB, Vertex AI, Google Drive RAG, gestión de usuarios, FAQs y dashboard administrativo.

## Stack

- Backend: FastAPI + SQLAlchemy async + PostgreSQL + Alembic
- Frontend: React + Vite
- IA: Google Vertex AI / Gemini
- RAG: Google Drive + ChromaDB + embeddings
- Infra: Docker Compose + Nginx para producción

---

## Inicio rápido en desarrollo

```bash
git clone https://github.com/cortinezo98/BOTIQ.git
cd BOTIQ

copy backend\.env.example backend\.env
docker compose up -d --build
```

Crear tablas en desarrollo si aún no tienes migraciones aplicadas:

```bash
docker compose exec backend python init_db.py
```

Crear o actualizar usuario administrador:

```bash
docker compose exec backend python create_admin.py
```

## URLs de desarrollo

| Servicio | URL |
|---|---|
| Frontend | http://localhost:5180 |
| Backend API | http://localhost:8002 |
| Swagger Docs | http://localhost:8002/docs |
| Health | http://localhost:8002/health |
| ChromaDB | http://localhost:8003 |
| PostgreSQL | localhost:5433 |

## Login API

```bash
curl -X POST http://localhost:8002/api/v1/auth/login \
  -F "username=admin@empresa.com" \
  -F "password=Admin123!"
```

---

## Roles

| Rol | Descripción |
|---|---|
| `employee` | Chat general + FAQs |
| `support_engineer` | Chat general + RAG + Servidores |
| `admin` | Todo lo anterior + dashboard + usuarios + FAQs |

---

## Módulos

| Módulo | Descripción |
|---|---|
| Empleados | FAQ + Gemini para consultas generales |
| Soporte RAG | Respuestas desde Google Drive y ChromaDB |
| Servidores | Validación de estado de infraestructura |
| Dashboard | Métricas, brechas, tokens y FAQs |
| Administración | Gestión de usuarios y FAQs |

---

## Comandos útiles

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose restart backend
docker compose exec backend pytest tests/ -v
docker compose down
docker compose down -v
```

---

## Producción

Crear archivo real de producción:

```bash
copy backend\.env.prod.example backend\.env.prod
```

Levantar:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Estructura principal

```text
BOTIQ/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── modules/
│   │   ├── schemas/
│   │   └── services/
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/
│       ├── hooks/
│       ├── pages/
│       └── services/
├── infra/nginx/
├── docs/
└── docker-compose.yml
```
