"""
Crea el primer usuario administrador de BOTIQ.

Windows CMD:  docker-compose exec backend python create_admin.py
Linux/Mac:    docker-compose exec backend python create_admin.py
"""
import asyncio, sys


async def main():
    print("\n🤖 BOTIQ — Crear usuario administrador")
    print("=" * 45)
    email = input("Email:      ").strip()
    full_name = input("Nombre:     ").strip()
    password = input("Contraseña: ").strip()
    if not email or not full_name or not password:
        print("❌ Todos los campos son obligatorios"); sys.exit(1)
    if len(password) < 8:
        print("❌ La contraseña debe tener al menos 8 caracteres"); sys.exit(1)

    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.core.config import settings
    from app.core.security import hash_password
    from app.core.roles import UserRole
    from app.db.session import Base
    from app.models.user import User
    from app.models import conversation, faq, server_log, knowledge_gap, audit_log  # noqa

    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        r = await session.execute(select(User).where(User.email == email))
        existing = r.scalar_one_or_none()
        if existing:
            print(f"\n⚠️  Ya existe usuario con email: {email} (rol: {existing.role.value})")
            ans = input("¿Cambiar rol a admin? (s/n): ").strip().lower()
            if ans == "s":
                existing.role = UserRole.ADMIN
                existing.is_active = True
                await session.commit()
                print(f"✅ Rol actualizado a ADMIN para {email}")
        else:
            user = User(email=email, full_name=full_name,
                        hashed_password=hash_password(password), role=UserRole.ADMIN, is_active=True)
            session.add(user)
            await session.commit()
            print(f"\n✅ Admin creado: {email}")
    await engine.dispose()
    print("\nAhora inicia sesión en http://localhost:5173")


if __name__ == "__main__":
    asyncio.run(main())
