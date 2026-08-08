import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "migrations"
    / "versions"
    / "0007_image_query_indexes.py"
)
EXPECTED_INDEXES = {
    "ix_images_owner_created_id",
    "ix_images_owner_sku_created_id",
    "ix_images_employee_created_id",
    "ix_images_employee_sku_created_id",
    "ix_images_status_created_id",
    "ix_images_sku_created_id",
}
REMOVED_SINGLE_INDEXES = {
    "ix_images_owner_id",
    "ix_images_employee_id",
    "ix_images_sku",
    "ix_images_status",
}


def load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_0007", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_upgrade(connection: sa.Connection) -> None:
    module = load_migration_module()
    context = MigrationContext.configure(connection)
    operations = Operations(context)
    original_op = module.op
    module.op = operations
    try:
        module.upgrade()
    finally:
        module.op = original_op


def create_images_table(connection: sa.Connection) -> None:
    metadata = sa.MetaData()
    sa.Table(
        "images",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.String(64), nullable=False),
        sa.Column("sku", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    metadata.create_all(connection)
    for index_name, column_name in (
        ("ix_images_owner_id", "owner_id"),
        ("ix_images_employee_id", "employee_id"),
        ("ix_images_sku", "sku"),
        ("ix_images_status", "status"),
    ):
        sa.Index(index_name, metadata.tables["images"].c[column_name]).create(connection)


def test_upgrade_creates_all_query_indexes_and_is_idempotent() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        create_images_table(connection)
        run_upgrade(connection)
        run_upgrade(connection)
        indexes = {
            index["name"] for index in inspect(connection).get_indexes("images")
        }

    assert EXPECTED_INDEXES <= indexes
    assert REMOVED_SINGLE_INDEXES.isdisjoint(indexes)
