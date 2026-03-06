#backend/app/core/ratelimit/security.py
from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
from collections import defaultdict
import asyncio
import json
from typing import Dict

from app.core.config import settings


class DDoSProtectionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts: Dict[str, list] = defaultdict(list)
        self.blocked_ips: Dict[str, float] = {}
        self.lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        now = time.time()

        if client_ip in self.blocked_ips:
            if now - self.blocked_ips[client_ip] < 3600:
                return Response(
                    content=json.dumps({"error": "IP заблокирован за подозрительную активность"}),
                    status_code=403,
                    media_type="application/json"
                )
            else:
                del self.blocked_ips[client_ip]

        async with self.lock:
            self.request_counts[client_ip] = [
                t for t in self.request_counts[client_ip]
                if t > now - 60
            ]

            if len(self.request_counts[client_ip]) >= self.requests_per_minute:
                self.blocked_ips[client_ip] = now
                return Response(
                    content=json.dumps({"error": "Слишком много запросов. IP заблокирован на час."}),
                    status_code=429,
                    media_type="application/json"
                )

            self.request_counts[client_ip].append(now)

        user_agent = request.headers.get("user-agent", "")
        if not user_agent or len(user_agent) < 10:
            return Response(
                content=json.dumps({"error": "Invalid request"}),
                status_code=400,
                media_type="application/json"
            )

        content_length = request.headers.get("content-length", 0)
        try:
            if int(content_length) > 10_000_000:
                return Response(
                    content=json.dumps({"error": "Request too large"}),
                    status_code=413,
                    media_type="application/json"
                )
        except:
            pass

        response = await call_next(request)
        return response