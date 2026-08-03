"""为图片增加不可猜测的公开访问令牌

Revision ID: 0003_image_public_token
Revises: 0002_operation_logs
Create Date: 2026-07-31
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0003_image_public_token"
down_revision: str | Sequence[str] | None = "0002_operation_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("images", sa.Column("public_token", sa.String(length=32), nullable=True))

    connection = op.get_bind()
    image_ids = connection.execute(sa.text("SELECT id FROM images")).scalars().all()
    for image_id in image_ids:
        connection.execute(
            sa.text("UPDATE images SET public_token = :token WHERE id = :image_id"),
            {"token": uuid4().hex, "image_id": image_id},
        )

    with op.batch_alter_table("images") as batch_op:
        batch_op.alter_column(
            "public_token",
            existing_type=sa.String(length=32),
            nullable=False,
        )
        batch_op.create_index("ix_images_public_token", ["public_token"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("images") as batch_op:
        batch_op.drop_index("ix_images_public_token")
        batch_op.drop_column("public_token")
