"""
Definición de roles y permisos del sistema BOTIQ.
SWEBOK v4: Seguridad por diseño — roles definidos como constantes tipadas.
"""

from enum import Enum


class UserRole(str, Enum):
    EMPLOYEE = "employee"              # Todos los usuarios
    SUPPORT_ENGINEER = "support_engineer"  # Ingeniero de soporte
    ADMIN = "admin"                    # Administrador / Dashboard


# Jerarquía de roles (mayor número = más privilegios)
ROLE_HIERARCHY = {
    UserRole.EMPLOYEE: 1,
    UserRole.SUPPORT_ENGINEER: 2,
    UserRole.ADMIN: 3,
}


def has_minimum_role(user_role: UserRole, required_role: UserRole) -> bool:
    """
    Verifica si un usuario tiene al menos el rol requerido.
    Ejemplo: has_minimum_role(ADMIN, SUPPORT_ENGINEER) → True
    """
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(required_role, 0)


# Permisos por módulo
MODULE_PERMISSIONS = {
    "employee_chat": [UserRole.EMPLOYEE, UserRole.SUPPORT_ENGINEER, UserRole.ADMIN],
    "support_rag": [UserRole.SUPPORT_ENGINEER, UserRole.ADMIN],
    "server_validation": [UserRole.SUPPORT_ENGINEER, UserRole.ADMIN],
    "dashboard": [UserRole.ADMIN],
    "faq_management": [UserRole.ADMIN],
}


def can_access_module(user_role: UserRole, module: str) -> bool:
    """
    Verifica si un rol tiene acceso a un módulo específico.
    """
    allowed_roles = MODULE_PERMISSIONS.get(module, [])
    return user_role in allowed_roles
