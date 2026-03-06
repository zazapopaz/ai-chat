# app/core/config.py
from pydantic_settings import BaseSettings
from typing import Optional, List, Union
from pydantic import field_validator, ConfigDict, ValidationInfo
import secrets
import warnings


class Settings(BaseSettings):
    # Базовые настройки
    PROJECT_NAME: str = "AI Chat Service"
    API_V1_STR: str = "/api/v1"
    VERSION: str = "1.0.0"

    # Режим разработки
    DEBUG: bool = True
    ENVIRONMENT: str = "development"  # development, staging, production

    # Настройки сервера
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS настройки - ВАЖНО: для разработки разрешаем все
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Преобразуем строку из .env в список"""
        if isinstance(v, str):
            # Убираем кавычки если есть
            v = v.strip('"').strip("'")
            # Пробуем распарсить как JSON
            if v.startswith('[') and v.endswith(']'):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # Иначе разбиваем по запятой
            return [i.strip().strip('"').strip("'") for i in v.split(",") if i.strip()]
        return v

    @field_validator("BACKEND_CORS_ORIGINS", mode="after")
    @classmethod
    def validate_cors_origins(cls, v: List[str], info: ValidationInfo) -> List[str]:
        """
        В production/staging запрещаем '*' в списке CORS‑доменов,
        чтобы избежать открытого доступа с любых сайтов.
        """
        env = info.data.get("ENVIRONMENT", "development")
        if env != "development" and "*" in v:
            raise ValueError(
                f"BACKEND_CORS_ORIGINS содержит '*' для окружения {env}. "
                f"В production/staging укажите конкретные домены (например, https://example.com)."
            )
        return v

    # База данных
    DATABASE_URL: str = "sqlite+aiosqlite:///./chat_service.db"

    # JWT - безопасность
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"  # Значение по умолчанию, будет заменено из .env

    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def validate_secret_key(cls, v: str, info: ValidationInfo) -> str:
        """Проверяем, что используется ключ из .env, а не дефолтный"""
        env = info.data.get("ENVIRONMENT", "development")

        # Если ключ все еще равен дефолтному значению
        if v == "CHANGE_ME_IN_PRODUCTION":
            if env == "production":
                raise ValueError(
                    f"В {env} окружении SECRET_KEY должен быть уникальным и надежным! "
                    f"Укажите SECRET_KEY в .env файле"
                )
            else:
                # В development генерируем временный ключ для удобства
                warnings.warn(
                    "⚠️ ВНИМАНИЕ: Используется временный SECRET_KEY, сгенерированный автоматически. "
                    "Для продакшена укажите свой SECRET_KEY в .env файле",
                    RuntimeWarning
                )
                return secrets.token_urlsafe(32)

        # Проверяем длину ключа (для безопасности)
        if len(v) < 32:
            warnings.warn(
                f"⚠️ SECRET_KEY слишком короткий ({len(v)} символов). "
                f"Рекомендуется использовать ключ длиной не менее 32 символов.",
                RuntimeWarning
            )

        # Если ключ пришел из .env и он не дефолтный - используем его
        return v

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 дней

    # Безопасность
    SECURITY_BCRYPT_ROUNDS: int = 12
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]
    RATE_LIMIT_PER_MINUTE: int = 60

    # Yandex GPT - обязательные поля
    YANDEX_API_KEY: Optional[str] = None
    YANDEX_FOLDER_ID: Optional[str] = None

    @field_validator("YANDEX_API_KEY", mode="after")
    @classmethod
    def validate_yandex_api_key(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Проверяем наличие API ключа в production"""
        env = info.data.get("ENVIRONMENT", "development")
        ai_provider = info.data.get("AI_PROVIDER", "yandexgpt")

        if env != "development" and ai_provider == "yandexgpt" and not v:
            raise ValueError(
                "YANDEX_API_KEY обязателен для production при использовании Yandex GPT! "
                "Получите ключ на https://console.cloud.yandex.ru"
            )

        if v and len(v) > 8:
            # Маскируем для логов
            masked = v[:4] + "..." + v[-4:]
            print(f"✅ Yandex API ключ загружен: {masked}")
        elif not v:
            print("⚠️ Yandex API ключ не указан, AI функции будут недоступны")

        return v

    @field_validator("YANDEX_FOLDER_ID", mode="after")
    @classmethod
    def validate_yandex_folder_id(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Проверяем наличие folder_id в production"""
        env = info.data.get("ENVIRONMENT", "development")
        ai_provider = info.data.get("AI_PROVIDER", "yandexgpt")

        if env != "development" and ai_provider == "yandexgpt" and not v:
            raise ValueError(
                "YANDEX_FOLDER_ID обязателен для production при использовании Yandex GPT!"
            )
        return v

    AI_PROVIDER: str = "yandexgpt"
    YANDEX_MODEL: str = "yandexgpt-lite"

    # Логирование
    LOG_LEVEL: str = "INFO"

    # Redis (для rate limiting, кэша и 2FA)
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"

    # Настройки виджета
    WIDGET_DEFAULT_TYPING_DELAY: int = 1000
    WIDGET_DEFAULT_RESPONSE_DELAY: int = 500
    WIDGET_MAX_MESSAGES_PER_SESSION: int = 50

    # Безопасность виджета - ограничиваем домены
    WIDGET_ALLOWED_DOMAINS: List[str] = ["*"]  # По умолчанию все, но ТОЛЬКО для разработки

    @field_validator("WIDGET_ALLOWED_DOMAINS", mode="after")
    @classmethod
    def validate_widget_domains(cls, v: List[str], info: ValidationInfo) -> List[str]:
        """
        В production/staging запрещаем '*' для доменов виджета.
        Виджет должен быть явно ограничен списком доверенных сайтов.
        """
        env = info.data.get("ENVIRONMENT", "development")
        if env != "development" and "*" in v:
            raise ValueError(
                f"WIDGET_ALLOWED_DOMAINS содержит '*' для окружения {env}. "
                f"Укажите конкретные домены, на которых разрешено встраивать виджет."
            )
        return v

    # === НОВЫЕ НАСТРОЙКИ ДЛЯ ВАЛИДАЦИИ И ЗАЩИТЫ ===

    # Rate limiting для разных эндпоинтов
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_WIDGET_MESSAGES: int = 10
    RATE_LIMIT_WIDGET_STARTS: int = 5
    RATE_LIMIT_CONTACT_SAVES: int = 3

    # Лимиты на длину данных
    MAX_MESSAGE_LENGTH: int = 2000
    MAX_NAME_LENGTH: int = 100
    MAX_PHONE_LENGTH: int = 20
    MAX_EMAIL_LENGTH: int = 100

    # Минимальные длины
    MIN_MESSAGE_LENGTH: int = 1
    MIN_PHONE_LENGTH: int = 5
    MIN_NAME_LENGTH: int = 2

    # Защита от флуда
    MAX_SESSIONS_PER_IP_PER_HOUR: int = 30
    MAX_SESSIONS_PER_TENANT_PER_DAY: int = 500
    MAX_MESSAGES_PER_SESSION: int = 12

    # Таймауты
    SESSION_TIMEOUT_MINUTES: int = 30
    INACTIVITY_SHUTDOWN_MINUTES: int = 3

    # Блокировка по IP
    IP_BLOCK_DURATION_HOURS: int = 1
    MAX_REQUESTS_BEFORE_BLOCK: int = 100

    # Спам-фильтры
    SPAM_PATTERNS: List[str] = [
        r'(.)\1{10,}',
        r'https?://(bit\.ly|goo\.gl|tinyurl|is\.gd|clck\.ru)',
    ]

    SPAM_WORDS: List[str] = [
        "спам", "рассылка", "casino", "viagra", "click here",
        "buy now", "заработок", "разбогатей", "кредит"
    ]

    # Временные email домены
    TEMP_EMAIL_DOMAINS: List[str] = [
        "temp-mail.org", "guerrillamail.com", "10minutemail.com",
        "mailinator.com", "yopmail.com", "throwawaymail.com",
        "tempmail.com", "tempemail.net", "fakeinbox.com"
    ]

    # User-Agent проверка
    MIN_USER_AGENT_LENGTH: int = 10

    # Размер запроса
    MAX_REQUEST_SIZE_MB: int = 10

    # Допустимые символы в имени
    ALLOWED_NAME_CHARS: str = r"[^a-zA-Zа-яА-Я\s\-]"

    # === НОВЫЕ НАСТРОЙКИ ДЛЯ EMAIL И 2FA ===

    # Email настройки для отправки писем
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    FROM_EMAIL: str = "noreply@agelar.ru"

    @field_validator("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", mode="after")
    @classmethod
    def validate_smtp_settings(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Проверяем наличие SMTP настроек в production"""
        env = info.data.get("ENVIRONMENT", "development")

        if env == "production" and v is None:
            field_name = info.field_name
            raise ValueError(
                f"{field_name} обязателен для production при использовании email рассылки! "
                f"Настройте SMTP для отправки писем."
            )
        return v

    # 2FA настройки
    TWO_FACTOR_ENABLED: bool = True
    TWO_FACTOR_CODE_EXPIRE_MINUTES: int = 10
    TWO_FACTOR_MAX_ATTEMPTS: int = 5

    # Верификация email
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 15
    VERIFICATION_MAX_ATTEMPTS: int = 5

    # Защита от перебора паролей (НОВОЕ!)
    MAX_LOGIN_ATTEMPTS: int = 5  # Максимум попыток входа
    LOGIN_BLOCK_MINUTES: int = 15  # Блокировка на 15 минут

    @field_validator("MAX_MESSAGE_LENGTH")
    @classmethod
    def validate_max_message_length(cls, v: int) -> int:
        """Проверяем разумность лимита сообщений"""
        if v < 1:
            raise ValueError("MAX_MESSAGE_LENGTH должен быть больше 0")
        if v > 10000:
            warnings.warn(
                f"MAX_MESSAGE_LENGTH = {v} слишком большой. Рекомендуется не больше 2000",
                RuntimeWarning
            )
        return v

    @field_validator("RATE_LIMIT_WIDGET_MESSAGES")
    @classmethod
    def validate_message_rate(cls, v: int) -> int:
        """Проверяем разумность rate limit для сообщений"""
        if v < 1:
            raise ValueError("RATE_LIMIT_WIDGET_MESSAGES должен быть больше 0")
        if v > 100:
            warnings.warn(
                f"RATE_LIMIT_WIDGET_MESSAGES = {v} слишком большой. Это может привести к спаму",
                RuntimeWarning
            )
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Игнорируем лишние переменные


# Создаем экземпляр настроек
settings = Settings()

# Логируем режим работы
print(f" Запуск в режиме: {settings.ENVIRONMENT}")
print(f" AI провайдер: {settings.AI_PROVIDER}")

# Проверяем SECRET_KEY (безопасно логируем)
if settings.SECRET_KEY:
    key_preview = settings.SECRET_KEY[:8] + "..." if len(settings.SECRET_KEY) > 8 else "***"
    print(f" SECRET_KEY загружен: {key_preview}")

    # Проверяем, не используется ли автоматически сгенерированный ключ
    if len(settings.SECRET_KEY) > 40:  # token_urlsafe(32) дает ~43 символа
        print("⚠️ Используется автоматически сгенерированный SECRET_KEY (для разработки)")

if settings.DEBUG:
    print(f" Режим отладки ВКЛЮЧЕН")
    print(f" Rate limit (общий): {settings.RATE_LIMIT_REQUESTS_PER_MINUTE}/min")
    print(f" Rate limit (сообщения): {settings.RATE_LIMIT_WIDGET_MESSAGES}/min")
    print(f" Макс. длина сообщения: {settings.MAX_MESSAGE_LENGTH}")
    print(f" Блокировка IP: {settings.IP_BLOCK_DURATION_HOURS}ч при {settings.MAX_REQUESTS_BEFORE_BLOCK} запросах")

# Логируем настройки email (маскируя пароль)
if settings.SMTP_HOST and settings.SMTP_USER:
    masked_password = "***" if settings.SMTP_PASSWORD else "не указан"
    print(f"SMTP настроен: {settings.SMTP_HOST}:{settings.SMTP_PORT} ({settings.SMTP_USER})")
else:
    print(f"SMTP не настроен. Email рассылка будет в режиме отладки.")

# Логируем статус 2FA
print(f"2FA: {'включена' if settings.TWO_FACTOR_ENABLED else 'выключена'}")
print(
    f"Защита от перебора паролей: {settings.MAX_LOGIN_ATTEMPTS} попыток, блокировка {settings.LOGIN_BLOCK_MINUTES} мин")