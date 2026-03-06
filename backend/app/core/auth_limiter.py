# app/core/auth_limiter.py
import time
import hashlib
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)


class LoginAttemptTracker:
    """
    Отслеживает неудачные попытки входа и блокирует при превышении лимита
    Поддерживает блокировку по email, IP и комбинации email+IP
    """

    def __init__(self):
        # Хранилище попыток: ключ -> список временных меток
        self.attempts: Dict[str, list] = defaultdict(list)

        # Заблокированные ключи: ключ -> время разблокировки
        self.blocked: Dict[str, float] = {}

        # Блокировка для потокобезопасности
        self.lock = asyncio.Lock()

        # Настройки
        self.max_attempts = settings.MAX_LOGIN_ATTEMPTS
        self.block_minutes = settings.LOGIN_BLOCK_MINUTES
        self.window_minutes = 15  # Окно для подсчета попыток

        logger.info(
            f"🔒 LoginAttemptTracker инициализирован: {self.max_attempts} попыток за {self.window_minutes} мин, блокировка {self.block_minutes} мин")

    def _get_email_key(self, email: str) -> str:
        """Ключ для блокировки по email"""
        return f"email:{email.lower()}"

    def _get_ip_key(self, ip: str) -> str:
        """Ключ для блокировки по IP"""
        return f"ip:{ip}"

    def _get_combined_key(self, email: str, ip: str) -> str:
        """Ключ для блокировки по комбинации email+IP"""
        # Хэшируем комбинацию для безопасности
        combined = f"{email.lower()}:{ip}".encode()
        hash_obj = hashlib.sha256(combined)
        return f"combined:{hash_obj.hexdigest()[:16]}"

    async def record_failed_attempt(self, email: str, ip: str) -> Tuple[bool, Optional[str]]:
        """
        Записывает неудачную попытку входа
        Возвращает (заблокирован_ли, сообщение_о_блокировке)
        """
        now = time.time()
        email_key = self._get_email_key(email)
        ip_key = self._get_ip_key(ip)
        combined_key = self._get_combined_key(email, ip)

        async with self.lock:
            # Проверяем, не заблокированы ли уже
            for key in [email_key, ip_key, combined_key]:
                if key in self.blocked:
                    if now < self.blocked[key]:
                        wait_minutes = int((self.blocked[key] - now) / 60)
                        return True, f"Слишком много попыток. Попробуйте через {wait_minutes} мин."
                    else:
                        # Снимаем блокировку
                        del self.blocked[key]

            # Записываем попытку для всех ключей
            for key in [email_key, ip_key, combined_key]:
                # Очищаем старые попытки
                self.attempts[key] = [t for t in self.attempts[key]
                                      if t > now - (self.window_minutes * 60)]

                # Добавляем новую попытку
                self.attempts[key].append(now)

                # Проверяем лимит
                if len(self.attempts[key]) >= self.max_attempts:
                    # Блокируем
                    block_until = now + (self.block_minutes * 60)
                    self.blocked[key] = block_until

                    # Логируем блокировку
                    logger.warning(f"🔒 Заблокирован {key} до {datetime.fromtimestamp(block_until)}")

                    # Очищаем попытки
                    del self.attempts[key]

                    return True, f"Слишком много попыток. Аккаунт заблокирован на {self.block_minutes} мин."

            # Периодическая очистка старых записей
            if len(self.attempts) > 1000:
                self._cleanup_old_attempts()

            return False, "OK"

    async def record_successful_attempt(self, email: str, ip: str):
        """
        Записывает успешный вход - очищает историю попыток
        """
        async with self.lock:
            email_key = self._get_email_key(email)
            ip_key = self._get_ip_key(ip)
            combined_key = self._get_combined_key(email, ip)

            # Очищаем попытки для всех ключей
            for key in [email_key, ip_key, combined_key]:
                if key in self.attempts:
                    del self.attempts[key]

                # Снимаем блокировку если была
                if key in self.blocked:
                    del self.blocked[key]

            logger.info(f"✅ Успешный вход для {email}, история попыток очищена")

    async def is_blocked(self, email: str, ip: str) -> Tuple[bool, Optional[str]]:
        """
        Проверяет, заблокирован ли email или IP
        """
        now = time.time()

        async with self.lock:
            for key in [self._get_email_key(email),
                        self._get_ip_key(ip),
                        self._get_combined_key(email, ip)]:
                if key in self.blocked:
                    if now < self.blocked[key]:
                        wait_minutes = int((self.blocked[key] - now) / 60)
                        return True, f"Аккаунт заблокирован. Попробуйте через {wait_minutes} мин."
                    else:
                        # Снимаем блокировку
                        del self.blocked[key]

        return False, None

    async def get_remaining_attempts(self, email: str, ip: str) -> int:
        """
        Возвращает количество оставшихся попыток
        """
        now = time.time()
        email_key = self._get_email_key(email)

        async with self.lock:
            # Очищаем старые попытки
            if email_key in self.attempts:
                self.attempts[email_key] = [t for t in self.attempts[email_key]
                                            if t > now - (self.window_minutes * 60)]
                used = len(self.attempts[email_key])
                return max(self.max_attempts - used, 0)

        return self.max_attempts

    def _cleanup_old_attempts(self):
        """Очистка старых записей"""
        now = time.time()

        # Очищаем попытки старше окна
        for key in list(self.attempts.keys()):
            self.attempts[key] = [t for t in self.attempts[key]
                                  if t > now - (self.window_minutes * 60)]
            if not self.attempts[key]:
                del self.attempts[key]

        # Очищаем истекшие блокировки
        for key in list(self.blocked.keys()):
            if now >= self.blocked[key]:
                del self.blocked[key]

        logger.debug(f"🧹 Очистка: {len(self.attempts)} активных попыток, {len(self.blocked)} активных блокировок")


# Создаем глобальный экземпляр
login_attempt_tracker = LoginAttemptTracker()