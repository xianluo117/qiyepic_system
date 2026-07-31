"""创建管理员操作日志表

Revision ID: 0002_operation_logs
Revises: 0001_initial
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_operation_logs"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operation_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=128), nullable=True),
        sa.Column("employee_id", sa.String(length=64), nullable=True),
        sa.Column("image_id", sa.Integer(), nullable=True),
        sa.Column("target", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operation_logs_category", "operation_logs", ["category"])
    op.create_index("ix_operation_logs_action", "operation_logs", ["action"])
    op.create_index("ix_operation_logs_status", "operation_logs", ["status"])
    op.create_index("ix_operation_logs_actor_id", "operation_logs", ["actor_id"])
    op.create_index(
        "ix_operation_logs_actor_username",
        "operation_logs",
        ["actor_username"],
    )
    op.create_index("ix_operation_logs_employee_id", "operation_logs", ["employee_id"])
    op.create_index("ix_operation_logs_image_id", "operation_logs", ["image_id"])
    op.create_index("ix_operation_logs_created_at", "operation_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("operation_logs")
