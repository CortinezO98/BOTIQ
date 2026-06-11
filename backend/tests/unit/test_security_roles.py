"""
Tests unitarios para seguridad y roles.
SWEBOK v4: Verificación y validación — los tests son parte del producto, no un extra.
"""

import pytest
from app.core.security import hash_password, verify_password, create_access_token, decode_token
from app.core.roles import UserRole, has_minimum_role, can_access_module


# ─── Tests de contraseñas ─────────────────────────────────────────────────────

def test_hash_password_returns_different_from_plain():
    plain = "MiContraseña123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert len(hashed) > 20


def test_verify_password_correct():
    plain = "MiContraseña123"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("correcta")
    assert verify_password("incorrecta", hashed) is False


# ─── Tests de JWT ─────────────────────────────────────────────────────────────

def test_create_and_decode_token():
    data = {"sub": "user-123", "role": "employee"}
    token = create_access_token(data)
    decoded = decode_token(token)
    assert decoded["user_id"] == "user-123"
    assert decoded["role"] == "employee"


def test_decode_invalid_token_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        decode_token("token.invalido.completamente")
    assert exc_info.value.status_code == 401


# ─── Tests de roles ───────────────────────────────────────────────────────────

def test_role_hierarchy_employee_below_support():
    assert has_minimum_role(UserRole.EMPLOYEE, UserRole.EMPLOYEE) is True
    assert has_minimum_role(UserRole.EMPLOYEE, UserRole.SUPPORT_ENGINEER) is False
    assert has_minimum_role(UserRole.EMPLOYEE, UserRole.ADMIN) is False


def test_role_hierarchy_support_above_employee():
    assert has_minimum_role(UserRole.SUPPORT_ENGINEER, UserRole.EMPLOYEE) is True
    assert has_minimum_role(UserRole.SUPPORT_ENGINEER, UserRole.SUPPORT_ENGINEER) is True
    assert has_minimum_role(UserRole.SUPPORT_ENGINEER, UserRole.ADMIN) is False


def test_role_hierarchy_admin_above_all():
    assert has_minimum_role(UserRole.ADMIN, UserRole.EMPLOYEE) is True
    assert has_minimum_role(UserRole.ADMIN, UserRole.SUPPORT_ENGINEER) is True
    assert has_minimum_role(UserRole.ADMIN, UserRole.ADMIN) is True


def test_module_permissions_employee_chat():
    assert can_access_module(UserRole.EMPLOYEE, "employee_chat") is True
    assert can_access_module(UserRole.SUPPORT_ENGINEER, "employee_chat") is True
    assert can_access_module(UserRole.ADMIN, "employee_chat") is True


def test_module_permissions_support_rag_restricted():
    assert can_access_module(UserRole.EMPLOYEE, "support_rag") is False
    assert can_access_module(UserRole.SUPPORT_ENGINEER, "support_rag") is True
    assert can_access_module(UserRole.ADMIN, "support_rag") is True


def test_module_permissions_dashboard_admin_only():
    assert can_access_module(UserRole.EMPLOYEE, "dashboard") is False
    assert can_access_module(UserRole.SUPPORT_ENGINEER, "dashboard") is False
    assert can_access_module(UserRole.ADMIN, "dashboard") is True
