# app/core/verification.py
import random
import string
import json
from datetime import datetime
from typing import Optional, Dict, Any
import logging
import redis.asyncio as redis

from app.core.config import settings
from app.core.storage import storage_manager

logger = logging.getLogger(__name__)


class VerificationService:
    """Сервис для управления верификацией email и 2FA кодами"""

    def __init__(self):
        self.redis = None
        self.prefix_verify = "verify:"  # Для подтверждения email
        self.prefix_2fa = "2fa:"  # Для двухфакторки
        self.prefix_2fa_enabled = "2fa_enabled:"  # Для хранения настроек 2FA
        self.use_redis = False  # Флаг использования Redis
        self.use_storage_manager = True  # Используем новый StorageManager

    async def init_redis(self):
        """Инициализация подключения к Redis"""
        if not self.redis and settings.REDIS_URL:
            try:
                self.redis = await redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2,  # Таймаут подключения 2 секунды
                    socket_timeout=2  # Таймаут операций 2 секунды
                )
                # Проверяем подключение
                await self.redis.ping()
                self.use_redis = True
                logger.info("✅ Подключение к Redis установлено")
            except Exception as e:
                logger.warning(f"⚠️ Redis недоступен: {e}")
                self.redis = None
                self.use_redis = False
                if settings.ENVIRONMENT == "production":
                    logger.error("❌ Redis обязателен для production режима!")
                    # В production не можем работать без Redis
                    raise
                else:
                    logger.info("🔄 Работаем в режиме без Redis (данные хранятся в StorageManager)")
        else:
            self.use_redis = False

    def generate_code(self, length: int = 6) -> str:
        """Генерация числового кода"""
        return ''.join(random.choices(string.digits, k=length))

    async def _get_redis(self):
        """Получение Redis клиента с ленивой инициализацией"""
        if self.redis is None and not self.use_redis:
            await self.init_redis()
        return self.redis

    async def _mock_store(self, key: str, data: dict, expire: int):
        """Имитация хранения в памяти (для обратной совместимости)"""
        if not hasattr(self, '_mock_storage'):
            self._mock_storage = {}

        # Добавляем время истечения
        data['_expire'] = datetime.utcnow().timestamp() + expire
        self._mock_storage[key] = data

        # Очищаем старые записи (каждые 100 записей)
        if len(self._mock_storage) % 100 == 0:
            self._cleanup_mock_storage()

        logger.debug(f"📝 Сохранено в память: {key} (истекает через {expire}с)")

    async def _mock_get(self, key: str) -> Optional[dict]:
        """Имитация получения из памяти (для обратной совместимости)"""
        if not hasattr(self, '_mock_storage'):
            return None

        data = self._mock_storage.get(key)
        if not data:
            return None

        # Проверяем не истекло ли
        now = datetime.utcnow().timestamp()
        if now > data.get('_expire', 0):
            del self._mock_storage[key]
            return None

        # Возвращаем копию без служебных полей
        result = {k: v for k, v in data.items() if not k.startswith('_')}
        return result

    async def _mock_delete(self, key: str):
        """Имитация удаления из памяти"""
        if hasattr(self, '_mock_storage') and key in self._mock_storage:
            del self._mock_storage[key]

    def _cleanup_mock_storage(self):
        """Очистка истекших записей из памяти"""
        if not hasattr(self, '_mock_storage'):
            return

        now = datetime.utcnow().timestamp()
        expired = [k for k, v in self._mock_storage.items()
                   if v.get('_expire', 0) < now]

        for k in expired:
            del self._mock_storage[k]

        if expired:
            logger.debug(f"🧹 Очищено {len(expired)} истекших записей из памяти")

    async def _storage_manager_store(self, key: str, data: dict, ttl: int) -> bool:
        """Сохранение через StorageManager"""
        try:
            return await storage_manager.set(key, data, ttl)
        except Exception as e:
            logger.error(f"Ошибка сохранения через StorageManager: {e}")
            return False

    async def _storage_manager_get(self, key: str) -> Optional[dict]:
        """Получение через StorageManager"""
        try:
            return await storage_manager.get(key)
        except Exception as e:
            logger.error(f"Ошибка получения через StorageManager: {e}")
            return None

    async def _storage_manager_delete(self, key: str) -> bool:
        """Удаление через StorageManager"""
        try:
            return await storage_manager.delete(key)
        except Exception as e:
            logger.error(f"Ошибка удаления через StorageManager: {e}")
            return False

    async def create_verification_code(self, email: str, purpose: str = "register") -> str:
        """
        Создание кода подтверждения для email
        purpose: register, reset_password
        """
        redis_client = await self._get_redis()

        code = self.generate_code()
        key = f"{self.prefix_verify}{purpose}:{email}"

        data = {
            "code": code,
            "email": email,
            "purpose": purpose,
            "created_at": datetime.utcnow().isoformat(),
            "attempts": 0,
            "verified": False
        }

        # Пробуем сохранить через StorageManager (он сам выберет лучшее хранилище)
        storage_success = await self._storage_manager_store(key, data, 900)

        if storage_success:
            logger.info(f"✅ Код верификации создан через StorageManager для {email}")
            return code

        # Fallback на старую логику если StorageManager не сработал
        if redis_client and self.use_redis:
            try:
                # Сохраняем в Redis на 15 минут
                await redis_client.setex(
                    key,
                    900,  # 15 минут
                    json.dumps(data)
                )
                logger.info(f"✅ Код верификации создан в Redis для {email}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка сохранения в Redis: {e}, используем память")
                await self._mock_store(key, data, 900)
        else:
            # Режим разработки - сохраняем в памяти
            await self._mock_store(key, data, 900)
            logger.info(f"✅ Код верификации создан в памяти для {email} (purpose: {purpose})")

        return code

    async def verify_code(self, email: str, code: str, purpose: str = "register") -> bool:
        """
        Проверка кода подтверждения
        """
        redis_client = await self._get_redis()
        key = f"{self.prefix_verify}{purpose}:{email}"

        # Сначала пробуем получить через StorageManager
        data = await self._storage_manager_get(key)
        used_storage_manager = data is not None

        if not data:
            # Пробуем получить из Redis
            if redis_client and self.use_redis:
                try:
                    data_json = await redis_client.get(key)
                    if data_json:
                        data = json.loads(data_json)
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка чтения из Redis: {e}")

        if not data:
            # Пробуем получить из памяти
            data = await self._mock_get(key)

        if not data:
            logger.warning(f"❌ Код не найден для {email}")
            return False

        # Проверяем количество попыток
        if data["attempts"] >= settings.VERIFICATION_MAX_ATTEMPTS:
            logger.warning(f"❌ Превышено количество попыток для {email}")
            # Удаляем код из всех хранилищ
            await self._storage_manager_delete(key)
            if redis_client and self.use_redis:
                await redis_client.delete(key)
            await self._mock_delete(key)
            return False

        # Увеличиваем счетчик попыток
        data["attempts"] += 1

        # Сохраняем обновленные данные
        if used_storage_manager:
            await self._storage_manager_store(key, data, 900)
        elif redis_client and self.use_redis:
            try:
                await redis_client.setex(key, 900, json.dumps(data))
            except Exception:
                await self._mock_store(key, data, 900)
        else:
            await self._mock_store(key, data, 900)

        # Проверяем код
        if data["code"] != code:
            logger.warning(f"❌ Неверный код для {email}")
            return False

        # Отмечаем как подтвержденный
        data["verified"] = True

        # Сохраняем финальное состояние
        if used_storage_manager:
            await self._storage_manager_store(key, data, 900)
        elif redis_client and self.use_redis:
            try:
                await redis_client.setex(key, 900, json.dumps(data))
            except Exception:
                await self._mock_store(key, data, 900)
        else:
            await self._mock_store(key, data, 900)

        logger.info(f"✅ Email {email} успешно подтвержден")
        return True

    async def is_verified(self, email: str, purpose: str = "register") -> bool:
        """Проверка, подтвержден ли уже email"""
        redis_client = await self._get_redis()
        key = f"{self.prefix_verify}{purpose}:{email}"

        # Сначала пробуем StorageManager
        data = await self._storage_manager_get(key)

        if not data and redis_client and self.use_redis:
            try:
                data_json = await redis_client.get(key)
                if data_json:
                    data = json.loads(data_json)
            except Exception:
                pass

        if not data:
            data = await self._mock_get(key)

        return data.get("verified", False) if data else False

    async def create_2fa_code(self, email: str) -> str:
        """
        Создание 2FA кода для входа
        """
        redis_client = await self._get_redis()

        code = self.generate_code()
        key = f"{self.prefix_2fa}{email}"

        data = {
            "code": code,
            "email": email,
            "created_at": datetime.utcnow().isoformat(),
            "attempts": 0
        }

        # Пробуем сохранить через StorageManager
        storage_success = await self._storage_manager_store(key, data, 600)

        if storage_success:
            logger.info(f"✅ 2FA код создан через StorageManager для {email}")
            return code

        # Fallback на старую логику
        if redis_client and self.use_redis:
            try:
                # Код живет 10 минут
                await redis_client.setex(
                    key,
                    600,  # 10 минут
                    json.dumps(data)
                )
                logger.info(f"✅ 2FA код создан в Redis для {email}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка сохранения 2FA в Redis: {e}, используем память")
                await self._mock_store(key, data, 600)
        else:
            await self._mock_store(key, data, 600)
            logger.info(f"✅ 2FA код создан в памяти для {email}")

        return code

    async def verify_2fa_code(self, email: str, code: str) -> bool:
        """
        Проверка 2FA кода
        """
        redis_client = await self._get_redis()
        key = f"{self.prefix_2fa}{email}"

        # Сначала пробуем StorageManager
        data = await self._storage_manager_get(key)
        used_storage_manager = data is not None

        if not data and redis_client and self.use_redis:
            try:
                data_json = await redis_client.get(key)
                if data_json:
                    data = json.loads(data_json)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка чтения 2FA из Redis: {e}")

        if not data:
            data = await self._mock_get(key)

        if not data:
            logger.warning(f"❌ 2FA код не найден для {email}")
            return False

        # Проверяем количество попыток
        if data["attempts"] >= settings.TWO_FACTOR_MAX_ATTEMPTS:
            logger.warning(f"❌ Превышено количество попыток 2FA для {email}")
            # Удаляем из всех хранилищ
            await self._storage_manager_delete(key)
            if redis_client and self.use_redis:
                await redis_client.delete(key)
            await self._mock_delete(key)
            return False

        # Увеличиваем счетчик
        data["attempts"] += 1

        # Сохраняем обновленные данные
        if used_storage_manager:
            await self._storage_manager_store(key, data, 600)
        elif redis_client and self.use_redis:
            try:
                await redis_client.setex(key, 600, json.dumps(data))
            except Exception:
                await self._mock_store(key, data, 600)
        else:
            await self._mock_store(key, data, 600)

        # Проверяем код
        if data["code"] != code:
            logger.warning(f"❌ Неверный 2FA код для {email}")
            return False

        # Успех - удаляем код из всех хранилищ
        await self._storage_manager_delete(key)
        if redis_client and self.use_redis:
            await redis_client.delete(key)
        await self._mock_delete(key)

        logger.info(f"✅ 2FA код успешно подтвержден для {email}")
        return True

    async def save_2fa_settings(self, user_id: str, email: str, enabled: bool = True):
        """
        Сохранение настроек 2FA для пользователя
        """
        redis_client = await self._get_redis()

        key = f"{self.prefix_2fa_enabled}{user_id}"
        data = {
            "user_id": user_id,
            "email": email,
            "enabled": enabled,
            "method": "email",
            "updated_at": datetime.utcnow().isoformat()
        }

        # Пробуем сохранить через StorageManager
        storage_success = await self._storage_manager_store(key, data, 2592000)

        if storage_success:
            logger.info(f"✅ Настройки 2FA сохранены через StorageManager для {email}")
            return

        # Fallback на старую логику
        if redis_client and self.use_redis:
            try:
                # Настройки хранятся постоянно (30 дней)
                await redis_client.setex(
                    key,
                    2592000,  # 30 дней
                    json.dumps(data)
                )
                logger.info(f"✅ Настройки 2FA сохранены в Redis для {email}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка сохранения 2FA настроек в Redis: {e}")
                await self._mock_store(key, data, 2592000)
        else:
            await self._mock_store(key, data, 2592000)
            logger.info(f"✅ Настройки 2FA сохранены в памяти для {email}: enabled={enabled}")

    async def get_2fa_settings(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение настроек 2FA пользователя
        """
        redis_client = await self._get_redis()
        key = f"{self.prefix_2fa_enabled}{user_id}"

        # Сначала пробуем StorageManager
        data = await self._storage_manager_get(key)
        if data:
            return data

        # Пробуем Redis
        if redis_client and self.use_redis:
            try:
                data_json = await redis_client.get(key)
                if data_json:
                    return json.loads(data_json)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка чтения 2FA настроек из Redis: {e}")

        # Пробуем память
        return await self._mock_get(key)

    async def delete_2fa_settings(self, user_id: str):
        """Удаление настроек 2FA"""
        redis_client = await self._get_redis()
        key = f"{self.prefix_2fa_enabled}{user_id}"

        # Удаляем из всех хранилищ
        await self._storage_manager_delete(key)

        if redis_client and self.use_redis:
            try:
                await redis_client.delete(key)
                logger.info(f"✅ Настройки 2FA удалены из Redis для {user_id}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка удаления 2FA настроек из Redis: {e}")

        await self._mock_delete(key)
        logger.info(f"✅ Настройки 2FA удалены из памяти для {user_id}")


# Создаем глобальный экземпляр
verification_service = VerificationService()