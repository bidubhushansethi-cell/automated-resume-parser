"""Application configuration. All secrets come from environment variables (.env)."""
import os
from pathlib import Path

from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent


def _database_uri():
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    password = os.environ.get("DB_PASSWORD")
    if not password:
        # Fall back to a local SQLite file so the app works without PostgreSQL
        return f"sqlite:///{BASE_DIR / 'resume_parser.db'}"
    return URL.create(
        "postgresql+psycopg2",
        username=os.environ.get("DB_USER", "postgres"),
        password=password,
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "resume_parser"),
    )


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", BASE_DIR / "uploads"))
    MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "5"))
    MAX_FILES_PER_UPLOAD = int(os.environ.get("MAX_FILES_PER_UPLOAD", "20"))
    MAX_CONTENT_LENGTH = (MAX_FILE_MB * MAX_FILES_PER_UPLOAD + 1) * 1024 * 1024
    ALLOWED_EXTENSIONS = {".pdf", ".docx"}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = 8 * 3600
    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    MAX_FILE_MB = 1
