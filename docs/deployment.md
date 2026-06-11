# 🚀 BOTIQ — Guía Completa: De Cero a Funcional con Docker

---

## REQUISITOS PREVIOS

Antes de empezar, instala en tu máquina:

| Herramienta | Versión mínima | Descarga |
|-------------|----------------|----------|
| Git | 2.x | https://git-scm.com |
| Docker Desktop | 4.x | https://www.docker.com/products/docker-desktop |
| Cuenta Google Cloud | — | https://console.cloud.google.com |

---

## PASO 1 — Subir el proyecto a GitHub

```bash
# Entra a la carpeta del proyecto
cd BOTIQ

# Inicializar git
git init
git add .
git commit -m "feat: BOTIQ v1.0.0 — initial structure"

# Crear rama develop
git branch develop

# Conectar con GitHub (repositorio ya creado como privado)
git remote add origin https://github.com/cortinezo98/BOTIQ.git
git push -u origin main
git push origin develop
```

---

## PASO 2 — Configurar Google Cloud

### 2.1 Crear el proyecto

```bash
# Instalar Google Cloud CLI: https://cloud.google.com/sdk/docs/install

gcloud auth login
gcloud projects create botiq-corporativo --name="BOTIQ Chatbot"
gcloud config set project botiq-corporativo
```

### 2.2 Habilitar las APIs necesarias

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  vision.googleapis.com \
  documentai.googleapis.com \
  storage.googleapis.com \
  drive.googleapis.com
```

### 2.3 Crear Service Account y descargar clave

```bash
# Crear Service Account
gcloud iam service-accounts create botiq-backend \
  --display-name="BOTIQ Backend"

# Variables
PROJECT=botiq-corporativo
SA=botiq-backend@botiq-corporativo.iam.gserviceaccount.com

# Asignar roles
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$SA" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$SA" --role="roles/cloudvision.user"
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$SA" --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$SA" --role="roles/documentai.apiUser"

# Descargar clave JSON
gcloud iam service-accounts keys create backend/credentials/service-account.json \
  --iam-account=$SA

echo "✅ Clave guardada en backend/credentials/service-account.json"
```

### 2.4 Crear bucket de Cloud Storage (para imágenes)

```bash
gcloud storage buckets create gs://botiq-images-bucket \
  --location=us-central1 \
  --uniform-bucket-level-access
```

### 2.5 Configurar Google Drive

1. Ve a **Google Drive** → Crear carpeta: `BOTIQ - Base de Conocimiento`
2. Clic derecho → **Compartir** → agregar el email del Service Account:
   `botiq-backend@botiq-corporativo.iam.gserviceaccount.com` → Rol: **Lector**
3. Copia el **ID de la carpeta** desde la URL:
   `https://drive.google.com/drive/folders/`**`ESTE_ES_EL_ID`**
4. Pega ese ID en `GDRIVE_FOLDER_ID` en el `.env`

---

## PASO 3 — Configurar las Variables de Entorno

```bash
# Copia el archivo de ejemplo
cp backend/.env.example backend/.env
```

Edita `backend/.env` y completa estos valores obligatorios:

```env
# ── Seguridad (OBLIGATORIO) ────────────────────────────────────
# Genera una clave segura ejecutando:
# python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=pega_aqui_la_clave_generada

# ── Google Cloud (OBLIGATORIO para IA) ────────────────────────
GCP_PROJECT_ID=botiq-corporativo
GCP_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/service-account.json

# ── Google Drive (OBLIGATORIO para RAG) ───────────────────────
GDRIVE_FOLDER_ID=el_id_de_tu_carpeta_en_drive

# ── API Servidores (opcional, usa datos demo si está vacío) ───
SERVER_DASHBOARD_API_URL=https://tu-api-de-servidores.com
SERVER_DASHBOARD_API_KEY=tu-api-key

# ── Estos valores ya están configurados para Docker ───────────
DATABASE_URL=postgresql://botiq_user:botiq_pass@db:5432/botiq_db
CHROMA_HOST=chromadb
CHROMA_PORT=8000
```

---

## PASO 4 — Levantar con Docker

```bash
# Construir y levantar todos los servicios
docker-compose up --build
```

Esto inicia:
- **db** → PostgreSQL en puerto 5432
- **chromadb** → Base vectorial para RAG en puerto 8001
- **backend** → FastAPI en puerto 8000
- **frontend** → React en puerto 5173

Espera a ver este mensaje en los logs:
```
botiq_backend  | ✅ BOTIQ v1.0.0 iniciado
botiq_backend  | INFO:     Application startup complete.
```

---

## PASO 5 — Ejecutar Migraciones (Primera vez)

Abre **otra terminal** y ejecuta:

```bash
docker-compose run --rm migrate
```

Deberías ver:
```
INFO  [alembic.runtime.migration] Running upgrade -> xxxx, initial migration
```

---

## PASO 6 — Crear Usuarios Iniciales

```bash
# Crear usuario ADMIN
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@tuempresa.com",
    "full_name": "Administrador",
    "password": "Admin123!",
    "role": "admin"
  }'

# Crear usuario Ingeniero de Soporte
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "soporte@tuempresa.com",
    "full_name": "Ing. Soporte",
    "password": "Soporte123!",
    "role": "support_engineer"
  }'

# Crear usuario Empleado
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "empleado@tuempresa.com",
    "full_name": "Empleado Test",
    "password": "Empleado123!",
    "role": "employee"
  }'
```

---

## PASO 7 — Verificar que todo funciona

```bash
# Backend health check
curl http://localhost:8000/health
# Respuesta esperada: {"status":"healthy"}

# Ver documentación Swagger
# Abrir en el navegador: http://localhost:8000/docs

# Frontend
# Abrir en el navegador: http://localhost:5173
```

---

## PASO 8 — Cargar la Base de Conocimiento RAG

1. Sube documentos `.txt`, `.pdf`, o Google Docs a la carpeta de Drive configurada
2. Haz login en http://localhost:5173 con el usuario `support_engineer`
3. Sincroniza el RAG:

```bash
# Obtener token del ingeniero de soporte
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -F "username=soporte@tuempresa.com" \
  -F "password=Soporte123!" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Sincronizar base de conocimiento
curl -X POST http://localhost:8000/api/v1/support/sync-knowledge-base \
  -H "Authorization: Bearer $TOKEN"
# Respuesta: {"message":"Sincronización iniciada en background"}

# Verificar estado del RAG
curl http://localhost:8000/api/v1/support/knowledge-base/status \
  -H "Authorization: Bearer $TOKEN"
# Respuesta: {"status":"active","total_chunks":N}
```

---

## PASO 9 — Cargar FAQs para Empleados

```bash
# Obtener token admin
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -F "username=admin@tuempresa.com" \
  -F "password=Admin123!" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Crear FAQ de ejemplo
curl -X POST "http://localhost:8000/api/v1/employees/faqs?question=No+puedo+ingresar+al+portal&answer=Intenta+limpiar+el+cache+del+navegador+y+verificar+tus+credenciales.+Si+el+problema+persiste+contac&category=Acceso" \
  -H "Authorization: Bearer $TOKEN"
```

---

## PASO 10 — Embeber el widget en otra página

Compila el widget:

```bash
docker-compose exec frontend npm run build:widget
# El archivo queda en: frontend/dist-widget/botiq-widget.iife.js
```

Pega este código en cualquier página HTML corporativa:

```html
<!-- Antes del </body> -->
<div id="botiq-root"></div>
<script src="/ruta/a/botiq-widget.iife.js"></script>
<script>
  BotiqWidget.init({
    apiUrl: 'http://localhost:8000',   // cambiar por URL de producción
    primaryColor: '#1E3A5F',
    position: 'bottom-right',
  });
</script>
```

---

## COMANDOS DOCKER DE USO DIARIO

```bash
# Iniciar todos los servicios
docker-compose up -d

# Ver logs en tiempo real
docker-compose logs -f

# Ver logs de un servicio específico
docker-compose logs -f backend

# Reiniciar un servicio (ej. después de cambiar código)
docker-compose restart backend

# Ejecutar tests del backend
docker-compose exec backend pytest tests/ -v

# Abrir shell en el backend
docker-compose exec backend bash

# Detener sin borrar datos
docker-compose stop

# Detener Y borrar todos los volúmenes (⚠️ borra la BD)
docker-compose down -v
```

---

## SOLUCIÓN DE PROBLEMAS COMUNES

| Problema | Solución |
|----------|----------|
| `Connection refused port 5432` | Ejecutar `docker-compose up -d db` y esperar el healthcheck |
| `Vertex AI not initialized` | Verificar que `backend/credentials/service-account.json` existe y que `GCP_PROJECT_ID` está en `.env` |
| `CORS error en el navegador` | Agregar tu URL al campo `ALLOWED_ORIGINS` en `.env` |
| `alembic: can't connect to DB` | Ejecutar `docker-compose up -d db` primero, esperar 10s, luego migrar |
| `ChromaDB connection error` | Ejecutar `docker-compose up -d chromadb` |
| Puerto 5173 en uso | Cambiar `"5173:5173"` a `"3001:5173"` en `docker-compose.yml` |
| `401 en todos los endpoints` | El `SECRET_KEY` en `.env` está vacío, generar con `secrets.token_hex(32)` |
| Widget no aparece en otra página | Verificar que `ALLOWED_ORIGINS` incluye el dominio de la página |

---

## FLUJO DE MIGRACIONES (al cambiar modelos)

```bash
# Generar nueva migración automáticamente
docker-compose exec backend alembic revision --autogenerate -m "descripcion_del_cambio"

# Aplicar la migración
docker-compose exec backend alembic upgrade head

# Ver historial de migraciones
docker-compose exec backend alembic history

# Revertir última migración
docker-compose exec backend alembic downgrade -1
```

---

## CHECKLIST FINAL ✅

- [ ] `service-account.json` en `backend/credentials/`
- [ ] `backend/.env` con `SECRET_KEY`, `GCP_PROJECT_ID`, `GDRIVE_FOLDER_ID`
- [ ] `docker-compose up --build` sin errores
- [ ] `docker-compose run --rm migrate` ejecutado
- [ ] Usuario admin, soporte y empleado creados
- [ ] http://localhost:8000/health responde `{"status":"healthy"}`
- [ ] http://localhost:5173 muestra la pantalla de login
- [ ] Login funciona con usuario admin
- [ ] Chat responde (modo demo sin credenciales GCP, o con IA real con credenciales)
- [ ] Dashboard visible con usuario admin
- [ ] RAG sincronizado (con archivos en Google Drive)
