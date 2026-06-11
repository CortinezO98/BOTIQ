from fastapi import APIRouter, Depends, BackgroundTasks
from app.api.deps import require_support
from app.models.user import User
from app.modules.support_rag.service import support_rag_service
from app.services.gdrive_service import gdrive_service

router = APIRouter()


@router.post("/sync-knowledge-base")
async def sync_kb(bg: BackgroundTasks, _: User = Depends(require_support)):
    """Sincroniza la base de conocimiento desde Google Drive. Ejecuta en background."""
    if not gdrive_service.is_configured():
        return {
            "message": "Google Drive no configurado",
            "instructions": [
                "1. Crea carpeta en Google Drive",
                "2. Comparte con el Service Account",
                "3. Agrega GDRIVE_FOLDER_ID en backend/.env",
                "4. Reinicia el backend"
            ]
        }
    bg.add_task(support_rag_service.sync_knowledge_base)
    return {"message": "Sincronización iniciada en background", "drive_configured": True}


@router.get("/knowledge-base/status")
async def kb_status(_: User = Depends(require_support)):
    try:
        col = support_rag_service._get_collection()
        return {
            "status": "active",
            "total_chunks": col.count(),
            "drive_configured": gdrive_service.is_configured(),
            "drive_folder_id": __import__('app.core.config', fromlist=['settings']).settings.GDRIVE_FOLDER_ID or "No configurado",
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
