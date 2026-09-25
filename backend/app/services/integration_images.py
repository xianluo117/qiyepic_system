"""MCP 与 API 共同使用的图片访问与结果描述。"""

from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.image import Image
from app.models.image_version import ImageVersion
from app.models.user import User, UserRole
from app.schemas.image import ImageResponse, ImageVersionResponse
from app.services.image_queries import apply_image_access_scope


def accessible_image(db: Session, user: User, image_id: int) -> Image:
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    if user.role != UserRole.ADMIN and image.owner_id != user.id:
        if user.role != UserRole.SUPERVISOR or image.owner.supervisor_id != user.id:
            raise HTTPException(status_code=403, detail="无权访问该图片")
    return image


def image_page(db: Session, user: User, sku: str | None, filename: str | None,
               page: int, page_size: int) -> dict:
    from sqlalchemy import func

    query = apply_image_access_scope(select(Image), user, None)
    if sku:
        query = query.where(Image.sku == sku.strip())
    if filename:
        query = query.where(Image.original_filename.contains(filename.strip()))
    total = db.scalar(query.with_only_columns(func.count(Image.id)).order_by(None)) or 0
    images = db.scalars(query.order_by(Image.created_at.desc(), Image.id.desc())
                        .offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [ImageResponse.model_validate(image).model_dump(mode="json") for image in images],
        "total": total, "page": page, "page_size": page_size,
    }


def image_links(
    db: Session, image: Image, base_url: str, version_number: int | None = None,
) -> dict[str, str | None]:
    prefix = base_url.rstrip("/") + settings.api_prefix.rstrip("/") + "/public/images"
    slug = "/".join(quote(value, safe="") for value in (
        image.employee_id, image.sku, Path(image.original_filename).stem,
    ))
    result: dict[str, str | None] = {
        "thumbnail": f"{prefix}/{image.id}/thumbnail",
        "original": f"{prefix}/{image.id}/{slug}/original",
        "processed": None,
    }
    selected_version = (
        version_number if version_number is not None else image.current_version_number
    )
    if selected_version is not None:
        version = db.scalar(select(ImageVersion).where(
            ImageVersion.image_id == image.id,
            ImageVersion.version_number == selected_version,
        ))
        if version is None:
            raise HTTPException(status_code=404, detail="处理版本不存在")
        revision = ImageVersionResponse.model_validate(version).revision
        result["processed"] = f"{prefix}/{image.id}/{slug}/processed?rev={revision}"
    return result
