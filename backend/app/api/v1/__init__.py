from fastapi import APIRouter

from app.api.v1.routes import admin, auth, chat, chat_smart, dashboard, employees, feedback, incidents, servers, servers_kb, support, widget

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
router.include_router(widget.router, prefix="/widget", tags=["Widget embebible"])
router.include_router(chat.router, prefix="/chat", tags=["Chat"])
router.include_router(chat_smart.router, prefix="/chat", tags=["Chat / Seguimiento Aranda"])
router.include_router(employees.router, prefix="/employees", tags=["Empleados / FAQs"])
router.include_router(support.router, prefix="/support", tags=["Soporte RAG"])
router.include_router(servers.router, prefix="/servers", tags=["Servidores"])
router.include_router(servers_kb.router, prefix="/servers-kb", tags=["Base de conocimiento — Servidores"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
router.include_router(admin.router, prefix="/admin", tags=["Administración"])
router.include_router(feedback.router, prefix="/chat", tags=["Feedback"])
router.include_router(incidents.router, prefix="/admin", tags=["Incidentes / Gobierno de IA"])
router.include_router(incidents.router, prefix="/dashboard", tags=["Incidentes / Gobierno de IA"], include_in_schema=False)
