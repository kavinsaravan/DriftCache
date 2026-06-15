"""
Database Session Management

Creates and manages PostgreSQL database connections
"""
import logging
from typing import Generator, Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Database connection manager

    Handles SQLAlchemy engine and session lifecycle
    """

    def __init__(self):
        """Initialize database manager"""
        self.engine = None
        self.SessionLocal = None
        self._initialized = False

    def initialize(self) -> None:
        """
        Initialize database engine and session factory

        Creates connection pool and configures SQLAlchemy
        """
        if self._initialized:
            logger.info("Database already initialized")
            return

        try:
            # Get database URL (supports SQLite or PostgreSQL)
            db_url = getattr(settings, 'DB_URL', settings.DATABASE_URL)

            # SQLite requires different engine configuration
            if db_url.startswith('sqlite'):
                self.engine = create_engine(
                    db_url,
                    connect_args={"check_same_thread": False},  # Required for SQLite
                    echo=False,
                )
            else:
                # PostgreSQL with connection pooling
                self.engine = create_engine(
                    db_url,
                    poolclass=QueuePool,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    echo=False,
                )

            # Add connection event listeners
            @event.listens_for(self.engine, "connect")
            def receive_connect(dbapi_conn, connection_record):
                logger.debug("Database connection established")

            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            self._initialized = True
            if db_url.startswith('sqlite'):
                logger.info(f"Database initialized: SQLite ({db_url})")
            else:
                logger.info(
                    f"Database initialized: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
                )

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def create_tables(self) -> None:
        """
        Create all database tables

        Note: In production, use Alembic migrations instead
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized")

        from app.database.base import Base
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")

    def dispose(self) -> None:
        """Dispose of database engine and connections"""
        if self.engine:
            self.engine.dispose()
            self._initialized = False
            logger.info("Database connections disposed")

    def get_session(self) -> Session:
        """
        Get a new database session

        Returns:
            SQLAlchemy Session

        Raises:
            RuntimeError: If database not initialized
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        return self.SessionLocal()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions

        Automatically commits on success, rolls back on error

        Usage:
            with db_manager.session_scope() as session:
                session.add(obj)
                # Automatically commits here

        Yields:
            SQLAlchemy Session
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def health_check(self) -> bool:
        """
        Check database connection health

        Returns:
            True if healthy, False otherwise
        """
        if not self._initialized:
            return False

        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    @property
    def is_initialized(self) -> bool:
        """Check if database is initialized"""
        return self._initialized


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """
    Get global database manager instance

    Returns:
        DatabaseManager singleton
    """
    global _db_manager

    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.initialize()

    return _db_manager


def get_db() -> Generator[Session, None, None]:
    """
    Get database session for dependency injection

    Usage with FastAPI:
        @app.get("/")
        def endpoint(db: Session = Depends(get_db)):
            ...

    Yields:
        SQLAlchemy Session
    """
    db_manager = get_db_manager()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def shutdown_db() -> None:
    """Shutdown database connections"""
    global _db_manager

    if _db_manager:
        _db_manager.dispose()
        _db_manager = None
