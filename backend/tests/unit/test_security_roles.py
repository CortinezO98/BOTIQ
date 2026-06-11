import pytest
from app.core.security import hash_password, verify_password, create_access_token, decode_token
from app.core.roles import UserRole, has_minimum_role, can_access_module

def test_password(): p="Abc123456"; h=hash_password(p); assert verify_password(p,h) and not verify_password("wrong",h)
def test_jwt():
    t=create_access_token({"sub":"u1","role":"employee"}); d=decode_token(t)
    assert d["user_id"]=="u1" and d["role"]=="employee"
def test_invalid_jwt():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e: decode_token("bad.token")
    assert e.value.status_code==401
def test_roles():
    assert has_minimum_role(UserRole.ADMIN,UserRole.EMPLOYEE)
    assert not has_minimum_role(UserRole.EMPLOYEE,UserRole.ADMIN)
def test_permissions():
    assert can_access_module(UserRole.EMPLOYEE,"employee_chat")
    assert not can_access_module(UserRole.EMPLOYEE,"support_rag")
    assert can_access_module(UserRole.ADMIN,"dashboard")
