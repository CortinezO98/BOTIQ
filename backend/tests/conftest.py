"""
Antes había un fixture event_loop(scope="session") acá para forzar un único
event loop compartido en toda la sesión de tests.

Con pytest-asyncio 1.x ese mecanismo ya no se respeta de forma confiable:
pytest-asyncio vuelve a crear un event loop nuevo por cada test función
(scope "function" por defecto), y el pool de conexiones async de SQLAlchemy
(creado una sola vez, a nivel de módulo, en app/db/session.py) queda con
conexiones ancladas al loop del primer test que las usó. Cuando un test
posterior corre en OTRO loop y SQLAlchemy intenta reutilizar esa conexión
pooleada, asyncpg revienta con:
    RuntimeError: ... got Future ... attached to a different loop

El reemplazo correcto es configurar el scope de sesión directamente en
pytest.ini (asyncio_default_fixture_loop_scope / asyncio_default_test_loop_scope
= session), que sí es el mecanismo soportado en pytest-asyncio 1.x para
lograr lo mismo que hacía este fixture. Ver pytest.ini.
"""