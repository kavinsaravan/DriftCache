"""
SQLAlchemy Base Model

Defines the declarative base for all database models
"""
from sqlalchemy.ext.declarative import declarative_base

# Create declarative base
Base = declarative_base()

# Import all models here to ensure they're registered with Base
# This is important for Alembic migrations
def import_models():
    """Import all models to register them with Base"""
    from app.models import request  # noqa
    from app.models import cache_entry  # noqa
    from app.models import cache_event  # noqa
    from app.models import embedding_record  # noqa
    from app.models import provider_call  # noqa
    from app.models import threshold_version  # noqa
    from app.models import index_version  # noqa
