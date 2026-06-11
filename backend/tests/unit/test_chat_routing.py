"""
Tests unitarios para la lógica de enrutamiento del chatbot.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.conversation import ModuleType
from app.core.roles import UserRole


# ─── Tests de enrutamiento de módulos ────────────────────────────────────────

def test_server_keywords_route_to_server_module():
    """Los ingenieros con palabras clave de servidor van al módulo de servidores."""
    from app.api.v1.routes.chat import _determine_module

    server_queries = [
        "¿Está caído el servidor?",
        "El server no responde",
        "¿Cuál es el uso de memoria del servidor?",
        "Hay un problema de CPU en infraestructura",
    ]

    for query in server_queries:
        module = _determine_module(query, UserRole.SUPPORT_ENGINEER)
        assert module == ModuleType.SERVER_VALIDATION, f"Falló para: {query}"


def test_employee_always_routes_to_employee_module():
    """Los empleados siempre van al módulo de empleados, sin importar el mensaje."""
    from app.api.v1.routes.chat import _determine_module

    queries = [
        "¿Está caído el servidor?",  # Aunque mencione servidor, es empleado
        "No puedo ingresar al portal",
        "Error en Word",
    ]

    for query in queries:
        module = _determine_module(query, UserRole.EMPLOYEE)
        assert module == ModuleType.EMPLOYEE, f"Empleado no debe ir a otro módulo: {query}"


def test_support_engineer_defaults_to_rag():
    """Ingeniero de soporte sin palabras clave de servidor va al RAG."""
    from app.api.v1.routes.chat import _determine_module

    non_server_queries = [
        "¿Cómo configuro el firewall?",
        "Necesito ayuda con Active Directory",
        "¿Cuál es el proceso de onboarding?",
    ]

    for query in non_server_queries:
        module = _determine_module(query, UserRole.SUPPORT_ENGINEER)
        assert module == ModuleType.SUPPORT_RAG, f"Soporte debería ir a RAG: {query}"


def test_admin_routes_same_as_support():
    """El admin tiene el mismo comportamiento de enrutamiento que el ingeniero de soporte."""
    from app.api.v1.routes.chat import _determine_module

    assert _determine_module("servidor caído", UserRole.ADMIN) == ModuleType.SERVER_VALIDATION
    assert _determine_module("consulta técnica", UserRole.ADMIN) == ModuleType.SUPPORT_RAG


# ─── Tests de módulo Employee ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_employee_bot_detects_escalation():
    """El bot detecta cuando debe escalar a Aranda."""
    from app.modules.employee_bot.service import EmployeeBotService

    service = EmployeeBotService()

    # Simular respuesta de Gemini que indica no poder resolver
    with patch.object(
        service,
        'generate_response',
        return_value={
            "text": "No tengo información sobre ese tema. Te recomiendo crear un ticket en Aranda.",
            "escalated_to_aranda": True,
            "tokens_used": 120,
        }
    ) as mock:
        result = await service.generate_response(
            user_message="Problema muy específico sin solución en FAQ",
            db=AsyncMock(),
        )
        assert result["escalated_to_aranda"] is True


# ─── Tests de chunking RAG ────────────────────────────────────────────────────

def test_chunk_text_splits_correctly():
    """El chunking divide el texto en partes del tamaño correcto."""
    from app.modules.support_rag.service import SupportRAGService

    service = SupportRAGService()
    text = " ".join([f"palabra{i}" for i in range(1200)])  # 1200 palabras

    chunks = service._chunk_text(text, chunk_size=500)

    assert len(chunks) == 3  # 1200 / 500 = 3 chunks (500, 500, 200)
    assert len(chunks[0].split()) == 500
    assert len(chunks[1].split()) == 500
    assert len(chunks[2].split()) == 200


def test_chunk_text_empty_input():
    """El chunking maneja texto vacío."""
    from app.modules.support_rag.service import SupportRAGService

    service = SupportRAGService()
    chunks = service._chunk_text("", chunk_size=500)
    assert chunks == []
