"""Streamable HTTP 图床 MCP 工具。文件上传由 Agent 本地客户端调用 API。"""

from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException
from mcp.server.fastmcp import Context
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.mcp.protocol import ImageMCP
from app.models.image_version import ImageVersion
from app.models.user import User
from app.schemas.image import ImageResponse, ImageVersionResponse
from app.services.integration_images import accessible_image, image_links, image_page
from app.services.integration_tokens import resolve_token

_public_url = urlsplit(settings.public_base_url)
mcp = ImageMCP(
    "图床集成", stateless_http=True, json_response=True,
    streamable_http_path="/",
    instructions="审查本地图片后用本地上传工具调用 API；本服务提供状态和链接查询。",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[_public_url.netloc] if _public_url.netloc else ["localhost", "127.0.0.1"],
        allowed_origins=[f"{_public_url.scheme}://{_public_url.netloc}"]
        if _public_url.netloc else [],
    ),
)

def _actor(db, permission: str, ctx: Context) -> User:
    request = ctx.request_context.request
    if request is None or not hasattr(request, "headers"):
        raise PermissionError("缺少 HTTP 请求身份")
    bearer = request.headers.get("authorization", "")
    if not bearer.startswith("Bearer "):
        raise PermissionError("缺少集成令牌")
    identity = resolve_token(db, bearer[7:], permission)
    if identity is None:
        raise PermissionError(f"令牌失效或缺少 {permission} 权限")
    return identity[0]


def _safe(call):
    try:
        return call()
    except HTTPException as exc:
        return {"error": {"status": exc.status_code, "message": exc.detail}}
    except PermissionError as exc:
        return {"error": {"status": 403, "message": str(exc)}}


@mcp.tool()
def upload_instructions(ctx: Context) -> dict[str, Any]:
    """返回本地上传参数与支持的权限。不要将本地文件路径传给远端 MCP。"""
    def run():
        with SessionLocal() as db:
            _actor(db, "images:read", ctx)
        return {"upload_path": settings.api_prefix.rstrip("/") + "/images/upload",
                "method": "POST",
                "auth": "Authorization: Bearer <集成令牌，需 images:upload 权限>",
                "fields": ["files", "sku", "ratio_width", "ratio_height", "min_short_side_px"],
                "max_file_size_mb": settings.max_upload_size_mb,
                "formats": list(settings.allowed_image_formats),
                "note": "本地上传文件后，使用响应中的 image.id 查询处理状态。"}
    return _safe(run)


@mcp.tool()
def search_images(ctx: Context, sku: str = "", filename: str = "",
                  page: int = 1, page_size: int = 50) -> dict[str, Any]:
    """按货号及文件名查找当前身份可访问的图片，分页返回。"""
    def run():
        if page < 1 or not 1 <= page_size <= 200:
            return {"error": {"status": 422, "message": "分页参数无效"}}
        with SessionLocal() as db:
            return image_page(db, _actor(db, "images:read", ctx), sku, filename, page, page_size)
    return _safe(run)


@mcp.tool()
def get_image(image_id: int, ctx: Context) -> dict[str, Any]:
    """通过上传结果里的图片 ID 查询异步处理状态与错误原因。"""
    def run():
        with SessionLocal() as db:
            image = accessible_image(db, _actor(db, "images:read", ctx), image_id)
            return ImageResponse.model_validate(image).model_dump(mode="json")
    return _safe(run)


@mcp.tool()
def get_image_links(
    image_id: int, ctx: Context, version_number: int | None = None,
) -> dict[str, Any]:
    """取得原图和指定版本链接；省略版本号时返回当前处理版本。链接无需鉴权。"""
    def run():
        if not settings.public_base_url:
            return {"error": {"status": 503, "message": "尚未配置公开访问地址"}}
        with SessionLocal() as db:
            image = accessible_image(db, _actor(db, "images:read", ctx), image_id)
            if version_number is not None and version_number < 1:
                raise HTTPException(status_code=422, detail="版本号必须大于 0")
            return image_links(db, image, settings.public_base_url, version_number)
    return _safe(run)


@mcp.tool()
def list_image_versions(image_id: int, ctx: Context) -> dict[str, Any]:
    """列出图片最近 10 个处理版本。"""
    def run():
        with SessionLocal() as db:
            _ = accessible_image(db, _actor(db, "images:read", ctx), image_id)
            versions = db.scalars(select(ImageVersion).where(ImageVersion.image_id == image_id)
                                  .order_by(ImageVersion.version_number.desc()).limit(10)).all()
            return {"items": [ImageVersionResponse.model_validate(v).model_dump(mode="json")
                              for v in versions]}
    return _safe(run)


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False,
))
def reprocess_image(image_id: int, ratio_width: int, ratio_height: int,
                    min_short_side_px: int, ctx: Context) -> dict[str, Any]:
    """重新处理自己上传的图片；需 images:reprocess 权限。"""
    def run():
        from app.schemas.image import ImageReprocessRequest
        from app.services.image_reprocessing import reprocess
        try:
            payload = ImageReprocessRequest(ratio_width=ratio_width,
                                            ratio_height=ratio_height,
                                            min_short_side_px=min_short_side_px)
        except ValueError:
            return {"error": {"status": 422, "message": "处理参数无效"}}
        with SessionLocal() as db:
            user = _actor(db, "images:reprocess", ctx)
            image = reprocess(db, user, image_id, payload)
            return ImageResponse.model_validate(image).model_dump(mode="json")
    return _safe(run)
