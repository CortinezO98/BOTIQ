from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.security import decode_token
from app.core.roles import UserRole, has_minimum_role
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    data = decode_token(token)
    result = await db.execute(
        select(User).where(User.id == data["user_id"], User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
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


