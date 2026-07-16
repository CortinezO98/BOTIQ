"""
Prueba segura de conectividad BOTIQ -> Aranda.

No crea tickets. Ejecuta únicamente:
1. Login
2. Renovación de sesión
3. Logout

Uso desde la raíz del proyecto:
    docker compose exec backend python test_aranda_connection.py
"""
import asyncio
import json

from app.services.aranda_service import aranda_service


async def main() -> None:
    report = aranda_service.configuration_report()
    safe_report = {
        "enabled": report["enabled"],
        "valid": report["valid"],
        "missing_or_invalid": report["missing_or_invalid"],
        "api_base": report["api_base"],
        "verify_tls": report["verify_tls"],
        "close_session_after_request": report["close_session_after_request"],
    }
    print("Configuración Aranda (sin secretos):")
    print(json.dumps(safe_report, ensure_ascii=False, indent=2))

    if not report["valid"]:
        raise SystemExit(1)

    result = await aranda_service.test_connection()
    print("\nResultado:")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    raise SystemExit(0 if result.get("ok") else 2)


if __name__ == "__main__":
    asyncio.run(main())
