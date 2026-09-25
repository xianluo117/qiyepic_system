"""添加集成令牌。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_integration_tokens"
down_revision: str | Sequence[str] | None = "0007_image_query_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("scopes", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_integration_tokens_token_hash"),
    )
    op.create_index("ix_integration_tokens_user_id", "integration_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_table("integration_tokens")
