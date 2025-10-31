# backend/app/middleware/request_logger.py
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.logger import get_logger

log = get_logger(__name__)

class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            ms = int((time.perf_counter() - start) * 1000)
            status = getattr(response, "status_code", "-")
            log.info("%s %s -> %s %dms", request.method, request.url.path, status, ms)