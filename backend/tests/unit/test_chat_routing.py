"""Tests de enrutamiento de módulos del chat."""
import pytest
from app.models.conversation import ModuleType
from app.core.roles import UserRole
from app.api.v1.routes.chat import _determine_module


def test_employee_siempre_va_a_employee():
    assert _determine_module("servidor caído", UserRole.EMPLOYEE) == ModuleType.EMPLOYEE
    assert _determine_module("error en Word", UserRole.EMPLOYEE) == ModuleType.EMPLOYEE


def test_soporte_con_keywords_servidor():
    assert _determine_module("¿el servidor está caído?", UserRole.SUPPORT_ENGINEER) == ModuleType.SERVER_VALIDATION
    assert _determine_module("problema de memoria en server", UserRole.SUPPORT_ENGINEER) == ModuleType.SERVER_VALIDATION


def test_soporte_sin_keywords_va_a_rag():
    assert _determine_module("¿cómo configuro el firewall?", UserRole.SUPPORT_ENGINEER) == ModuleType.SUPPORT_RAG
    assert _determine_module("necesito ayuda con LDAP", UserRole.SUPPORT_ENGINEER) == ModuleType.SUPPORT_RAG


def test_chunk_text():
    from app.modules.support_rag.service import SupportRAGService
    s = SupportRAGService()
    texto = " ".join([f"p{i}" for i in range(1200)])
    chunks = s._chunk_text(texto, 500)
    assert len(chunks) == 3
    assert len(chunks[0].split()) == 500


def test_chunk_text_vacio():
    from app.modules.support_rag.service import SupportRAGService
    assert SupportRAGService()._chunk_text("") == []
