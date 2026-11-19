import pytest

from app import main as app_main
from app.config import get_settings


@pytest.fixture(autouse=True)
def fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_missing_settings_are_reported_by_name(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # .env fayli yo'q papka
    monkeypatch.delenv("BOT_TOKEN")
    monkeypatch.delenv("ENCRYPTION_KEY")
    with pytest.raises(SystemExit) as exit_info:
        app_main.main()
    message = str(exit_info.value)
    assert "BOT_TOKEN" in message and "ENCRYPTION_KEY" in message


def test_malformed_encryption_key_stops_startup(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENCRYPTION_KEY", "not-a-valid-key")
    monkeypatch.setattr("app.utils.crypto._cipher", None)
    with pytest.raises(SystemExit) as exit_info:
        app_main.main()
    assert "ENCRYPTION_KEY" in str(exit_info.value)


def test_run_migrations_creates_tables(tmp_path):
    import sqlalchemy as sa

    db_path = tmp_path / "bot.db"
    app_main.run_migrations(f"sqlite+aiosqlite:///{db_path}")
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.connect() as connection:
        assert "transactions" in sa.inspect(connection).get_table_names()
    engine.dispose()
