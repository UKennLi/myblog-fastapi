from pathlib import Path
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str = "myblog_db"
    db_user: str
    db_password: SecretStr
    db_timezone: str = "Asia/Shanghai"
    display_timezone: str = "UTC"
    session_secret: SecretStr
    session_file: Path = ROOT / "state/sessions.sqlite3"
    session_timeout: int = 1800
    cookie_secure: bool = False
    uploads_dir: Path = ROOT / "uploads"
    max_upload_bytes: int = 10 * 1024 * 1024
    db_pool_size: int = 5
    db_max_overflow: int = 10
    legacy_template_js: bool = False
    public_site_url: str = ""

    @field_validator("session_secret")
    @classmethod
    def strong_secret(cls, value):
        if len(value.get_secret_value()) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 characters")
        return value
