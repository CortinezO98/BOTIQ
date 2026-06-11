"""Tests unitarios de seguridad y roles."""
import pytest
from app.core.security import hash_password, verify_password, create_access_token, decode_token
from app.core.roles import UserRole, has_minimum_role, can_access_module


def test_hash_verify_password():
    p = "MiPassword123"
    h = hash_password(p)
    assert h != p
    assert verify_password(p, h) is True
    assert verify_password("incorrecta", h) is False


def test_jwt_create_decode():
    token = create_access_token({"sub": "user-123", "role": "employee"})
    data = decode_token(token)
    assert data["user_id"] == "user-123"
    assert data["role"] == "employee"


def test_jwt_invalid_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        decode_token("invalid.token.here")
    assert exc.value.status_code == 401


def test_role_hierarchy():
    assert has_minimum_role(UserRole.EMPLOYEE, UserRole.EMPLOYEE) is True
    assert has_minimum_role(UserRole.EMPLOYEE, UserRole.SUPPORT_ENGINEER) is False
    assert has_minimum_role(UserRole.ADMIN, UserRole.EMPLOYEE) is True
    assert has_minimum_role(UserRole.ADMIN, UserRole.ADMIN) is True


def test_module_permissions():
    assert can_access_module(UserRole.EMPLOYEE, "employee_chat") is True
    assert can_access_module(UserRole.EMPLOYEE, "support_rag") is False
    assert can_access_module(UserRole.EMPLOYEE, "dashboard") is False
    assert can_access_module(UserRole.SUPPORT_ENGINEER, "support_rag") is True
    assert can_access_module(UserRole.ADMIN, "dashboard") is True
