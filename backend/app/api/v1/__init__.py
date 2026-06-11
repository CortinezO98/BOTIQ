"""Router principal API v1 — BOTIQ."""
from fastapi import APIRouter
from app.api.v1.routes import auth, chat, employees, support, servers, dashboard, admin

router = APIRouter()
router.include_router(auth.router,       prefix="/auth",      tags=["Autenticación"])
router.include_router(chat.router,       prefix="/chat",      tags=["Chat"])
router.include_router(employees.router,  prefix="/employees", tags=["Empleados / FAQs"])
router.include_router(support.router,    prefix="/support",   tags=["Soporte RAG"])
router.include_router(servers.router,    prefix="/servers",   tags=["Servidores"])
router.include_router(dashboard.router,  prefix="/dashboard", tags=["Dashboard"])
router.include_router(admin.router,      prefix="/admin",     tags=["Administración de Usuarios"])
