"""Configuracao de logging estruturado com structlog (CONVENTION §2)."""

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    """Configura structlog como logger padrao do servico auth.

    - Formato JSON para compatibilidade com Loki (producao)
    - ConsoleRenderer colorido em dev (json_logs=False)
    - Timestamps ISO 8601
    - Niveis de log via add_log_level
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    """Retorna um logger structlog vinculado ao modulo.

    Uso:
        from app.utils.logconfig import get_logger
        logger = get_logger(__name__)
        logger.info("evento", chave="valor")
    """
    return structlog.get_logger(name or __name__)
