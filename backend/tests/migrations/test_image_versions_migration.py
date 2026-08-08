import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import UniqueConstraint, inspect

from app.models.image_version import ImageVersion

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "migrations"
    / "versions"
    / "0006_image_versions.py"
)


def load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_0006", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_images_table(connection: sa.Connection) -> None:
    metadata = sa.MetaData()
    sa.Table(
        "images",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    metadata.create_all(connection)


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


def test_upgrade_recovers_when_column_already_exists_but_table_does_not() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        create_images_table(connection)
        connection.execute(
            sa.text("ALTER TABLE images ADD COLUMN current_version_number INTEGER")
        )

        run_upgrade(connection)

        inspector = inspect(connection)
        image_columns = {column["name"] for column in inspector.get_columns("images")}
        table_names = set(inspector.get_table_names())
        indexes = {
            index["name"] for index in inspector.get_indexes("image_versions")
        }
        unique_constraints = {
            constraint["name"]: tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("image_versions")
        }

    assert "current_version_number" in image_columns
    assert "image_versions" in table_names
    assert "ix_image_versions_image_id" in indexes
    assert "ix_image_versions_created_at" in indexes
    assert unique_constraints["uq_image_versions_image_version"] == (
        "image_id",
        "version_number",
    )
    assert ("processed_path",) not in unique_constraints.values()


def test_upgrade_is_idempotent_after_all_objects_exist() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        create_images_table(connection)
        run_upgrade(connection)
        run_upgrade(connection)

        inspector = inspect(connection)
        image_columns = [
            column["name"] for column in inspector.get_columns("images")
        ]
        table_names = inspector.get_table_names()

    assert image_columns.count("current_version_number") == 1
    assert table_names.count("image_versions") == 1


def test_model_does_not_create_unique_index_for_long_processed_path() -> None:
    processed_path = ImageVersion.__table__.columns["processed_path"]
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in ImageVersion.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert processed_path.type.length == 1024
    assert processed_path.unique is not True
    assert ("processed_path",) not in unique_constraints
    assert ("image_id", "version_number") in unique_constraints
