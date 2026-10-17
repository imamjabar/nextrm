import os
from typing import List

# Shared product identity.
APP_NAME: str = os.getenv("APP_NAME", "NextRM")
APP_TAGLINE: str = os.getenv("APP_TAGLINE", "AI relationship copilot for banks")
APP_VERSION: str = "1.0.0"

# DATABASE CONFIGURATION: PostgreSQL only (Cloud SQL in the cloud, scripts/dev_db.sh locally)
DATABASE_URL_EXPLICIT: bool = "DATABASE_URL" in os.environ
DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+psycopg://127.0.0.1:54417/nextrm")
DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "5"))
DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))

# ENVIRONMENT
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

# CORS
CORS_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# AI CONFIGURATION
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "")

# SECURITY
JWT_SECRET: str = os.getenv("JWT_SECRET", "nextrm-development-secret-key-32bytes-min")
ALGORITHM: str = "HS256"
