"""Persist COS fallback operations."""
import sqlalchemy as sa
from alembic import op

revision = "0010_storage_pending"
down_revision = "0009_mcp_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "storage_pending",
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("revision", sa.String(32), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("storage_pending")
