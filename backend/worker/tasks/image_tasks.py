import tempfile
from datetime import datetime
from pathlib import Path

from celery.utils.log import get_task_logger
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.image import Image, ImageStatus
from app.models.image_version import ImageVersion
from app.models.operation_log import LogCategory, LogStatus
from app.processing.paths import get_versioned_processed_filename
from app.processing.processor import ImageProcessor
from app.services.audit import add_operation_log
from app.storage.factory import create_storage
from worker.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(
    bind=True,
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_image(self, image_id: int) -> dict[str, int | bool | str]:
    """读取原图，依次执行裁剪、像素处理和 2 MiB 限制压缩。"""

    storage = create_storage()
    processor = ImageProcessor()

    with SessionLocal() as db:
        image = db.get(Image, image_id)
        if image is None:
            raise ValueError(f"图片记录不存在: {image_id}")

        image.status = ImageStatus.PROCESSING
        image.error_message = None
        add_operation_log(
            db,
            category=LogCategory.PROCESSING,
            action="process_image",
            status=LogStatus.INFO,
            employee_id=image.employee_id,
            image_id=image.id,
            target=f"{image.sku}/{image.original_filename}",
            message=f"开始处理图片 {image.original_filename}",
        )
        db.commit()

        latest_version = db.scalar(
            select(func.max(ImageVersion.version_number)).where(
                ImageVersion.image_id == image.id,
            )
        )
        current_version_number = image.current_version_number or 0
        version_number = max(latest_version or 0, current_version_number) + 1
        processed_key = storage.build_key(
            image.employee_id,
            "processed",
            image.sku,
            get_versioned_processed_filename(
                image.original_filename,
                image.id,
                version_number,
            ),
        )
        try:
            with tempfile.TemporaryDirectory() as temporary_dir:
                temporary_root = Path(temporary_dir)
                source_path = storage.download_to_path(
                    image.original_path,
                    temporary_root / "original" / image.original_filename,
                )
                target_path = temporary_root / "processed" / get_versioned_processed_filename(
                    image.original_filename,
                    image.id,
                    version_number,
                )
                result = processor.process(
                    source_path=source_path,
                    target_path=target_path,
                    ratio_width=image.target_ratio_width,
                    ratio_height=image.target_ratio_height,
                    min_short_side_px=image.min_short_side_px,
                )
                storage.upload_from_path(processed_key, target_path, "image/jpeg")

            version = ImageVersion(
                image_id=image.id,
                version_number=version_number,
                processed_path=processed_key,
                ratio_width=image.target_ratio_width,
                ratio_height=image.target_ratio_height,
                min_short_side_px=image.min_short_side_px,
                output_width=result.output_width,
                output_height=result.output_height,
                file_size=result.output_file_size,
                compression_setting=result.compression_setting,
            )
            db.add(version)
            image.processed_path = processed_key
            image.current_version_number = version_number
            image.original_width = result.original_width
            image.original_height = result.original_height
            image.processed_width = result.output_width
            image.processed_height = result.output_height
            image.status = ImageStatus.SUCCESS
            image.processed_at = datetime.now()
            add_operation_log(
                db,
                category=LogCategory.PROCESSING,
                action="process_image",
                status=LogStatus.SUCCESS,
                employee_id=image.employee_id,
                image_id=image.id,
                target=f"{image.sku}/{image.original_filename}",
                message=f"图片处理成功 {image.original_filename}",
                details=(
                    f"output={result.output_width}x{result.output_height}, "
                    f"file_size={result.output_file_size}, "
                    f"compression={result.compression_setting}, "
                    f"enlarged={result.enlarged}, "
                    f"reduced_for_size_limit={result.reduced_for_size_limit}"
                ),
            )
            db.flush()
            expired_versions = list(
                db.scalars(
                    select(ImageVersion)
                    .where(ImageVersion.image_id == image.id)
                    .order_by(ImageVersion.version_number.desc())
                    .offset(10)
                ).all()
            )
            expired_paths = [item.processed_path for item in expired_versions]
            for item in expired_versions:
                db.delete(item)
            db.commit()
            for expired_path in expired_paths:
                storage.delete(expired_path)

            return {
                "image_id": image_id,
                "output_width": result.output_width,
                "output_height": result.output_height,
                "output_file_size": result.output_file_size,
                "compression_setting": result.compression_setting,
                "enlarged": result.enlarged,
                "reduced_for_size_limit": result.reduced_for_size_limit,
                "version_number": version_number,
            }
        except Exception as exc:
            db.rollback()
            try:
                storage.delete(processed_key)
            except (OSError, ValueError):
                logger.exception("清理失败处理图时发生异常，image_id=%s", image_id)
            image = db.get(Image, image_id)
            if image is not None:
                image.status = (
                    ImageStatus.SUCCESS
                    if image.processed_path
                    else ImageStatus.FAILED
                )
                image.error_message = str(exc)[:2000]
                add_operation_log(
                    db,
                    category=LogCategory.PROCESSING,
                    action="process_image",
                    status=LogStatus.FAILED,
                    employee_id=image.employee_id,
                    image_id=image.id,
                    target=f"{image.sku}/{image.original_filename}",
                    message=f"图片处理失败 {image.original_filename}",
                    details=str(exc),
                )
                db.commit()
            logger.exception("图片处理失败，image_id=%s", image_id)
            raise
