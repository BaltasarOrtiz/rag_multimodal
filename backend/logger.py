import sys
from loguru import logger as _base_logger


def setup_logging() -> None:
    _base_logger.remove()
    _base_logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DDTHH:mm:ss.SSS}Z | {level} | {extra[request_id]} | {message}",
        serialize=True,   # JSON estructurado — request_id aparece en el campo 'extra'
        level="INFO",
    )


setup_logging()

# Bind a default request_id so the format field always exists outside request context
logger = _base_logger.bind(request_id="")

__all__ = ["logger"]
