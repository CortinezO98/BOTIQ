#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# BOTIQ — Script de inicialización del repositorio GitHub
# Ejecutar UNA SOLA VEZ después de clonar o crear el proyecto
# ═══════════════════════════════════════════════════════════════════

set -e  # Salir si algún comando falla

echo ""
echo "🤖 ═══════════════════════════════════════════"
echo "   BOTIQ — Inicialización del Proyecto"
echo "═══════════════════════════════════════════════"
echo ""

# ─── 1. Verificar prerrequisitos ──────────────────────────────────
echo "📋 Verificando prerrequisitos..."

command -v git >/dev/null 2>&1 || { echo "❌ Git no está instalado."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 no está instalado."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js no está instalado."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ Docker no está instalado."; exit 1; }

echo "✅ Prerrequisitos OK"
echo ""

# ─── 2. Configurar entorno del backend ───────────────────────────
echo "🐍 Configurando backend Python..."

cd backend

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Backend configurado"
echo ""

# ─── 3. Copiar variables de entorno ──────────────────────────────
if [ ! -f .env ]; then
    cp .env.example .env
    echo "📄 Archivo .env creado desde .env.example"
    echo "⚠️  IMPORTANTE: Edita backend/.env con tus credenciales reales"
else
    echo "📄 .env ya existe, no se sobreescribe"
fi

cd ..

# ─── 4. Configurar frontend ───────────────────────────────────────
echo "⚛️  Configurando frontend React..."

cd frontend
npm install
echo "✅ Frontend configurado"
cd ..
echo ""

# ─── 5. Crear carpeta de credenciales ────────────────────────────
mkdir -p backend/credentials
echo "📁 Carpeta backend/credentials/ creada"
echo "⚠️  Coloca tu service-account.json de Google Cloud aquí"
echo ""

# ─── 6. Levantar servicios con Docker ────────────────────────────
echo "🐳 ¿Deseas levantar los servicios con Docker ahora? (y/n)"
read -r answer
if [ "$answer" = "y" ]; then
    docker-compose up -d db chromadb
    echo "✅ PostgreSQL y ChromaDB iniciados"
    echo ""

    # Esperar a que PostgreSQL esté listo
    echo "⏳ Esperando a que PostgreSQL esté listo..."
    sleep 5

    # Ejecutar migraciones
    cd backend
    source venv/bin/activate
    alembic upgrade head
    cd ..
    echo "✅ Migraciones ejecutadas"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "✅ BOTIQ inicializado correctamente"
echo ""
echo "Próximos pasos:"
echo "  1. Edita backend/.env con tus credenciales de Google Cloud"
echo "  2. Coloca tu service-account.json en backend/credentials/"
echo "  3. Ejecuta: docker-compose up --build"
echo "  4. Backend disponible en: http://localhost:8000"
echo "  5. Frontend disponible en: http://localhost:5173"
echo "  6. Swagger docs en: http://localhost:8000/docs"
echo "═══════════════════════════════════════════════"
