# app/core/ratelimit/redis.py
import time
import hashlib
import json
from typing import Optional, Tuple
import redis.asyncio as redis

from app.core.config import settings
from app.core.ratelimit.base import RateLimiterInterface


class RedisRateLimiter(RateLimiterInterface):
    """
    Rate limiter на Redis для продакшена
    Данные общие для всех инстансов, не сбрасываются при рестарте
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self.prefix = "ratelimit:"

    def _get_key(self, tenant_id: str, action: str,
                 client_id: Optional[str] = None,
                 session_id: Optional[str] = None,
                 client_ip: Optional[str] = None) -> str:
        """Генерирует ключ для Redis"""
        if client_id and client_id.startswith('client_'):
            return f"{self.prefix}{tenant_id}:{action}:client:{client_id}"
        elif session_id:
            ip_part = hashlib.md5(client_ip.encode()).hexdigest()[:8] if client_ip else "noip"
            return f"{self.prefix}{tenant_id}:{action}:session:{session_id}:{ip_part}"
        elif client_ip:
            return f"{self.prefix}{tenant_id}:{action}:ip:{client_ip}"
        else:
            return f"{self.prefix}{tenant_id}:{action}:unknown"

    def _get_block_key(self, client_ip: str) -> str:
        """Ключ для заблокированных IP"""
        return f"{self.prefix}blocked:{client_ip}"

    async def check_limit(
            self,
            tenant_id: str,
            action: str,
            client_id: Optional[str] = None,
            session_id: Optional[str] = None,
            client_ip: Optional[str] = None,
            max_requests: Optional[int] = None,
            period: int = 60
    ) -> Tuple[bool, str]:
        now = time.time()

        # Проверяем блокировку IP
        if client_ip:
            block_key = self._get_block_key(client_ip)
            blocked = await self.redis.get(block_key)
            if blocked:
                ttl = await self.redis.ttl(block_key)
                return False, f"IP заблокирован. Осталось {ttl} сек."

        # Определяем лимит
        if max_requests is None:
            if action == 'message':
                max_requests = settings.RATE_LIMIT_WIDGET_MESSAGES
            elif action == 'start':
                max_requests = settings.RATE_LIMIT_WIDGET_STARTS
            elif action == 'contact':
                max_requests = settings.RATE_LIMIT_CONTACT_SAVES
            else:
                max_requests = settings.RATE_LIMIT_REQUESTS_PER_MINUTE

        key = self._get_key(tenant_id, action, client_id, session_id, client_ip)
        pipe = self.redis.pipeline()

        # Добавляем текущий timestamp в sorted set
        now_ms = int(now * 1000)
        min_score = now_ms - (period * 1000)

        pipe.zadd(key, {str(now_ms): now_ms})
        pipe.zremrangebyscore(key, 0, min_score)  # удаляем старые
        pipe.zcard(key)  # считаем количество
        pipe.expire(key, period * 2)  # TTL на всякий случай

        results = await pipe.execute()
        current_count = results[3]  # zcard результат

        if current_count > max_requests:
            # Слишком много запросов
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_time = oldest[0][1] / 1000
                wait_time = int(oldest_time + period - now)
                return False, f"Слишком много запросов. Подождите {wait_time} сек."
            return False, "Слишком много запросов"

        # Проверяем количество сессий с IP (для защиты от DDoS)
        if client_ip and session_id and action == 'start':
            sessions_key = f"{self.prefix}sessions:{client_ip}"
            await self.redis.sadd(sessions_key, session_id)
            sessions_count = await self.redis.scard(sessions_key)

            if sessions_count > settings.MAX_SESSIONS_PER_IP_PER_HOUR:
                # Блокируем IP на час
                block_key = self._get_block_key(client_ip)
                await self.redis.setex(
                    block_key,
                    settings.IP_BLOCK_DURATION_HOURS * 3600,
                    "1"
                )
                # Очищаем сессии
                await self.redis.delete(sessions_key)
                return False, f"IP заблокирован за подозрительную активность"

            # Сессии живут час
            await self.redis.expire(sessions_key, 3600)

        return True, "OK"

    async def get_remaining_requests(
            self,
            tenant_id: str,
            action: str,
            client_id: Optional[str] = None,
            session_id: Optional[str] = None,
            client_ip: Optional[str] = None
    ) -> int:
        now = time.time()
        period = 60

        if action == 'message':
            max_requests = settings.RATE_LIMIT_WIDGET_MESSAGES
        elif action == 'start':
            max_requests = settings.RATE_LIMIT_WIDGET_STARTS
        elif action == 'contact':
            max_requests = settings.RATE_LIMIT_CONTACT_SAVES
        else:
            max_requests = settings.RATE_LIMIT_REQUESTS_PER_MINUTE

        key = self._get_key(tenant_id, action, client_id, session_id, client_ip)

        # Считаем количество за последние period секунд
        min_score = (now - period) * 1000
        count = await self.redis.zcount(key, min_score, now * 1000)

        return max(max_requests - count, 0)

    async def reset_limit(
            self,
            tenant_id: str,
            client_id: Optional[str] = None,
            session_id: Optional[str] = None,
            client_ip: Optional[str] = None
    ):
        """Сбрасывает лимиты для всех actions"""
        pattern = f"{self.prefix}{tenant_id}:*"
        if client_id:
            pattern = f"{self.prefix}{tenant_id}:*:client:{client_id}"
        elif session_id:
            ip_part = hashlib.md5(client_ip.encode()).hexdigest()[:8] if client_ip else "noip"
            pattern = f"{self.prefix}{tenant_id}:*:session:{session_id}:{ip_part}"
        elif client_ip:
            pattern = f"{self.prefix}{tenant_id}:*:ip:{client_ip}"

        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)