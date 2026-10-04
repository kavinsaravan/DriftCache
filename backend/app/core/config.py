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
    API_KEY: str = Field(default="", description="API key for authentication (set in production)")
    METRICS_API_KEY: str = Field(default="", description="Read-only key for metrics/dashboard (optional)")
    REQUIRE_API_KEY: bool = Field(default=True, description="Require API key for requests")

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Vercel domains (set via env var in production)
    VERCEL_DOMAIN: str = Field(default="")

    # Allow all Vercel domains (for preview deployments)
    ALLOW_ALL_VERCEL: bool = Field(default=True)

    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins including Vercel domain if set"""
        origins = self.CORS_ORIGINS.copy()

        # Add specific Vercel domain
        if self.VERCEL_DOMAIN:
            origins.append(f"https://{self.VERCEL_DOMAIN}")

        # For development: allow all Vercel preview deployments
        # Note: In production, you should set specific domains only
        if self.ALLOW_ALL_VERCEL:
            # This is handled in main.py with allow_origin_regex
            pass

        return origins

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
        if self.DATABASE_URL and self.DATABASE_URL.startswith(("postgresql://", "postgres://", "sqlite://")):
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis
    REDIS_URL: str = Field(default="")
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    REDIS_PASSWORD: str = Field(default="")

    def get_redis_url(self) -> str:
        """Get Redis URL from env var or construct from components"""
        if self.REDIS_URL:
            return self.REDIS_URL
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

    # Fine-Tuning & Model Training
    HF_TOKEN: str = Field(default="", description="Hugging Face API token for model uploads")
    WANDB_API_KEY: str = Field(default="", description="Weights & Biases API key for experiment tracking")
    ENABLE_TRAINING: bool = Field(default=True, description="Enable fine-tuning capabilities")

    # Vector Search
    VECTOR_INDEX_TYPE: str = Field(default="FLAT")  # FLAT, IVF, HNSW

    # Storage Paths (relative to project root)
    INDEX_STORAGE_DIR: str = Field(default="data/cache")
    FAISS_INDEX_FILENAME: str = Field(default="faiss.index")
    METADATA_FILENAME: str = Field(default="metadata.json")

    # Autonomous Optimization
    DRIFT_DETECTION_ENABLED: bool = Field(default=True)
    OPTIMIZATION_INTERVAL_SECONDS: int = Field(default=300)  # 5 minutes

    def get_index_path(self) -> str:
        """Get absolute path to FAISS index file"""
        from pathlib import Path
        # Find project root (backend/app/core/config.py -> DriftCache/)
        # parent: core -> app -> backend -> DriftCache (3 parent calls)
        project_root = Path(__file__).parent.parent.parent.parent
        storage_dir = project_root / self.INDEX_STORAGE_DIR
        storage_dir.mkdir(parents=True, exist_ok=True)
        return str(storage_dir / self.FAISS_INDEX_FILENAME)

    def get_metadata_path(self) -> str:
        """Get absolute path to metadata file"""
        from pathlib import Path
        # Find project root (backend/app/core/config.py -> DriftCache/)
        project_root = Path(__file__).parent.parent.parent.parent
        storage_dir = project_root / self.INDEX_STORAGE_DIR
        storage_dir.mkdir(parents=True, exist_ok=True)
        return str(storage_dir / self.METADATA_FILENAME)

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore unknown env vars (for backwards compatibility)


settings = Settings()
