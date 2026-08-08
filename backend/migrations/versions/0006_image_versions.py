"""增加图片处理版本表

Revision ID: 0006_image_versions
Revises: 0005_remove_image_public_token
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0006_image_versions"
down_revision: str | Sequence[str] | None = "0005_remove_image_public_token"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = inspect(connection)
    image_columns = {column["name"] for column in inspector.get_columns("images")}

    # MySQL 的 DDL 会立即提交。容器在创建列后异常重启时，Alembic
    # 版本号仍停留在 0005，因此迁移必须能够从半完成状态继续执行。
    if "current_version_number" not in image_columns:
        with op.batch_alter_table("images") as batch_op:
            batch_op.add_column(
                sa.Column("current_version_number", sa.Integer(), nullable=True)
            )

    inspector = inspect(connection)
    if "image_versions" not in inspector.get_table_names():
        op.create_table(
            "image_versions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("image_id", sa.Integer(), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("processed_path", sa.String(length=1024), nullable=False),
            sa.Column("ratio_width", sa.Integer(), nullable=False),
            sa.Column("ratio_height", sa.Integer(), nullable=False),
            sa.Column("min_short_side_px", sa.Integer(), nullable=False),
            sa.Column("output_width", sa.Integer(), nullable=False),
            sa.Column("output_height", sa.Integer(), nullable=False),
            sa.Column("file_size", sa.BigInteger(), nullable=False),
            sa.Column("compression_setting", sa.String(length=128), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["image_id"],
                ["images.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "image_id",
                "version_number",
                name="uq_image_versions_image_version",
            ),
        )

    inspector = inspect(connection)
    existing_indexes = {
        index["name"] for index in inspector.get_indexes("image_versions")
    }
    if "ix_image_versions_image_id" not in existing_indexes:
        op.create_index(
            "ix_image_versions_image_id",
            "image_versions",
            ["image_id"],
            unique=False,
        )
    if "ix_image_versions_created_at" not in existing_indexes:
        op.create_index(
            "ix_image_versions_created_at",
            "image_versions",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_image_versions_created_at", table_name="image_versions")
    op.drop_index("ix_image_versions_image_id", table_name="image_versions")
    op.drop_table("image_versions")
    with op.batch_alter_table("images") as batch_op:
        batch_op.drop_column("current_version_number")
