"""Logging estruturado com structlog."""
import logging

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configura logging estruturado com structlog."""
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    """Retorna um logger structlog com o nome do módulo."""
    return structlog.get_logger(name)
