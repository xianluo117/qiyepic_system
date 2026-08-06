from datetime import datetime

from celery.utils.log import get_task_logger

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.image import Image, ImageStatus
from app.models.operation_log import LogCategory, LogStatus
from app.processing.processor import ImageProcessor
from app.services.audit import add_operation_log
from app.storage.local import LocalStorage
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

    storage = LocalStorage(settings.image_root)
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

        try:
            processed_key = storage.build_key(
                image.employee_id,
                "processed",
                image.sku,
                image.original_filename,
            )
            result = processor.process(
                source_path=storage.get_local_path(image.original_path),
                target_path=storage.get_local_path(processed_key),
                ratio_width=image.target_ratio_width,
                ratio_height=image.target_ratio_height,
                min_short_side_px=image.min_short_side_px,
            )

            image.processed_path = processed_key
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
            db.commit()

            return {
                "image_id": image_id,
                "output_width": result.output_width,
                "output_height": result.output_height,
                "output_file_size": result.output_file_size,
                "compression_setting": result.compression_setting,
                "enlarged": result.enlarged,
                "reduced_for_size_limit": result.reduced_for_size_limit,
            }
        except Exception as exc:
            db.rollback()
            try:
                storage.get_local_path(processed_key).unlink(missing_ok=True)
                processing_path = storage.get_local_path(processed_key)
                processing_path.with_name(f".{processing_path.name}.processing").unlink(
                    missing_ok=True,
                )
            except (OSError, ValueError):
                logger.exception("清理失败处理图时发生异常，image_id=%s", image_id)
            image = db.get(Image, image_id)
            if image is not None:
                image.status = ImageStatus.FAILED
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
