# app/core/ratelimit/base.py
from abc import ABC, abstractmethod
from typing import Optional, Tuple


class RateLimiterInterface(ABC):
    """Интерфейс для rate limiter'ов"""

    @abstractmethod
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
        """
        Проверить лимит запросов
        Returns: (разрешено, сообщение)
        """
        pass

    @abstractmethod
    async def get_remaining_requests(
            self,
            tenant_id: str,
            action: str,
            client_id: Optional[str] = None,
            session_id: Optional[str] = None,
            client_ip: Optional[str] = None
    ) -> int:
        """Получить количество оставшихся запросов"""
        pass

    @abstractmethod
    async def reset_limit(
            self,
            tenant_id: str,
            client_id: Optional[str] = None,
            session_id: Optional[str] = None,
            client_ip: Optional[str] = None
    ):
        """Сбросить лимит"""
        pass