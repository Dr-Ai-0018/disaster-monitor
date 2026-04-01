from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logger(log_file: str, level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stdout, level=level.upper(), enqueue=False)
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logger.add(log_file, level=level.upper(), rotation="10 MB", retention=5, enqueue=False)


def get_logger(name: str):
    return logger.bind(module=name)
