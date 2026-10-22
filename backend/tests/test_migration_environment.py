"""Exercise the real Alembic environment without a live service/database."""
from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import settings
from app.database.base import Base


def test_migration_environment_imports_current_models_and_emits_upgrade_sql(monkeypatch):
    backend = Path(__file__).resolve().parents[1]
    # Offline PostgreSQL SQL generation runs env.py and every upgrade, avoiding
    # SQLite's unsupported ALTER statements and any connection to a real DB.
    monkeypatch.setattr(settings, 'DATABASE_URL', 'postgresql://test:test@localhost/driftcache_test')
    output = StringIO()
    config = Config(str(backend / 'alembic.ini'), output_buffer=output)
    config.set_main_option('script_location', str(backend / 'alembic'))
    command.upgrade(config, 'head', sql=True)
    sql = output.getvalue()
    assert 'CREATE TABLE requests' in sql
    assert 'CREATE TABLE projects' in sql
    assert '013' in sql
    assert {'requests', 'cache_entries', 'cache_events', 'index_versions', 'projects', 'training_jobs'} <= set(Base.metadata.tables)
