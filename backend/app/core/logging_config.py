"""
logging_config.py — Logging estructurado para BOTIQ.

Uso:
    from app.core.logging_config import get_logger
    logger = get_logger(__name__)

    logger.info("rag_response", conversation_id=str(conv_id), tokens=1234, latency_ms=456)
    logger.warning("knowledge_gap", query="dame el paso a paso", module="support_rag")
    logger.error("gemini_error", error=str(exc), model="gemini-2.5-flash")

En desarrollo (ENVIRONMENT != production): formato legible por humanos.
En producción: JSON de una línea por evento, listo para ingestión en Cloud Logging, Datadog, Loki o cualquier stack de observabilidad.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, MutableMapping

from app.core.config import settings


class _JsonFormatter(logging.Formatter):
    """
    Formateador JSON de una línea. Cada evento incluye:
        - timestamp  ISO-8601 UTC
        - level      DEBUG / INFO / WARNING / ERROR / CRITICAL
        - logger     nombre del módulo Python
        - message    texto del evento
      - **kwargs   campos extra pasados al logger (conversation_id, tokens, etc.)
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Campos extra pasados como kwargs al logger
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "exc_info", "exc_text",
                "message",
            }:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class _DevFormatter(logging.Formatter):
    """
    Formato legible para desarrollo:
    [2026-06-17 15:40:31] INFO     app.services.support_rag — rag_response | conv=abc123 tokens=1234
    """

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        color = self.LEVEL_COLORS.get(record.levelname, "")
        level = f"{color}{record.levelname:<8}{self.RESET}"

        extras: list[str] = []
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "exc_info", "exc_text",
                "message",
            }:
                extras.append(f"{key}={value}")

        extra_str = " | " + " ".join(extras) if extras else ""
        line = f"[{ts}] {level} {record.name} — {record.getMessage()}{extra_str}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


class _BotiqLogger(logging.LoggerAdapter):
    """
    Adapter que permite pasar campos extra como kwargs directos:
        logger.info("evento", conversation_id="abc", tokens=123)
    en vez del verbose:
        logger.info("evento", extra={"conversation_id": "abc", "tokens": 123})
    """

    def process(
        self, msg: str, kwargs: MutableMapping[str, Any]
    ) -> tuple[str, MutableMapping[str, Any]]:
        extra = dict(self.extra or {})
        # Todo lo que no sea un argumento estándar de logging lo trata como campo extra
        for key in list(kwargs.keys()):
            if key not in {"exc_info", "stack_info", "stacklevel"}:
                extra[key] = kwargs.pop(key)
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging() -> None:
    """
    Configura el sistema de logging global de BOTIQ.
    Llamar una sola vez en el startup de la app (main.py lifespan).
    """
    is_production = settings.ENVIRONMENT.lower() == "production"
    level = logging.DEBUG if settings.DEBUG else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    # Limpiar handlers existentes para evitar duplicados en reloads de uvicorn
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(_JsonFormatter() if is_production else _DevFormatter())
    root.addHandler(handler)

    # Silenciar librerías muy verbosas en INFO
    for noisy in ("sqlalchemy.engine", "httpx", "httpcore", "urllib3", "google.auth"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # uvicorn ya tiene su propio handler — no duplicar
    logging.getLogger("uvicorn.access").propagate = False


def get_logger(name: str, **base_fields: Any) -> _BotiqLogger:
    """
    Retorna un logger estructurado para el módulo dado.

    Args:
        name: normalmente __name__ del módulo
        **base_fields: campos que se incluyen en TODOS los logs de este logger (p.ej. module="support_rag", service="gemini")
    """
    return _BotiqLogger(logging.getLogger(name), base_fields)