"""增加图片查询复合索引

Revision ID: 0007_image_query_indexes
Revises: 0006_image_versions
Create Date: 2026-08-08
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

revision: str = "0007_image_query_indexes"
down_revision: str | Sequence[str] | None = "0006_image_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_COLUMNS = {
    "ix_images_owner_created_id": ["owner_id", "created_at", "id"],
    "ix_images_owner_sku_created_id": ["owner_id", "sku", "created_at", "id"],
    "ix_images_employee_created_id": ["employee_id", "created_at", "id"],
    "ix_images_employee_sku_created_id": [
        "employee_id",
        "sku",
        "created_at",
        "id",
    ],
    "ix_images_status_created_id": ["status", "created_at", "id"],
    "ix_images_sku_created_id": ["sku", "created_at", "id"],
}
_COVERED_SINGLE_INDEX_COLUMNS = {
    "ix_images_owner_id": ["owner_id"],
    "ix_images_employee_id": ["employee_id"],
    "ix_images_sku": ["sku"],
    "ix_images_status": ["status"],
}


def _get_existing_indexes() -> set[str]:
    return {
        index["name"] for index in inspect(op.get_bind()).get_indexes("images")
    }


def upgrade() -> None:
    existing_indexes = _get_existing_indexes()
    for index_name, columns in _INDEX_COLUMNS.items():
        if index_name not in existing_indexes:
            op.create_index(index_name, "images", columns, unique=False)

    existing_indexes = _get_existing_indexes()
    for index_name in _COVERED_SINGLE_INDEX_COLUMNS:
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="images")


def downgrade() -> None:
    existing_indexes = _get_existing_indexes()
    for index_name, columns in _COVERED_SINGLE_INDEX_COLUMNS.items():
        if index_name not in existing_indexes:
            op.create_index(index_name, "images", columns, unique=False)

    existing_indexes = _get_existing_indexes()
    for index_name in reversed(_INDEX_COLUMNS):
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="images")
