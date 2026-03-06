# app/core/storage.py
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import redis.asyncio as redis  # Меняем aioredis на redis.asyncio
from redis.exceptions import ConnectionError as RedisConnectionError
import asyncio
from collections import defaultdict
import time
import os
import glob

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageBackend:
    """Абстрактный класс для хранилища"""

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    async def set(self, key: str, value: Dict[str, Any], ttl: int) -> bool:
        raise NotImplementedError

    async def delete(self, key: str) -> bool:
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        raise NotImplementedError


class RedisStorage(StorageBackend):
    """Хранилище на Redis"""

    def __init__(self, url: str):
        self.url = url
        self.client = None
        self.connected = False

    async def connect(self) -> bool:
        """Подключение к Redis"""
        try:
            self.client = await redis.from_url(
                self.url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=True,
                health_check_interval=30
            )
            # Проверяем подключение
            await self.client.ping()
            self.connected = True
            logger.info("✅ RedisStorage: подключение установлено")
            return True
        except Exception as e:
            logger.warning(f"⚠️ RedisStorage: ошибка подключения: {e}")
            self.connected = False
            return False

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        if not self.connected:
            return None
        try:
            data = await self.client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"RedisStorage.get error: {e}")
            return None

    async def set(self, key: str, value: Dict[str, Any], ttl: int) -> bool:
        if not self.connected:
            return False
        try:
            await self.client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"RedisStorage.set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        if not self.connected:
            return False
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"RedisStorage.delete error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        if not self.connected:
            return False
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"RedisStorage.exists error: {e}")
            return False


class FileStorage(StorageBackend):
    """Файловое хранилище (персистентное, не теряется при рестарте)"""

    def __init__(self, base_path: str = "./data"):
        self.base_path = base_path
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.expiry: Dict[str, float] = {}
        self._ensure_directory()
        self._load_from_disk()
        logger.info(f"📁 FileStorage: инициализирован в {base_path}")

    def _ensure_directory(self):
        """Создает директорию для хранения файлов"""
        os.makedirs(self.base_path, exist_ok=True)

    def _get_file_path(self, key: str) -> str:
        """Возвращает путь к файлу для ключа"""
        # Экранируем недопустимые символы для имени файла
        safe_key = key.replace('/', '_').replace(':', '_').replace('\\', '_')
        return os.path.join(self.base_path, f"{safe_key}.json")

    def _load_from_disk(self):
        """Загружает все файлы из директории"""
        try:
            files = glob.glob(os.path.join(self.base_path, "*.json"))
            now = time.time()

            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Проверяем не истек ли
                    if '_expire' in data and data['_expire'] < now:
                        os.remove(file_path)
                        continue

                    # Извлекаем ключ из имени файла
                    key = os.path.basename(file_path).replace('.json', '')
                    key = key.replace('_', ':', 1)  # Восстанавливаем первый разделитель

                    self.cache[key] = data
                    self.expiry[key] = data.get('_expire', now + 3600)

                except Exception as e:
                    logger.error(f"Ошибка загрузки файла {file_path}: {e}")

            logger.info(f"📁 FileStorage: загружено {len(self.cache)} записей")

        except Exception as e:
            logger.error(f"Ошибка загрузки данных из файлов: {e}")

    def _save_to_disk(self, key: str, data: Dict[str, Any]):
        """Сохраняет данные в файл"""
        try:
            file_path = self._get_file_path(key)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения файла {key}: {e}")

    def _delete_from_disk(self, key: str):
        """Удаляет файл с диска"""
        try:
            file_path = self._get_file_path(key)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Ошибка удаления файла {key}: {e}")

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        # Проверяем кэш
        data = self.cache.get(key)
        if not data:
            return None

        # Проверяем не истек ли
        now = time.time()
        if '_expire' in data and data['_expire'] < now:
            await self.delete(key)
            return None

        # Возвращаем копию без служебных полей
        return {k: v for k, v in data.items() if not k.startswith('_')}

    async def set(self, key: str, value: Dict[str, Any], ttl: int) -> bool:
        now = time.time()
        expire = now + ttl

        # Добавляем служебные поля
        data = value.copy()
        data['_expire'] = expire
        data['_created'] = now

        # Сохраняем в кэш
        self.cache[key] = data
        self.expiry[key] = expire

        # Сохраняем на диск
        self._save_to_disk(key, data)

        return True

    async def delete(self, key: str) -> bool:
        if key in self.cache:
            del self.cache[key]
        if key in self.expiry:
            del self.expiry[key]

        # Удаляем с диска
        self._delete_from_disk(key)

        return True

    async def exists(self, key: str) -> bool:
        if key not in self.cache:
            return False

        # Проверяем не истек ли
        now = time.time()
        if key in self.expiry and self.expiry[key] < now:
            await self.delete(key)
            return False

        return True

    async def cleanup(self):
        """Очищает истекшие записи"""
        now = time.time()
        expired = [k for k, v in self.expiry.items() if v < now]

        for key in expired:
            await self.delete(key)

        if expired:
            logger.info(f"🧹 FileStorage: очищено {len(expired)} истекших записей")


class MemoryStorage(StorageBackend):
    """Хранилище в памяти (только для разработки, данные теряются при рестарте)"""

    def __init__(self):
        self.storage: Dict[str, Dict[str, Any]] = {}
        self.expiry: Dict[str, float] = {}
        logger.warning("⚠️ MemoryStorage: данные будут потеряны при перезапуске!")

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        data = self.storage.get(key)
        if not data:
            return None

        # Проверяем не истек ли
        if key in self.expiry and self.expiry[key] < time.time():
            await self.delete(key)
            return None

        return data

    async def set(self, key: str, value: Dict[str, Any], ttl: int) -> bool:
        self.storage[key] = value
        self.expiry[key] = time.time() + ttl
        return True

    async def delete(self, key: str) -> bool:
        if key in self.storage:
            del self.storage[key]
        if key in self.expiry:
            del self.expiry[key]
        return True

    async def exists(self, key: str) -> bool:
        if key not in self.storage:
            return False
        if key in self.expiry and self.expiry[key] < time.time():
            await self.delete(key)
            return False
        return True


class StorageManager:
    """Менеджер хранилищ с автоматическим переключением"""

    def __init__(self):
        self.storages: List[StorageBackend] = []
        self.primary_storage: Optional[StorageBackend] = None
        self.backup_storage: Optional[StorageBackend] = None
        self._init_storages()

    def _init_storages(self):
        """Инициализирует все доступные хранилища"""

        # 1. Пытаемся подключиться к Redis
        if settings.REDIS_URL:
            redis_storage = RedisStorage(settings.REDIS_URL)
            self.storages.append(redis_storage)

        # 2. Файловое хранилище (всегда доступно)
        file_storage = FileStorage()
        self.storages.append(file_storage)

        # 3. Memory как последнее средство
        memory_storage = MemoryStorage()
        self.storages.append(memory_storage)

        # Запускаем выбор основного хранилища
        asyncio.create_task(self._select_primary())

    async def _select_primary(self):
        """Выбирает основное хранилище (Redis если доступен, иначе файловое)"""
        for storage in self.storages:
            if isinstance(storage, RedisStorage):
                if await storage.connect():
                    self.primary_storage = storage
                    self.backup_storage = self.storages[1]  # FileStorage
                    logger.info("✅ StorageManager: основное хранилище - Redis, резерв - FileStorage")
                    return
            elif isinstance(storage, FileStorage):
                self.primary_storage = storage
                self.backup_storage = self.storages[2]  # MemoryStorage
                logger.info("📁 StorageManager: основное хранилище - FileStorage, резерв - Memory")
                return

        # Если ничего не сработало (такого не должно быть)
        self.primary_storage = self.storages[-1]  # MemoryStorage
        self.backup_storage = None
        logger.error("❌ StorageManager: только MemoryStorage доступно!")

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Пытается получить данные сначала из основного хранилища, потом из резервного"""
        if self.primary_storage:
            data = await self.primary_storage.get(key)
            if data is not None:
                return data

        if self.backup_storage:
            data = await self.backup_storage.get(key)
            if data is not None:
                # Восстанавливаем данные в основном хранилище если нашли в резервном
                if self.primary_storage and '_expire' in data:
                    ttl = int(data['_expire'] - time.time())
                    if ttl > 0:
                        await self.primary_storage.set(key, data, ttl)
                return data

        return None

    async def set(self, key: str, value: Dict[str, Any], ttl: int) -> bool:
        """Сохраняет данные во все доступные хранилища"""
        success = False

        # Сохраняем в основное
        if self.primary_storage:
            if await self.primary_storage.set(key, value, ttl):
                success = True

        # Сохраняем в резервное
        if self.backup_storage:
            if await self.backup_storage.set(key, value, ttl):
                success = True

        return success

    async def delete(self, key: str) -> bool:
        """Удаляет данные из всех хранилищ"""
        success = False

        if self.primary_storage:
            if await self.primary_storage.delete(key):
                success = True

        if self.backup_storage:
            if await self.backup_storage.delete(key):
                success = True

        return success

    async def exists(self, key: str) -> bool:
        """Проверяет существование ключа"""
        if self.primary_storage and await self.primary_storage.exists(key):
            return True
        if self.backup_storage and await self.backup_storage.exists(key):
            return True
        return False


# Создаем глобальный экземпляр менеджера хранилищ
storage_manager = StorageManager()