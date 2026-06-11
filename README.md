# 🤖 BOTIQ — Corporate Intelligent Chatbot

> Chatbot corporativo con Vertex AI (Google Cloud), RAG sobre Google Drive,
> validación de servidores y dashboard de métricas.
> **Stack:** FastAPI · React · PostgreSQL · ChromaDB · Docker

---

## ⚡ Inicio Rápido (Docker)

```bash
# 1. Clonar el repositorio
git clone https://github.com/cortinezo98/BOTIQ.git
cd BOTIQ

# 2. Configurar variables de entorno
cp backend/.env.example backend/.env
# Editar backend/.env con tus credenciales

# 3. Colocar el service account de Google Cloud
# Copiar service-account.json a: backend/credentials/service-account.json

# 4. Levantar todo con Docker
docker-compose up --build

# 5. (Primera vez) Ejecutar migraciones
docker-compose run --rm migrate

# 6. Crear usuario administrador
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@empresa.com","full_name":"Admin","password":"Admin123!","role":"admin"}'
```

**URLs:**
| Servicio | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |

---

## 🧩 Módulos

| Módulo | Descripción | Rol requerido |
|--------|-------------|---------------|
| **Empleados** | FAQ + Gemini Pro para consultas generales | Todos |
| **Soporte RAG** | Base de conocimiento desde Google Drive | Ingeniero de Soporte |
| **Servidores** | Validación API del tablero + Gemini | Ingeniero de Soporte |
| **Dashboard** | Métricas, tokens, brechas de conocimiento | Admin |

---

## 🔐 Roles

| Rol | Descripción |
|-----|-------------|
| `employee` | Chat general + FAQ |
| `support_engineer` | + RAG + Servidores |
| `admin` | + Dashboard + Gestión FAQs |

---

## 📁 Estructura

```
BOTIQ/
├── backend/              # FastAPI + Python 3.11
│   ├── app/
│   │   ├── api/v1/       # Endpoints REST
│   │   ├── core/         # Config, roles, seguridad
│   │   ├── modules/      # employee_bot, support_rag, server_monitor
│   │   ├── services/     # vertex/, gdrive, gcs, metrics
│   │   └── models/       # SQLAlchemy ORM
│   ├── credentials/      # service-account.json (NO en git)
│   └── tests/
├── frontend/             # React + Vite
│   └── src/
│       ├── components/   # ChatWidget, Dashboard
│       ├── pages/        # Login, Chat, Dashboard
│       └── embed/        # Widget embebible
├── docker-compose.yml
└── docs/
```

---

## 🔧 Comandos útiles Docker

```bash
# Ver logs en tiempo real
docker-compose logs -f backend
docker-compose logs -f frontend

# Ejecutar migraciones manualmente
docker-compose run --rm migrate

# Abrir shell en el backend
docker-compose exec backend bash

# Correr tests
docker-compose exec backend pytest tests/ -v

# Reiniciar solo el backend
docker-compose restart backend

# Limpiar todo (¡borra datos!)
docker-compose down -v
```

---

## 🌐 Embeber el widget en otras páginas

```html
<div id="botiq-root"></div>
<script src="https://tu-dominio.com/botiq-widget.iife.js"></script>
<script>
  BotiqWidget.init({
    apiUrl: 'https://tu-api-botiq.com',
    primaryColor: '#1E3A5F',
    position: 'bottom-right',
    authToken: 'JWT_DEL_USUARIO'  // opcional
  });
</script>
```

---

## 📖 Documentación adicional

- [Guía de despliegue completa](docs/deployment.md)
- [Arquitectura técnica](docs/architecture.md)
