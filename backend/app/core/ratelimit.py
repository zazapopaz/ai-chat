from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import Optional
import json
from fastapi import Request, Response
from collections import defaultdict
import time

from app.core.config import settings

# Глобальный лимитер для разных случаев
limiter = Limiter(key_func=get_remote_address)


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (не связанные с rate limiting)

def validate_client_id(client_id: Optional[str]) -> bool:
    """
    Проверка формата client_id
    """
    if client_id is None:
        return True
    # Наш формат: client_время_рандом
    if client_id.startswith('client_'):
        return True
    # Если не наш формат, но есть значение - считаем валидным
    return len(client_id) < 100


def generate_client_id() -> str:
    """
    Генерация нового client_id (для виджета)
    """
    import secrets
    import time
    random_part = secrets.token_urlsafe(8).replace('-', '').replace('_', '')
    return f"client_{int(time.time())}_{random_part}"


class RateLimitMiddleware:
    """
    Middleware для глобального rate limiting
    """

    def __init__(self, app):
        self.app = app
        self.ip_requests = defaultdict(list)

    async def __call__(self, request: Request, call_next):
        client_ip = request.client.host
        now = time.time()

        # Проверяем глобальный лимит по IP
        self.ip_requests[client_ip] = [t for t in self.ip_requests[client_ip]
                                       if t > now - 60]

        if len(self.ip_requests[client_ip]) >= settings.MAX_REQUESTS_BEFORE_BLOCK:
            return Response(
                content=json.dumps({"error": "Слишком много запросов", "blocked": True}),
                status_code=429,
                media_type="application/json"
            )

        self.ip_requests[client_ip].append(now)

        # Продолжаем обработку
        response = await call_next(request)
        return response


# Декоратор для rate limiting в эндпоинтах
def rate_limit(limit: str):
    """Пример: @rate_limit("10/minute")"""
    return limiter.limit(limit)