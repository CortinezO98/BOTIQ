from enum import Enum


class UserRole(str, Enum):
    EMPLOYEE = "employee"
    SUPPORT_ENGINEER = "support_engineer"
    ADMIN = "admin"


ROLE_HIERARCHY = {
    UserRole.EMPLOYEE: 1,
    UserRole.SUPPORT_ENGINEER: 2,
    UserRole.ADMIN: 3,
}


def has_minimum_role(user_role: UserRole, required_role: UserRole) -> bool:
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(required_role, 0)


MODULE_PERMISSIONS = {
    "employee_chat":     [UserRole.EMPLOYEE, UserRole.SUPPORT_ENGINEER, UserRole.ADMIN],
    "support_rag":       [UserRole.SUPPORT_ENGINEER, UserRole.ADMIN],
    "server_validation": [UserRole.SUPPORT_ENGINEER, UserRole.ADMIN],
    "dashboard":         [UserRole.ADMIN],
    "faq_management":    [UserRole.ADMIN],
}


def can_access_module(user_role: UserRole, module: str) -> bool:
    return user_role in MODULE_PERMISSIONS.get(module, [])
