"""Alembic migratsiyasi modellar bilan bir xil sxema yaratishini tekshiradi."""

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from app.database import Base

ROOT = Path(__file__).resolve().parent.parent


def alembic_config(db_path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    return config


def test_upgrade_creates_schema_identical_to_models(tmp_path):
    db_path = tmp_path / "migrated.db"
    command.upgrade(alembic_config(db_path), "head")

    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.connect() as connection:
        tables = set(sa.inspect(connection).get_table_names())
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()

    assert {"users", "cards", "categories", "transactions", "merchant_rules"} <= tables
    assert differences == []


def test_downgrade_removes_all_tables(tmp_path):
    db_path = tmp_path / "migrated.db"
    config = alembic_config(db_path)
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.connect() as connection:
        tables = set(sa.inspect(connection).get_table_names()) - {"alembic_version"}
    engine.dispose()
    assert tables == set()
