import logging
from app.core.config import settings
from app.core.storage import storage_manager

logger = logging.getLogger(__name__)

from app.core.ratelimit.memory import MemoryRateLimiter

try:
    from app.core.ratelimit.redis import RedisRateLimiter
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis не установлен, используется MemoryRateLimiter")

class RateLimiterFactory:
    @staticmethod
    def create():
        if settings.ENVIRONMENT == "production":
            redis_client = None
            for storage in storage_manager.storages:
                if hasattr(storage, 'client') and storage.client:
                    try:
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
                logger.warning("⚠Production режим: Redis не доступен, используем MemoryRateLimiter")

        logger.info("Используем MemoryRateLimiter")
        return MemoryRateLimiter()

widget_limiter = RateLimiterFactory.create()