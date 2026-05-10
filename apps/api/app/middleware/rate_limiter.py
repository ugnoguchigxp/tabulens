import time
import asyncio
from typing import Dict, Optional, Callable
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimiter:
    def __init__(self, window_ms: int, limit: int, message: str = "Too many requests"):
        self.window_ms = window_ms
        self.limit = limit
        self.message = message
        self.store: Dict[str, Dict[str, float]] = {}
        
    def _get_client_ip(self, request: Request) -> str:
        # Simple IP detection, respect x-forwarded-for if needed
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "global"

    async def __call__(self, request: Request, call_next: Callable):
        key = self._get_client_ip(request)
        now = time.time() * 1000
        
        if key in self.store:
            record = self.store[key]
            if now > record["reset_time"]:
                self.store[key] = {"count": 1, "reset_time": now + self.window_ms}
            else:
                if record["count"] >= self.limit:
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": {
                                "code": "RATE_LIMIT_EXCEEDED",
                                "message": self.message
                            }
                        }
                    )
                record["count"] += 1
        else:
            self.store[key] = {"count": 1, "reset_time": now + self.window_ms}
            
        return await call_next(request)

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, window_ms: int, limit: int, path_prefix: str = "/api"):
        super().__init__(app)
        self.limiter = RateLimiter(window_ms, limit)
        self.path_prefix = path_prefix

    async def dispatch(self, request: Request, call_next: Callable):
        if not request.url.path.startswith(self.path_prefix):
            return await call_next(request)
            
        return await self.limiter(request, call_next)
