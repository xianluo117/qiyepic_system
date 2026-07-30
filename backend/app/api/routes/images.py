import io
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image as PillowImage
from PIL import UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.image import Image, ImageStatus
from app.models.user import User, UserRole
from app.schemas.image import ImageResponse, UploadFileResult, UploadResponse
from app.storage.local import LocalStorage
from worker.tasks.image_tasks import process_image

router = APIRouter()
_storage = LocalStorage(settings.image_root)
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


def _get_accessible_image(image_id: int, user: User, db: Session) -> Image:
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    if user.role != UserRole.ADMIN and image.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该图片")
    return image


@router.get("", response_model=list[ImageResponse])
def list_images(
    sku: str | None = None,
    filename: str | None = None,
    image_status: ImageStatus | None = Query(default=None, alias="status"),
    employee_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Image]:
    query = select(Image).order_by(Image.created_at.desc())
    if current_user.role != UserRole.ADMIN:
        query = query.where(Image.owner_id == current_user.id)
    elif employee_id:
        query = query.where(Image.employee_id == employee_id)
    if sku:
        query = query.where(Image.sku.contains(sku.strip()))
    if filename:
        query = query.where(Image.original_filename.contains(filename.strip()))
    if image_status:
        query = query.where(Image.status == image_status)
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
            db.commit()
            db.refresh(image)

            process_image.delay(image.id)
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
    elif kind == "processed":
        key = image.processed_path
        if not key:
            raise HTTPException(status_code=409, detail="处理图尚未生成")
    else:
        raise HTTPException(status_code=400, detail="文件类型必须是 original 或 processed")

    path = _storage.get_local_path(key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在")
    return FileResponse(path=path, media_type=image.content_type, filename=image.original_filename)


@router.post("/{image_id}/retry", response_model=ImageResponse)
def retry_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Image:
    image = _get_accessible_image(image_id, current_user, db)
    if image.status in {ImageStatus.PENDING, ImageStatus.PROCESSING}:
        raise HTTPException(status_code=409, detail="图片任务正在处理中")
    image.status = ImageStatus.PENDING
    image.error_message = None
    db.commit()
    process_image.delay(image.id)
    db.refresh(image)
    return image


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    image = _get_accessible_image(image_id, current_user, db)
    original_path = image.original_path
    processed_path = image.processed_path
    db.delete(image)
    db.commit()
    _storage.delete(original_path)
    if processed_path:
        _storage.delete(processed_path)
