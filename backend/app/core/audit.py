# app/core/audit.py
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Request

# Специальный логгер для аудита
audit_logger = logging.getLogger("audit")


def log_audit(
        action: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        tenant_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        status: str = "success"
):
    """
    Логирование важных действий (аудит)
    """
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "user_id": user_id,
        "user_email": user_email,
        "tenant_id": tenant_id,
        "status": status,
        "details": details or {}
    }

    if request:
        log_data.update({
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "method": request.method,
            "path": request.url.path
        })

    audit_logger.info(json.dumps(log_data, ensure_ascii=False))