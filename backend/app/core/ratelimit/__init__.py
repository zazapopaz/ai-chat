import logging
from app.core.config import settings
from app.core.storage import storage_manager

logger = logging.getLogger(__name__)

# Импортируем реализации
from app.core.ratelimit.memory import MemoryRateLimiter

# Redis импортируем только если нужен (чтобы не было ошибок если redis не установлен)
try:
    from app.core.ratelimit.redis import RedisRateLimiter

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis не установлен, используется MemoryRateLimiter")


class RateLimiterFactory:
    """Фабрика для создания rate limiter'а в зависимости от окружения"""

    @staticmethod
    def create():
        """Создает подходящий rate limiter"""

        # В production пробуем использовать Redis
        if settings.ENVIRONMENT == "production":
            # Ищем Redis клиент в storage_manager
            redis_client = None
            for storage in storage_manager.storages:
                if hasattr(storage, 'client') and storage.client:
                    try:
                        # Пробуем сделать ping чтобы убедиться что Redis работает
                        import asyncio
                        asyncio.create_task(storage.client.ping())
                        redis_client = storage.client
                        logger.info("Найден рабочий Redis клиент")
                        break
                    except:
                        continue

            if redis_client and REDIS_AVAILABLE:
                logger.info("Production режим: используем RedisRateLimiter")
                return RedisRateLimiter(redis_client)
            else:
                logger.warning(
                    "Production режим: Redis не доступен, "
                    "используем MemoryRateLimiter (лимиты сбросятся при рестарте!)"
                )

        # По умолчанию (development или если Redis не доступен)
        logger.info("💻 Используем MemoryRateLimiter")
        return MemoryRateLimiter()


# Создаем глобальный экземпляр
widget_limiter = RateLimiterFactory.create()