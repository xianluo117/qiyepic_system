from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.image import Image
from app.models.image_version import ImageVersion
from app.processing.paths import get_processed_filename
from app.services.thumbnail_service import ThumbnailService
from app.services.version_revision import revision_to_version_number
from app.storage.local import LocalStorage

router = APIRouter()
_storage = LocalStorage(settings.image_root)
_thumbnails = ThumbnailService(settings.image_root)
_IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
_NO_CACHE = "no-store, no-cache, must-revalidate, max-age=0"


def _validate_descriptive_path(
    image: Image,
    employee_id: str,
    sku: str,
    filename: str,
) -> None:
    if (
        image.employee_id != employee_id
        or image.sku != sku
        or Path(image.original_filename).stem != filename
    ):
        raise HTTPException(status_code=404, detail="公开图片不存在或链接已失效")


def _file_response(
    key: str,
    media_type: str,
    filename: str,
    cache_control: str,
) -> FileResponse:
    path = _storage.get_local_path(key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在")
    return FileResponse(
        path=path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
        headers={"Cache-Control": cache_control},
    )


@router.get("/images/{image_id}/thumbnail")
def read_public_thumbnail(
    image_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="公开图片不存在或链接已失效")

    source_path = _storage.get_local_path(image.original_path)
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在")

    thumbnail_path = _thumbnails.get_or_create(image.id, source_path)
    return FileResponse(
        path=thumbnail_path,
        media_type="image/jpeg",
        content_disposition_type="inline",
        headers={"Cache-Control": _IMMUTABLE_CACHE},
    )


def _resolve_version_number(
    revision: str | None,
    legacy_version_number: int | None,
) -> int | None:
    if revision is not None and legacy_version_number is not None:
        raise HTTPException(status_code=400, detail="修订标识 rev 与旧版本参数 v 不能同时使用")
    if revision is None:
        return legacy_version_number
    try:
        return revision_to_version_number(revision)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/images/{image_id}/{employee_id}/{sku}/{filename}/{kind}")
def read_versioned_public_image(
    image_id: int,
    employee_id: str,
    sku: str,
    filename: str,
    kind: str,
    revision: str | None = Query(default=None, alias="rev"),
    legacy_version_number: int | None = Query(default=None, alias="v", ge=1),
    db: Session = Depends(get_db),
) -> FileResponse:
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="公开图片不存在或链接已失效")
    _validate_descriptive_path(image, employee_id, sku, filename)

    if kind == "original":
        return _file_response(
            image.original_path,
            image.content_type,
            image.original_filename,
            _IMMUTABLE_CACHE,
        )
    if kind != "processed":
        raise HTTPException(status_code=400, detail="图片类型必须是 original 或 processed")
    version_number = _resolve_version_number(revision, legacy_version_number)
    if version_number is None:
        raise HTTPException(status_code=422, detail="处理图链接必须包含修订参数 rev")

    version = db.scalar(
        select(ImageVersion).where(
            ImageVersion.image_id == image.id,
            ImageVersion.version_number == version_number,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="处理版本不存在或链接已失效")
    return _file_response(
        version.processed_path,
        "image/jpeg",
        get_processed_filename(image.original_filename),
        _IMMUTABLE_CACHE,
    )


@router.get("/images/{employee_id}/{sku}/{filename}/{kind}")
def read_legacy_public_image(
    employee_id: str,
    sku: str,
    filename: str,
    kind: str,
    revision: str | None = Query(default=None, alias="rev"),
    legacy_version_number: int | None = Query(default=None, alias="v", ge=1),
    db: Session = Depends(get_db),
) -> FileResponse:
    candidates = db.scalars(
        select(Image).where(
            Image.employee_id == employee_id,
            Image.sku == sku,
        )
    ).all()
    matches = [
        image
        for image in candidates
        if Path(image.original_filename).stem == filename
    ]
    if not matches:
        raise HTTPException(status_code=404, detail="公开图片不存在或链接已失效")
    if len(matches) > 1:
        raise HTTPException(status_code=409, detail="存在多个同名但扩展名不同的图片")
    image = matches[0]

    # 无 ID 的描述路径是表格批量递归编辑所需的正式业务 URL。
    # 只有纯字母 rev 能唯一指向不可变版本，因此可安全使用长期缓存；旧 v 链接继续禁用缓存。
    cache_control = _NO_CACHE
    if kind == "original":
        key = image.original_path
        media_type = image.content_type
        filename_for_response = image.original_filename
    elif kind == "processed":
        version_number = _resolve_version_number(revision, legacy_version_number)
        if version_number is not None:
            version = db.scalar(
                select(ImageVersion).where(
                    ImageVersion.image_id == image.id,
                    ImageVersion.version_number == version_number,
                )
            )
            if version is None:
                raise HTTPException(
                    status_code=404,
                    detail="处理版本不存在或链接已失效",
                )
            key = version.processed_path
            if revision is not None:
                cache_control = _IMMUTABLE_CACHE
        else:
            if image.current_version_number is not None:
                raise HTTPException(
                    status_code=422,
                    detail="处理图链接必须包含修订参数 rev",
                )
            key = image.processed_path
            if not key:
                raise HTTPException(status_code=404, detail="处理图尚未生成")
        media_type = "image/jpeg"
        filename_for_response = get_processed_filename(image.original_filename)
    else:
        raise HTTPException(status_code=400, detail="图片类型必须是 original 或 processed")

    return _file_response(key, media_type, filename_for_response, cache_control)
