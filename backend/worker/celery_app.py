from celery import Celery

from app.core.config import settings

_broker_url = "memory://" if settings.task_always_eager else settings.redis_url
_result_backend = "cache+memory://" if settings.task_always_eager else settings.redis_url

celery_app = Celery(
    "image_system",
    broker=_broker_url,
    backend=_result_backend,
    include=["worker.tasks.image_tasks"],
)
celery_app.conf.update(
    task_always_eager=settings.task_always_eager,
    task_eager_propagates=True,
    task_store_eager_result=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
