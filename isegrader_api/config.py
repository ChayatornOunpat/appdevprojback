import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _mariadb_uri() -> str:
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit

    host = os.environ.get("MARIADB_HOST", os.environ.get("MYSQL_HOST", "127.0.0.1"))
    port = os.environ.get("MARIADB_PORT", os.environ.get("MYSQL_PORT", "3306"))
    user = os.environ.get("MARIADB_USER", os.environ.get("MYSQL_USER", "root"))
    password = os.environ.get("MARIADB_PASSWORD", os.environ.get("MYSQL_PASSWORD", ""))
    database = os.environ.get("MARIADB_DATABASE", os.environ.get("MYSQL_DATABASE", "isegrader_api"))

    auth = quote_plus(user)
    if password:
        auth = f"{auth}:{quote_plus(password)}"

    return f"mysql+pymysql://{auth}@{host}:{port}/{quote_plus(database)}?charset=utf8mb4"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_SECONDS", "86400"))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES_DAYS", "30"))
    )

    SQLALCHEMY_DATABASE_URI = _mariadb_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DESCRIPTION_DIR = os.environ.get("DESCRIPTION_DIR", str(BASE_DIR / "instance" / "graderfiles"))
    RESOURCE_DIR = os.environ.get("RESOURCE_DIR", str(BASE_DIR / "instance" / "resourcefiles"))
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
    AUTO_CREATE_DB = _env_bool("AUTO_CREATE_DB", True)
    SEED_DATABASE = _env_bool("SEED_DATABASE", True)
