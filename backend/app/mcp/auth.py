"""远端 MCP 请求鉴权：所有协议请求使用可撤销集成令牌。"""

from collections.abc import Callable
from urllib.parse import urlsplit

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.integration_tokens import resolve_token


class IntegrationAuthMiddleware:
    def __init__(self, app: Callable):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        # Host/Origin 使用部署时配置的公开域名校验，防止 DNS rebinding 和跨站调用。
        if settings.public_base_url:
            expected = urlsplit(settings.public_base_url).netloc.lower()
            host = headers.get(b"host", b"").decode("ascii", errors="ignore").lower()
            origin = headers.get(b"origin", b"").decode("ascii", errors="ignore")
            if host != expected or (origin and urlsplit(origin).netloc.lower() != expected):
                await send({"type": "http.response.start", "status": 403, "headers": []})
                await send({"type": "http.response.body", "body": b""})
                return
        bearer = headers.get(b"authorization", b"").decode("utf-8", errors="replace")
        authorized = None
        if bearer.startswith("Bearer "):
            with SessionLocal() as db:
                authorized = resolve_token(db, bearer[7:], "images:read")
        if authorized is None:
            body = b'{"error":"unauthorized"}'
            await send({"type": "http.response.start", "status": 401, "headers": [
                (b"content-type", b"application/json"),
                (b"www-authenticate", b"Bearer"),
            ]})
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)
