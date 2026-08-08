import io
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image as PillowImage
from PIL import UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.image import Image, ImageStatus
from app.models.image_version import ImageVersion
from app.models.operation_log import LogCategory, LogStatus
from app.models.user import User, UserRole
from app.processing.paths import get_processed_filename
from app.schemas.image import (
    ImagePageResponse,
    ImageReprocessRequest,
    ImageResponse,
    ImageVersionResponse,
    UploadFileResult,
    UploadResponse,
)
from app.services.audit import add_operation_log
from app.services.image_queries import apply_image_access_scope
from app.services.thumbnail_service import ThumbnailService
from app.storage.local import LocalStorage
from worker.tasks.image_tasks import process_image

router = APIRouter()
_storage = LocalStorage(settings.image_root)
_thumbnails = ThumbnailService(settings.image_root)
_SKU_PATTERN = re.compile(r"^[^/\\\x00-\x1f]+$")


def _normalize_filename(filename: str | None) -> tuple[str, str]:
    if not filename:
        raise ValueError("文件名不能为空")
    base_name = Path(filename.replace("\\", "/")).name.strip()
    if not base_name or base_name in {".", ".."}:
        raise ValueError("文件名无效")
    normalized = base_name.casefold()
    return base_name, normalized


def _validate_sku(sku: str) -> str:
    value = sku.strip()
    if not value or not _SKU_PATTERN.fullmatch(value) or value in {".", ".."}:
        raise ValueError("货号包含非法字符")
    if len(value) > 128:
        raise ValueError("货号长度不能超过 128 个字符")
    return value


def _remove_incomplete_processed_file(key: str) -> None:
    """重试前清理可能由旧任务留下的处理图和临时文件。"""
    path = _storage.get_local_path(key)
    path.unlink(missing_ok=True)
    path.with_name(f".{path.name}.processing").unlink(missing_ok=True)


def _check_image(content: bytes) -> tuple[str, int, int]:
    try:
        with PillowImage.open(io.BytesIO(content)) as image:
            image.verify()
        with PillowImage.open(io.BytesIO(content)) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("文件不是有效图片或图片已经损坏") from exc

    if image_format not in settings.allowed_image_formats:
        raise ValueError("仅支持 JPEG、PNG 和 WebP 图片")
    return image_format, width, height


def _can_access_image(image: Image, user: User) -> bool:
    if user.role == UserRole.ADMIN or image.owner_id == user.id:
        return True
    return user.role == UserRole.SUPERVISOR and image.owner.supervisor_id == user.id


def _get_accessible_image(image_id: int, user: User, db: Session) -> Image:
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    if not _can_access_image(image, user):
        raise HTTPException(status_code=403, detail="无权访问该图片")
    return image


def _get_manageable_image(image_id: int, user: User, db: Session) -> Image:
    image = _get_accessible_image(image_id, user, db)
    if user.role != UserRole.ADMIN and image.owner_id != user.id:
        raise HTTPException(status_code=403, detail="只能修改自己上传的图片")
    return image


@router.get("", response_model=ImagePageResponse)
def list_images(
    sku: str | None = None,
    filename: str | None = None,
    image_status: ImageStatus | None = Query(default=None, alias="status"),
    employee_id: str | None = None,
    sort_by: Literal["created_at", "sku", "filename", "status"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImagePageResponse:
    query = apply_image_access_scope(select(Image), current_user, employee_id)
    if sku:
        query = query.where(Image.sku == sku.strip())
    if filename:
        query = query.where(Image.original_filename.contains(filename.strip()))
    if image_status:
        query = query.where(Image.status == image_status)

    total_query = query.with_only_columns(func.count(Image.id)).order_by(None)
    total = db.scalar(total_query) or 0
    sort_columns = {
        "created_at": Image.created_at,
        "sku": Image.sku,
        "filename": Image.original_filename,
        "status": Image.status,
    }
    sort_column = sort_columns[sort_by]
    order_expression = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    page_query = (
        query.order_by(order_expression, Image.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return ImagePageResponse(
        items=list(db.scalars(page_query).all()),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/skus", response_model=list[str])
def list_image_skus(
    keyword: str | None = Query(default=None, max_length=128),
    employee_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    query = apply_image_access_scope(
        select(Image.sku).distinct(),
        current_user,
        employee_id,
    )
    normalized_keyword = keyword.strip() if keyword else ""
    if normalized_keyword:
        query = query.where(Image.sku.startswith(normalized_keyword, autoescape=True))
    query = query.order_by(Image.sku.asc()).limit(limit)
    return list(db.scalars(query).all())


@router.post("/upload", response_model=UploadResponse)
def upload_images(
    files: list[UploadFile] = File(...),
    sku: str = Form(...),
    ratio_width: int = Form(..., gt=0, le=1000),
    ratio_height: int = Form(..., gt=0, le=1000),
    min_short_side_px: int = Form(..., gt=0, le=20000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    try:
        safe_sku = _validate_sku(sku)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    results: list[UploadFileResult] = []

    for upload in files:
        original_key: str | None = None
        try:
            filename, normalized_filename = _normalize_filename(upload.filename)
            content = upload.file.read(max_bytes + 1)
            if not content:
                raise ValueError("文件内容为空")
            if len(content) > max_bytes:
                raise ValueError(f"单个文件不能超过 {settings.max_upload_size_mb} MB")

            image_format, width, height = _check_image(content)
            content_type = f"image/{'jpeg' if image_format == 'JPEG' else image_format.lower()}"
            original_key = _storage.build_key(
                current_user.employee_id,
                "original",
                safe_sku,
                filename,
            )
            if _storage.exists(original_key):
                raise FileExistsError("同一员工和货号下已存在同名文件，请修改本地文件名")

            _storage.save(original_key, io.BytesIO(content))
            image = Image(
                owner_id=current_user.id,
                employee_id=current_user.employee_id,
                sku=safe_sku,
                original_filename=filename,
                normalized_filename=normalized_filename,
                original_path=original_key,
                target_ratio_width=ratio_width,
                target_ratio_height=ratio_height,
                min_short_side_px=min_short_side_px,
                original_width=width,
                original_height=height,
                file_size=len(content),
                content_type=content_type,
                status=ImageStatus.PENDING,
            )
            db.add(image)
            db.flush()
            add_operation_log(
                db,
                category=LogCategory.IMAGE,
                action="upload_image",
                status=LogStatus.SUCCESS,
                actor=current_user,
                image_id=image.id,
                target=f"{safe_sku}/{filename}",
                message=f"上传图片 {filename}",
                details=f"ratio={ratio_width}:{ratio_height}, min_short_side={min_short_side_px}",
            )
            db.commit()
            db.refresh(image)

            try:
                process_image.delay(image.id)
            except Exception as exc:
                image.status = ImageStatus.FAILED
                image.error_message = f"处理任务提交失败: {exc}"[:2000]
                add_operation_log(
                    db,
                    category=LogCategory.PROCESSING,
                    action="enqueue_image",
                    status=LogStatus.FAILED,
                    actor=current_user,
                    image_id=image.id,
                    target=f"{safe_sku}/{filename}",
                    message="图片已保存，但无法提交处理任务",
                    details=str(exc),
                )
                db.commit()
            db.refresh(image)
            results.append(
                UploadFileResult(
                    filename=filename,
                    success=True,
                    image=ImageResponse.model_validate(image),
                ),
            )
        except (ValueError, FileExistsError) as exc:
            db.rollback()
            if original_key and _storage.exists(original_key):
                existing = db.scalar(select(Image).where(Image.original_path == original_key))
                if existing is None:
                    _storage.delete(original_key)
            results.append(
                UploadFileResult(
                    filename=upload.filename or "未命名文件",
                    success=False,
                    error=str(exc),
                ),
            )
        except IntegrityError:
            db.rollback()
            if original_key:
                _storage.delete(original_key)
            results.append(
                UploadFileResult(
                    filename=upload.filename or "未命名文件",
                    success=False,
                    error="同一员工和货号下已存在同名文件，请修改本地文件名",
                ),
            )
        finally:
            upload.file.close()

    return UploadResponse(results=results)


@router.get("/{image_id}", response_model=ImageResponse)
def get_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Image:
    return _get_accessible_image(image_id, current_user, db)


@router.get("/{image_id}/file/{kind}")
def download_image(
    image_id: int,
    kind: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    image = _get_accessible_image(image_id, current_user, db)
    if kind == "original":
        key = image.original_path
        media_type = image.content_type
        filename = image.original_filename
    elif kind == "processed":
        key = image.processed_path
        if not key:
            raise HTTPException(status_code=409, detail="处理图尚未生成")
        media_type = "image/jpeg"
        filename = get_processed_filename(image.original_filename)
    else:
        raise HTTPException(status_code=400, detail="文件类型必须是 original 或 processed")

    path = _storage.get_local_path(key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在")
    return FileResponse(
        path=path,
        media_type=media_type,
        filename=filename,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@router.get("/{image_id}/versions", response_model=list[ImageVersionResponse])
def list_image_versions(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ImageVersion]:
    _get_accessible_image(image_id, current_user, db)
    return list(
        db.scalars(
            select(ImageVersion)
            .where(ImageVersion.image_id == image_id)
            .order_by(ImageVersion.version_number.desc())
            .limit(10)
        ).all()
    )


@router.get("/{image_id}/versions/{version_number}/file")
def download_image_version(
    image_id: int,
    version_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    image = _get_accessible_image(image_id, current_user, db)
    version = db.scalar(
        select(ImageVersion).where(
            ImageVersion.image_id == image_id,
            ImageVersion.version_number == version_number,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="处理版本不存在")
    path = _storage.get_local_path(version.processed_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="处理版本文件不存在")
    return FileResponse(
        path=path,
        media_type="image/jpeg",
        filename=get_processed_filename(image.original_filename),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@router.post("/{image_id}/retry", response_model=ImageResponse)
def retry_image(
    image_id: int,
    payload: ImageReprocessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Image:
    image = _get_manageable_image(image_id, current_user, db)
    if image.status in {ImageStatus.PENDING, ImageStatus.PROCESSING}:
        raise HTTPException(status_code=409, detail="图片任务正在处理中")
    if image.current_version_number is None:
        legacy_keys = {
            _storage.build_key(
                image.employee_id,
                "processed",
                image.sku,
                get_processed_filename(image.original_filename),
            ),
            _storage.build_key(
                image.employee_id,
                "processed",
                image.sku,
                image.original_filename,
            ),
        }
        for processed_key in legacy_keys:
            if processed_key != image.processed_path:
                _remove_incomplete_processed_file(processed_key)
    image.target_ratio_width = payload.ratio_width
    image.target_ratio_height = payload.ratio_height
    image.min_short_side_px = payload.min_short_side_px
    image.status = ImageStatus.PENDING
    image.error_message = None
    add_operation_log(
        db,
        category=LogCategory.PROCESSING,
        action="retry_image",
        status=LogStatus.INFO,
        actor=current_user,
        image_id=image.id,
        target=f"{image.sku}/{image.original_filename}",
        message=f"重新提交图片处理任务 {image.original_filename}",
        details=(
            f"ratio={payload.ratio_width}:{payload.ratio_height}, "
            f"min_short_side={payload.min_short_side_px}"
        ),
    )
    db.commit()
    try:
        process_image.delay(image.id)
    except Exception as exc:
        image.status = ImageStatus.FAILED
        image.error_message = f"处理任务提交失败: {exc}"[:2000]
        add_operation_log(
            db,
            category=LogCategory.PROCESSING,
            action="enqueue_image",
            status=LogStatus.FAILED,
            actor=current_user,
            image_id=image.id,
            target=f"{image.sku}/{image.original_filename}",
            message="无法提交图片重试任务",
            details=str(exc),
        )
        db.commit()
    db.refresh(image)
    return image


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    image = _get_manageable_image(image_id, current_user, db)
    original_path = image.original_path
    processed_paths = {item.processed_path for item in image.versions}
    if image.processed_path:
        processed_paths.add(image.processed_path)
    add_operation_log(
        db,
        category=LogCategory.IMAGE,
        action="delete_image",
        status=LogStatus.SUCCESS,
        actor=current_user,
        employee_id=image.employee_id,
        target=f"{image.sku}/{image.original_filename}",
        message=f"删除图片 {image.original_filename}",
    )
    db.delete(image)
    db.commit()
    _storage.delete(original_path)
    _thumbnails.delete(image_id)
    for processed_path in processed_paths:
        _storage.delete(processed_path)
