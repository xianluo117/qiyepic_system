"""增加主管角色与直属员工归属

Revision ID: 0004_supervisor_role
Revises: 0003_image_public_token
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_supervisor_role"
down_revision: str | Sequence[str] | None = "0003_image_public_token"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("supervisor_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_users_supervisor_id", ["supervisor_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_users_supervisor_id_users",
            "users",
            ["supervisor_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_supervisor_id_users", type_="foreignkey")
        batch_op.drop_index("ix_users_supervisor_id")
        batch_op.drop_column("supervisor_id")
