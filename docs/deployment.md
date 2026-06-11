# 🚀 BOTIQ — Guía Completa de Despliegue

## PASO A PASO: Desde cero hasta producción

---

## PARTE 1 — Crear el Repositorio en GitHub

### 1.1 Crear el repositorio privado en GitHub

1. Ve a [github.com/new](https://github.com/new)
2. Configura:
   - **Repository name:** `BOTIQ`
   - **Visibility:** `Private` ✅
   - **NO** marques "Add a README file" (ya tenemos uno)
   - **NO** marques "Add .gitignore" (ya tenemos uno)
3. Clic en **"Create repository"**

### 1.2 Subir el código al repositorio

```bash
# En la carpeta raíz del proyecto BOTIQ/
git init
git add .
git commit -m "feat: initial project structure — BOTIQ v1.0.0"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/BOTIQ.git
git push -u origin main
```

### 1.3 Crear ramas de trabajo

```bash
# Rama de desarrollo
git checkout -b develop
git push -u origin develop

# Proteger la rama main en GitHub:
# Settings → Branches → Add rule → Branch name: main
# ✅ Require a pull request before merging
# ✅ Require status checks to pass before merging
```

---

## PARTE 2 — Configurar Google Cloud

### 2.1 Crear proyecto en Google Cloud

```bash
# Instalar Google Cloud CLI: https://cloud.google.com/sdk/docs/install

# Autenticarse
gcloud auth login

# Crear proyecto
gcloud projects create botiq-corporativo --name="BOTIQ Chatbot"

# Establecer proyecto activo
gcloud config set project botiq-corporativo
```

### 2.2 Habilitar APIs necesarias

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  vision.googleapis.com \
  documentai.googleapis.com \
  storage.googleapis.com \
  drive.googleapis.com \
  secretmanager.googleapis.com
```

### 2.3 Crear Service Account

```bash
# Crear Service Account
gcloud iam service-accounts create botiq-backend \
  --display-name="BOTIQ Backend Service Account"

# Asignar roles necesarios
SA_EMAIL="botiq-backend@botiq-corporativo.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding botiq-corporativo \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding botiq-corporativo \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/cloudvision.user"

gcloud projects add-iam-policy-binding botiq-corporativo \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/documentai.apiUser"

gcloud projects add-iam-policy-binding botiq-corporativo \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/storage.objectAdmin"

# Descargar la clave JSON
gcloud iam service-accounts keys create backend/credentials/service-account.json \
  --iam-account=$SA_EMAIL

echo "✅ Service Account creado y clave descargada en backend/credentials/"
```

### 2.4 Crear bucket en Cloud Storage

```bash
# Crear bucket para imágenes del chatbot
gcloud storage buckets create gs://botiq-images-bucket \
  --location=us-central1 \
  --uniform-bucket-level-access

# Configurar lifecycle: eliminar imágenes después de 1 día
cat > /tmp/lifecycle.json << 'EOF'
{
  "lifecycle": {
    "rule": [{
      "action": {"type": "Delete"},
      "condition": {"age": 1}
    }]
  }
}
EOF

gcloud storage buckets update gs://botiq-images-bucket \
  --lifecycle-file=/tmp/lifecycle.json

echo "✅ Bucket creado con lifecycle de 1 día"
```

### 2.5 Configurar Google Drive

```bash
# 1. Ve a Google Drive
# 2. Crea una carpeta llamada "BOTIQ - Base de Conocimiento"
# 3. Haz clic derecho → Compartir
# 4. Agrega el email del Service Account: botiq-backend@botiq-corporativo.iam.gserviceaccount.com
# 5. Permisos: Lector
# 6. Copia el ID de la carpeta desde la URL:
#    https://drive.google.com/drive/folders/ESTE_ES_EL_ID
# 7. Pega el ID en GDRIVE_FOLDER_ID del .env
echo "📁 Configura Google Drive manualmente según las instrucciones"
```

### 2.6 Configurar Document AI (opcional)

```bash
# Solo necesario si hay PDFs escaneados en la base de conocimiento

# 1. Ve a: https://console.cloud.google.com/ai/document-ai
# 2. Clic en "Create Processor"
# 3. Selecciona "Document OCR"
# 4. Región: us (recomendado)
# 5. Copia el Processor ID al .env: DOCUMENT_AI_PROCESSOR_ID
echo "📄 Configura Document AI manualmente si necesitas OCR en PDFs"
```

---

## PARTE 3 — Configurar Variables de Entorno

### 3.1 Editar backend/.env

```bash
cd backend
cp .env.example .env
nano .env  # o usa tu editor favorito
```

Valores que debes completar:

```env
GCP_PROJECT_ID=botiq-corporativo
GCP_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/service-account.json

VERTEX_GEMINI_MODEL=gemini-1.5-pro
VERTEX_EMBEDDING_MODEL=text-multilingual-embedding-002

GDRIVE_FOLDER_ID=TU_ID_DE_CARPETA_DRIVE

GCS_BUCKET_NAME=botiq-images-bucket

SERVER_DASHBOARD_API_URL=https://tu-api-de-servidores.com
SERVER_DASHBOARD_API_KEY=tu-api-key

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

### 3.2 Agregar secrets a GitHub Actions

```bash
# Ve a: GitHub repo → Settings → Secrets and variables → Actions
# Agrega estos secrets:
# - GCP_PROJECT_ID
# - SECRET_KEY
```

---

## PARTE 4 — Levantar el Proyecto

### 4.1 Primera vez (desarrollo local)

```bash
# Dar permisos al script de inicialización
chmod +x scripts/init.sh
./scripts/init.sh

# O manualmente:
docker-compose up --build
```

### 4.2 Verificar que todo funciona

```bash
# Backend health check
curl http://localhost:8000/health
# Esperado: {"status": "healthy"}

# Ver documentación interactiva
open http://localhost:8000/docs

# Frontend
open http://localhost:5173
```

### 4.3 Ejecutar migraciones

```bash
docker-compose exec backend alembic upgrade head
```

### 4.4 Sincronizar base de conocimiento RAG

```bash
# 1. Haz login como ingeniero de soporte en http://localhost:5173
# 2. O via API:
curl -X POST http://localhost:8000/api/v1/support/sync-knowledge-base \
  -H "Authorization: Bearer TU_TOKEN_JWT"
```

---

## PARTE 5 — Crear usuarios iniciales

```bash
# Crear usuario admin
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@tuempresa.com",
    "full_name": "Administrador BOTIQ",
    "password": "TuPasswordSegura123",
    "role": "admin"
  }'

# Crear ingeniero de soporte
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "soporte@tuempresa.com",
    "full_name": "Ingeniero de Soporte",
    "password": "OtraPasswordSegura456",
    "role": "support_engineer"
  }'
```

---

## PARTE 6 — Embeber el widget en otras páginas

```html
<!-- Agregar al final del <body> de cualquier página corporativa -->
<div id="botiq-widget-root"></div>
<script src="https://tu-dominio.com/botiq-widget.js"></script>
<script>
  BotiqWidget.init({
    apiUrl: 'https://tu-api-botiq.com',
    primaryColor: '#1E3A5F',
    position: 'bottom-right',
    // authToken: 'JWT del usuario si ya está autenticado en tu sistema'
  });
</script>
```

```bash
# Compilar el widget embebible
cd frontend
npm run build:widget
# Resultado: frontend/dist-widget/botiq-widget.iife.js
# Sube este archivo a tu CDN o servidor estático
```

---

## PARTE 7 — Flujo de trabajo Git (SWEBOK v4)

```bash
# Para nuevas funcionalidades
git checkout develop
git checkout -b feature/nombre-de-la-feature
# ... desarrollar ...
git add .
git commit -m "feat: descripción de la feature"
git push origin feature/nombre-de-la-feature
# Crear Pull Request hacia develop en GitHub

# Para hotfixes en producción
git checkout main
git checkout -b hotfix/descripcion
# ... fix ...
git commit -m "fix: descripción del fix"
# PR hacia main Y develop
```

### Convención de commits

```
feat:     Nueva funcionalidad
fix:      Corrección de bug
docs:     Cambios en documentación
test:     Agregar o modificar tests
refactor: Refactorización sin cambios de comportamiento
chore:    Tareas de mantenimiento
```

---

## ✅ Checklist de Verificación Final

- [ ] Repositorio privado creado en GitHub
- [ ] Código subido a rama `main`
- [ ] Rama `develop` creada
- [ ] Proyecto Google Cloud creado
- [ ] APIs de Vertex AI habilitadas
- [ ] Service Account creado con roles correctos
- [ ] `service-account.json` en `backend/credentials/` (NO en git)
- [ ] Bucket GCS creado con lifecycle de 1 día
- [ ] Carpeta de Google Drive compartida con Service Account
- [ ] `backend/.env` configurado con todas las variables
- [ ] `docker-compose up --build` ejecutado sin errores
- [ ] Migraciones de BD ejecutadas (`alembic upgrade head`)
- [ ] Usuario admin creado
- [ ] Base de conocimiento RAG sincronizada
- [ ] Tests pasando (`pytest tests/`)
- [ ] Widget embebible compilado

---

## 🆘 Solución de Problemas Comunes

| Problema | Solución |
|----------|----------|
| `Error: Vertex AI not initialized` | Verifica que `GOOGLE_APPLICATION_CREDENTIALS` apunta al JSON correcto |
| `Connection refused: 5432` | Ejecuta `docker-compose up -d db` primero |
| `ChromaDB connection error` | Ejecuta `docker-compose up -d chromadb` |
| `401 Unauthorized en todos los endpoints` | Verifica que `SECRET_KEY` en `.env` no esté vacío |
| `Google Drive: 403 Forbidden` | El Service Account no tiene permisos en la carpeta de Drive |
| `Vertex AI: quota exceeded` | Revisa los límites en Google Cloud Console → APIs → Vertex AI |
