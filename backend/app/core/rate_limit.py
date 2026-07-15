"""
rate_limit.py — Instancia única de slowapi Limiter.

Antes vivía inline en main.py. Se extrae a su propio módulo para que
las routes (auth.py, chat.py, etc.) puedan importar `limiter` y aplicar
límites específicos con @limiter.limit(...) sin crear un import circular
con main.py (que a su vez importa el router de routes).

Uso en una route:
    from app.core.rate_limit import limiter
    from app.core.config import settings

    @router.post("/login")
    @limiter.limit(settings.LOGIN_RATE_LIMIT)
    async def login(request: Request, ...):
        ...

IMPORTANTE: el parámetro `request: Request` es obligatorio en el
endpoint decorado — slowapi lo necesita para leer la IP remota.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.RATE_LIMIT_ENABLED,
    default_limits=[settings.API_RATE_LIMIT],
)