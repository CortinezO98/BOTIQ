from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.security import decode_token
from app.core.roles import UserRole, has_minimum_role
from app.core.widget_security import validate_widget_request_context
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User

# auto_error=False: si no hay header Authorization, NO lanza 401 acá — dejamos
# que get_current_user intente la cookie httpOnly antes de fallar. Así no se
# rompe nada que ya use el header Bearer (scripts, Postman, Swagger).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _resolve_token(request: Request, header_token: Optional[str]) -> str:
    if header_token:
        return header_token

    cookie_token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if cookie_token:
        return cookie_token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    request: Request,
    header_token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = _resolve_token(request, header_token)
    data = decode_token(token)

    if data.get("purpose") == "widget_access":
        validate_widget_request_context(request, data)

    result = await db.execute(
        select(User).where(
            User.id == data["user_id"],
            User.is_active == True,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )

    # Defensa en profundidad: los tokens del widget se emiten únicamente para
    # identidades employee. Aunque una cuenta cambie de rol después de emitir
    # el token, ese JWT no debe convertirse en una sesión de soporte/admin.
    if (
        data.get("purpose") == "widget_access"
        and user.role != UserRole.EMPLOYEE
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El widget externo solo admite el perfil Empleado.",
        )

    request.state.auth_claims = data
    return user


def require_role(minimum_role: UserRole):
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_minimum_role(current_user.role, minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere rol: {minimum_role.value}",
            )
        return current_user
    return checker


require_employee = require_role(UserRole.EMPLOYEE)
require_support = require_role(UserRole.SUPPORT_ENGINEER)
require_admin = require_role(UserRole.ADMIN)
