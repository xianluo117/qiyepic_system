#!/bin/sh
set -eu

wait_for_database() {
    python - <<'PY'
import time
from sqlalchemy import create_engine, text
from app.core.config import settings

last_error = None
for _ in range(60):
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        raise SystemExit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(2)

raise SystemExit(f"数据库连接超时: {last_error}")
PY
}

case "${1:-api}" in
    api)
        wait_for_database
        alembic upgrade head
        exec uvicorn app.main:app --host 0.0.0.0 --port 1231 --workers "${API_WORKERS:-2}"
        ;;
    worker)
        wait_for_database
        exec celery -A worker.celery_app:celery_app worker \
            --loglevel="${CELERY_LOG_LEVEL:-INFO}" \
            --concurrency="${CELERY_CONCURRENCY:-2}"
        ;;
    web)
        exec nginx -g "daemon off;"
        ;;
    *)
        exec "$@"
        ;;
esac
