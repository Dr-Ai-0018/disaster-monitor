"""
统一日志模块（loguru）
"""
import sys
from pathlib import Path
from loguru import logger as _logger


def setup_logger(log_file: str = "logs/disaster.log", level: str = "INFO"):
    """初始化日志配置"""
    _logger.remove()

    # 控制台输出
    _logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # 文件输出（按日期滚动）
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        _logger.add(
            log_file.replace(".log", "_{time:YYYY-MM-DD}.log"),
            rotation="00:00",
            retention="30 days",
            level="DEBUG",
            encoding="utf-8",
        )

    return _logger


def get_logger(name: str = __name__):
    return _logger.bind(name=name)
