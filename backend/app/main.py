from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import time
import logging
import asyncio
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from app.core.config import settings
from app.core.security import limiter
from app.database import engine, Base, AsyncSessionLocal as async_session
from app.api import api_router
from app.middleware.security import DDoSProtectionMiddleware
from app.core.cleanup import run_cleanup_periodically

# 🔥 НОВЫЕ ИМПОРТЫ ДЛЯ ЛОГИРОВАНИЯ
from app.core.logging_config import setup_logging
from app.middleware.logging import RequestLoggingMiddleware
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 🔥 НАСТРАИВАЕМ ЛОГИРОВАНИЕ В САМОМ НАЧАЛЕ
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК AI CHAT SERVICE")
    logger.info("=" * 50)
    logger.info(f"🌍 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🐛 Debug mode: {settings.DEBUG}")
    logger.info(f"🤖 AI Provider: {settings.AI_PROVIDER}")
    logger.info(f"📁 Logs directory: ./logs")

    # Запускаем фоновую задачу для очистки временных сессий
    cleanup_task = asyncio.create_task(run_cleanup_periodically())
    logger.info("🧹 Фоновая задача очистки временных сессий запущена")

    # Проверяем rate limiter для production
    if settings.ENVIRONMENT == "production":
        from app.core.ratelimit import widget_limiter
        if hasattr(widget_limiter, '__class__') and 'Memory' in widget_limiter.__class__.__name__:
            logger.warning(
                "⚠️ ВНИМАНИЕ: В production режиме используется MemoryRateLimiter!\n"
                "   Установите и настройте Redis для сохранения лимитов между рестартами."
            )

    # Создаем таблицы в БД (только для разработки)
    if settings.DEBUG:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created")
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise

    yield

    # Shutdown
    logger.info("=" * 50)
    logger.info("🛑 ОСТАНОВКА AI CHAT SERVICE")
    logger.info("=" * 50)
    cleanup_task.cancel()
    try:
        await cleanup_task
        logger.info("🧹 Фоновая задача очистки остановлена")
    except asyncio.CancelledError:
        logger.info("🧹 Фоновая задача очистки отменена")
    await engine.dispose()
    logger.info("✅ Соединения с БД закрыты")


# Функция для проверки домена виджета
def is_widget_domain_allowed(domain: str) -> bool:
    """
    Проверяет, разрешен ли домен для встраивания виджета
    """
    if settings.DEBUG:
        return True

    if "*" in settings.WIDGET_ALLOWED_DOMAINS:
        logger.warning(f"⚠️ Виджет загружен с домена {domain} (разрешены все домены)")
        return True

    for allowed_domain in settings.WIDGET_ALLOWED_DOMAINS:
        if domain == allowed_domain or domain.endswith(f".{allowed_domain}"):
            return True

    logger.warning(f"❌ Заблокирована загрузка виджета с домена {domain}")
    return False


# Middleware для проверки домена виджета
async def widget_domain_middleware(request: Request, call_next):
    """
    Middleware для проверки доменов, с которых загружается виджет
    """
    if request.url.path.startswith(f"{settings.API_V1_STR}/widget/"):
        referer = request.headers.get("referer")

        if request.url.path.endswith("/widget.js"):
            if referer:
                try:
                    parsed = urlparse(referer)
                    domain = parsed.netloc or parsed.path.split('/')[0]
                    if not is_widget_domain_allowed(domain):
                        logger.warning(f"❌ Заблокирована загрузка виджета с домена {domain}")
                        return JSONResponse(
                            status_code=403,
                            content={"error": "Domain not allowed"}
                        )
                except Exception as e:
                    logger.error(f"Ошибка при парсинге referer: {e}")
            else:
                logger.warning(f"❌ Запрос виджета без Referer: {request.client.host}")
                return JSONResponse(
                    status_code=403,
                    content={"error": "Referer header required"}
                )

    response = await call_next(request)
    return response


# Создаем приложение
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Настройка CORS
cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "null",
    "file://",
]

if settings.BACKEND_CORS_ORIGINS:
    for origin in settings.BACKEND_CORS_ORIGINS:
        if origin not in cors_origins:
            cors_origins.append(origin)

if settings.DEBUG:
    cors_origins.extend([
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:3001",
        "http://localhost:5000",
        "*",
    ])

logger.info(f"🔧 CORS разрешены origins: {cors_origins}")

# Добавляем middleware в правильном порядке
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# 🔥 НОВЫЙ MIDDLEWARE ДЛЯ ЛОГИРОВАНИЯ ЗАПРОСОВ (ставить ПОСЛЕ CORS)
app.add_middleware(RequestLoggingMiddleware)

if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )

app.middleware("http")(widget_domain_middleware)

if not settings.DEBUG:
    app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(DDoSProtectionMiddleware, requests_per_minute=settings.MAX_REQUESTS_BEFORE_BLOCK)

# Rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Обработчики ошибок
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "path": request.url.path,
            "method": request.method,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "message": "Ошибка валидации данных",
            "details": exc.errors(),
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"💥 Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Внутренняя ошибка сервера" if not settings.DEBUG else str(exc),
            "detail": str(exc) if settings.DEBUG else None,
            "path": request.url.path,
        },
    )


# Подключаем API роутеры
app.include_router(api_router, prefix=settings.API_V1_STR)


# Health checks
@app.get("/", include_in_schema=False)
async def root():
    logger.debug("Root endpoint accessed")
    return {
        "message": f"{settings.PROJECT_NAME} API",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs" if settings.DEBUG else None,
        "status": "operational",
        "cors_origins": cors_origins,
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint для мониторинга"""
    from sqlalchemy import text

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))

        # Проверяем, что логи работают
        log_dir = os.path.exists("logs")

        return {
            "status": "healthy",
            "database": "connected",
            "logging": "active" if log_dir else "warning",
            "timestamp": time.time(),
            "environment": settings.ENVIRONMENT,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e) if settings.DEBUG else "Database connection failed",
            },
        )


# Тестовый endpoint для проверки CORS
if settings.DEBUG:
    @app.get("/test-cors", tags=["debug"])
    async def test_cors(request: Request):
        """Тест CORS настроек"""
        logger.info(f"Test CORS accessed from {request.client.host}")
        return {
            "message": "CORS is working!",
            "your_origin": request.headers.get("origin", "none"),
            "allowed_origins": cors_origins,
            "headers": dict(request.headers),
        }


    @app.options("/test-cors", tags=["debug"])
    async def test_cors_preflight():
        """Preflight запрос для теста CORS"""
        return JSONResponse(
            content={"message": "OK"},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )