# app/core/cleanup.py
import asyncio
import logging
from datetime import datetime, timedelta

from app.core.storage import storage_manager

logger = logging.getLogger(__name__)


async def cleanup_temp_sessions():
    """Очищает старые временные сессии (запускать по расписанию)"""
    logger.info("Запуск очистки временных сессий...")

    # Эта функция будет вызываться периодически
    # StorageManager сам удалит истекшие записи по TTL
    # Дополнительно можно добавить логику для ручной очистки

    logger.info("Очистка временных сессий завершена")


# Функция для запуска в отдельном потоке
async def run_cleanup_periodically():
    while True:
        await asyncio.sleep(3600)  # Каждый час
        await cleanup_temp_sessions()