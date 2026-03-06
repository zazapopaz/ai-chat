# app/middleware/logging.py
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Логирует все HTTP запросы
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Логируем входящий запрос
        logger.info(f"→ {request.method} {request.url.path} - Client: {request.client.host}")

        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000

            # Логируем ответ
            log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
            logger.log(
                log_level,
                f"← {request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Time: {process_time:.2f}ms"
            )

            # Добавляем заголовок с временем ответа
            response.headers["X-Process-Time"] = str(process_time)

            return response

        except Exception as e:
            logger.exception(f"❌ {request.method} {request.url.path} - Error: {str(e)}")
            raise