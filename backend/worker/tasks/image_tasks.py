from datetime import datetime

from celery.utils.log import get_task_logger

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.image import Image, ImageStatus
from app.processing.processor import ImageProcessor
from app.storage.local import LocalStorage
from worker.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(
    bind=True,
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_image(self, image_id: int) -> dict[str, int | bool]:
    """读取原图，先裁剪，再按最小短边判断是否放大。"""

    storage = LocalStorage(settings.image_root)
    processor = ImageProcessor()

    with SessionLocal() as db:
        image = db.get(Image, image_id)
        if image is None:
            raise ValueError(f"图片记录不存在: {image_id}")

        image.status = ImageStatus.PROCESSING
        image.error_message = None
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
            db.commit()

            return {
                "image_id": image_id,
                "output_width": result.output_width,
                "output_height": result.output_height,
                "enlarged": result.enlarged,
            }
        except Exception as exc:
            db.rollback()
            image = db.get(Image, image_id)
            if image is not None:
                image.status = ImageStatus.FAILED
                image.error_message = str(exc)[:2000]
                db.commit()
            logger.exception("图片处理失败，image_id=%s", image_id)
            raise
