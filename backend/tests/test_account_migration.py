"""Ownership migration preserves pre-existing administrator-managed projects."""
import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_account_migration_preserves_existing_projects(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/014_add_user_accounts.py'
    spec = importlib.util.spec_from_file_location('account_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite:///' + str(tmp_path / 'migration.db'))
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE projects (id VARCHAR(36) PRIMARY KEY, name VARCHAR(100), tenant_id VARCHAR(100))'))
        connection.execute(text("INSERT INTO projects VALUES ('existing', 'Existing project', 'project:existing')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert connection.execute(text('SELECT id, owner_id FROM projects')).one() == ('existing', None)
        assert {'users', 'user_sessions', 'auth_attempts'} <= set(inspect(connection).get_table_names())
        assert any(fk['referred_table'] == 'users' for fk in inspect(connection).get_foreign_keys('projects'))
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert connection.execute(text('SELECT id FROM projects')).scalar() == 'existing'
        assert 'owner_id' not in [col['name'] for col in inspect(connection).get_columns('projects')]
    engine.dispose()
