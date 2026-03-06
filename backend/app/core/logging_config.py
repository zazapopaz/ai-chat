# app/core/logging_config.py
import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path

from app.core.config import settings


def setup_logging():
    """
    Настройка логирования в файлы и консоль
    """
    # Создаем папку для логов если её нет
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Формат логов
    detailed_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    simple_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Очищаем существующие handler'ы (чтобы не дублировать при перезагрузке)
    root_logger.handlers.clear()

    # 1. Консольный handler (всегда нужен)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(simple_format)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # 2. Файловый handler для всех логов (ротация по размеру)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=10_485_760,  # 10 MB
        backupCount=5,  # хранить 5 файлов
        encoding='utf-8'
    )
    file_handler.setFormatter(detailed_format)
    file_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    root_logger.addHandler(file_handler)

    # 3. Отдельный файл для ошибок (чтобы быстро искать)
    error_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "error.log",
        maxBytes=10_485_760,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setFormatter(detailed_format)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)

    # 4. Отдельный файл для аудита (важные действия)
    audit_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "audit.log",
        maxBytes=10_485_760,
        backupCount=3,
        encoding='utf-8'
    )
    audit_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    audit_handler.setLevel(logging.INFO)

    # Создаем отдельный логгер для аудита
    audit_logger = logging.getLogger("audit")
    audit_logger.propagate = False  # не отправлять в корневой логгер
    audit_logger.addHandler(audit_handler)
    audit_logger.setLevel(logging.INFO)

    # 5. Для продакшена добавляем JSON формат (удобно для парсинга)
    if settings.ENVIRONMENT == "production":
        import json_logging
        import sys

        # JSON handler для структурированных логов
        json_handler = logging.StreamHandler(sys.stdout)
        json_handler.setFormatter(json_logging.JSONLogFormatter())
        json_handler.setLevel(logging.INFO)
        root_logger.addHandler(json_handler)

    logging.info(f"✅ Логирование настроено. Файлы логов: {log_dir.absolute()}")
    return root_logger