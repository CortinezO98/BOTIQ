"""
Consulta categorías y servicios configurados en Aranda sin crear tickets.

Uso:
    docker compose exec backend python inspect_aranda_catalogs.py

Requiere ARANDA_ENABLED=true y ARANDA_PROJECT_ID configurado.
"""
import asyncio
import json

from app.core.config import settings
from app.services.aranda_service import ArandaIntegrationError, aranda_service


async def main() -> None:
    try:
        categories = await aranda_service.list_categories(
            project_id=settings.ARANDA_PROJECT_ID,
            item_type=settings.ARANDA_DEFAULT_ITEM_TYPE,
        )
        services = await aranda_service.list_services(project_id=settings.ARANDA_PROJECT_ID)
    except ArandaIntegrationError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": exc.code,
                    "http_status": exc.http_status,
                    "message": "No fue posible consultar los catálogos de Aranda.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(2)

    print(
        json.dumps(
            {
                "ok": True,
                "project_id": settings.ARANDA_PROJECT_ID,
                "item_type": settings.ARANDA_DEFAULT_ITEM_TYPE,
                "categories": categories,
                "services": services,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
