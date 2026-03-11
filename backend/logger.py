import sys
from loguru import logger


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DDTHH:mm:ss.SSS}Z | {level} | {message}",
        serialize=True,   # JSON estructurado
        level="INFO",
    )


setup_logging()

__all__ = ["logger"]
