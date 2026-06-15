"""
Application configuration
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings"""

    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "DriftCache"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.vercel.app",  # Vercel preview and production deployments
    ]

    # Database
    DATABASE_URL: str = Field(default="sqlite:///./driftcache.db")
    POSTGRES_USER: str = Field(default="driftcache")
    POSTGRES_PASSWORD: str = Field(default="driftcache_password")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="driftcache")

    @property
    def DB_URL(self) -> str:
        """Return DATABASE_URL if set, otherwise construct PostgreSQL URL"""
        if self.DATABASE_URL and not self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    REDIS_PASSWORD: str = Field(default="")

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # LLM Provider Configuration
    ANTHROPIC_API_KEY: str = Field(default="")
    OPENAI_API_KEY: str = Field(default="")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    DEFAULT_MODEL: str = Field(default="claude-3-5-sonnet-20241022")

    # Semantic Cache Settings
    SIMILARITY_THRESHOLD: float = Field(default=0.85, ge=0.0, le=1.0)
    CACHE_TTL_SECONDS: int = Field(default=3600)  # 1 hour default

    # Embedding Model
    EMBEDDING_MODEL: str = Field(default="all-MiniLM-L6-v2")
    EMBEDDING_DIMENSION: int = Field(default=384)

    # Vector Search
    VECTOR_INDEX_TYPE: str = Field(default="FLAT")  # FLAT, IVF, HNSW

    # Autonomous Optimization
    DRIFT_DETECTION_ENABLED: bool = Field(default=True)
    OPTIMIZATION_INTERVAL_SECONDS: int = Field(default=300)  # 5 minutes

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
