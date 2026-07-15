from fastapi import APIRouter

from app.api.v1.routes import admin, auth, chat, dashboard, employees, feedback, incidents, servers, support

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
router.include_router(chat.router, prefix="/chat", tags=["Chat"])
router.include_router(employees.router, prefix="/employees", tags=["Empleados / FAQs"])
router.include_router(support.router, prefix="/support", tags=["Soporte RAG"])
router.include_router(servers.router, prefix="/servers", tags=["Servidores"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
router.include_router(admin.router, prefix="/admin", tags=["Administración"])

# ─────────────────────────────────────────────────────────────────────────────
# feedback.py define 3 endpoints que en realidad pertenecen a dos áreas
# distintas (ver docstring del archivo):
#   POST /chat/message/{id}/feedback         -> ya lo llama el frontend (useChat.js)
#   POST /chat/session/{id}/satisfaction     -> ya lo llama el frontend (useChat.js)
#   GET  /feedback/summary                   -> pensado para /dashboard/feedback/summary,
#                                                pero el frontend aún no lo consume.
# Se monta bajo /chat porque son los dos endpoints que YA están en uso; el
# summary queda disponible en /chat/feedback/summary (protegido con require_admin)
# hasta que se decida separar el router en dos archivos.
router.include_router(feedback.router, prefix="/chat", tags=["Feedback"])

# incidents.py mezcla intencionalmente /admin/* y /dashboard/incident-alerts/count
# (ver su propio docstring). Ningún endpoint de este router está en uso todavía
# desde el frontend, así que no hay riesgo de romper nada al montarlo dos veces:
# una vez para que /admin/* funcione como está documentado, y otra para que
# /dashboard/incident-alerts/count exista para el badge del navbar. Las rutas
# "de más" que aparecen duplicadas bajo el otro prefijo quedan protegidas por
# el mismo require_admin/get_current_user que ya tienen internamente.
router.include_router(incidents.router, prefix="/admin", tags=["Incidentes / Gobierno de IA"])
router.include_router(incidents.router, prefix="/dashboard", tags=["Incidentes / Gobierno de IA"], include_in_schema=False)