import time
import hashlib
from collections import defaultdict
from typing import Dict, Optional, Tuple, Set
import asyncio

from app.core.config import settings
from app.core.ratelimit.base import RateLimiterInterface


def check_suspicious_activity(message: str) -> bool:
    """
    Проверка на подозрительную активность
    """
    if not message:
        return False

    # 1. Проверяем длину
    if len(message) > settings.MAX_MESSAGE_LENGTH:
        return True

    # 2. Проверяем URL короткие ссылки
    url_patterns = ['bit.ly', 'goo.gl', 'tinyurl', 'is.gd', 'clck.ru', 'shorturl']
    message_lower = message.lower()
    if any(pattern in message_lower for pattern in url_patterns):
        return True

    return False


class MemoryRateLimiter(RateLimiterInterface):
    """
    Rate limiter в памяти для разработки
    (твой текущий WidgetRateLimiter с небольшими изменениями)
    """

    def __init__(self):
        self.requests: Dict[str, list] = {}
        self.blocked_ips: Dict[str, float] = {}
        self.active_sessions: Dict[str, Set[str]] = defaultdict(set)
        self.lock = asyncio.Lock()

    def _get_key(self, tenant_id: str, client_id: Optional[str] = None,
                 session_id: Optional[str] = None, client_ip: Optional[str] = None) -> str:
        """Генерирует ключ для rate limiting"""
        if client_id and client_id.startswith('client_'):
            return f"{tenant_id}:client:{client_id}"
        elif session_id:
            ip_part = hashlib.md5(client_ip.encode()).hexdigest()[:8] if client_ip else "noip"
            return f"{tenant_id}:session:{session_id}:{ip_part}"
        elif client_ip:
            return f"{tenant_id}:ip:{client_ip}"
        else:
            return f"{tenant_id}:unknown:{int(time.time())}"

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
        if client_ip and client_ip in self.blocked_ips:
            if now < self.blocked_ips[client_ip]:
                wait_time = int(self.blocked_ips[client_ip] - now)
                return False, f"IP заблокирован. Осталось {wait_time} сек."
            else:
                async with self.lock:
                    del self.blocked_ips[client_ip]

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

        key = self._get_key(tenant_id, client_id, session_id, client_ip)

        async with self.lock:
            history = self.requests.get(key, [])
            history = [t for t in history if t > now - period]

            if len(history) >= max_requests:
                wait_time = int(history[0] + period - now)
                return False, f"Слишком много запросов. Подождите {wait_time} сек."

            history.append(now)
            self.requests[key] = history

            # Проверяем активность с IP
            if client_ip and session_id:
                self.active_sessions[client_ip].add(session_id)
                if len(self.active_sessions[client_ip]) > settings.MAX_SESSIONS_PER_IP_PER_HOUR:
                    self.blocked_ips[client_ip] = now + (settings.IP_BLOCK_DURATION_HOURS * 3600)
                    self._cleanup_ip_sessions(client_ip)
                    return False, f"IP заблокирован за подозрительную активность"

            if len(self.requests) > 1000:
                self._cleanup_old_keys()

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

        key = self._get_key(tenant_id, client_id, session_id, client_ip)

        async with self.lock:
            history = self.requests.get(key, [])
            history = [t for t in history if t > now - period]
            used = len(history)

        return max(max_requests - used, 0)

    async def reset_limit(
            self,
            tenant_id: str,
            client_id: Optional[str] = None,
            session_id: Optional[str] = None,
            client_ip: Optional[str] = None
    ):
        key = self._get_key(tenant_id, client_id, session_id, client_ip)
        async with self.lock:
            if key in self.requests:
                del self.requests[key]

    def _cleanup_ip_sessions(self, ip: str):
        if ip in self.active_sessions:
            del self.active_sessions[ip]

    def _cleanup_old_keys(self):
        now = time.time()
        expired_keys = []

        for key, history in self.requests.items():
            if all(t < now - 3600 for t in history):
                expired_keys.append(key)

        for key in expired_keys:
            del self.requests[key]

        expired_ips = []
        for ip, sessions in self.active_sessions.items():
            if ip not in self.blocked_ips:
                has_recent = False
                for key in self.requests:
                    if f":ip:{ip}" in key or f":{ip}" in key:
                        has_recent = True
                        break
                if not has_recent:
                    expired_ips.append(ip)

        for ip in expired_ips:
            del self.active_sessions[ip]