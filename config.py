from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1200
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    UPLOAD_ROOT: str = "uploads"
    ENVIRONMENT: str = "development"

    CLIENT_DOCUMENTS_ENABLED: bool = False
    MALWARE_SCAN_ENFORCED: bool = False
    EMAIL_RECOVERY_ENABLED: bool = False

    ZEPTO_API_KEY: str = ""
    ZEPTO_BASE_URL: str = ""
    ZEPTO_SENDER_EMAIL: str = ""
    ZEPTO_SENDER_NAME: str = "SaffoCare"
    FRONTEND_URL: str = "http://localhost:5173"

    DOCUMENT_UPLOAD_LINK_EXPIRY_HOURS: int = 72
    DOCUMENT_MAX_FILE_SIZE_MB: int = 5
    LEGAL_PRIVATE_UPLOAD_DIR: str = "private_uploads/legal_documents"

    EMAIL_REQUEST_TIMEOUT_SECONDS: int = 15
    EMAIL_MAX_RETRIES: int = 3
    EMAIL_RETRY_DELAY_SECONDS: int = 5
    EMAIL_RECOVERY_INTERVAL_SECONDS: int = 60
    EMAIL_PROCESSING_LEASE_SECONDS: int = 120
    EMAIL_PAYLOAD_ENCRYPTION_KEY: str = ""

    @property
    def email_configured(self) -> bool:
        return bool(
            self.ZEPTO_API_KEY.strip()
            and self.ZEPTO_BASE_URL.strip()
            and self.ZEPTO_SENDER_EMAIL.strip()
            and self.EMAIL_PAYLOAD_ENCRYPTION_KEY.strip()
        )


def _validate_settings(value: Settings) -> Settings:
    if value.DOCUMENT_UPLOAD_LINK_EXPIRY_HOURS < 1:
        raise ValueError("DOCUMENT_UPLOAD_LINK_EXPIRY_HOURS must be positive")
    if value.DOCUMENT_MAX_FILE_SIZE_MB < 1:
        raise ValueError("DOCUMENT_MAX_FILE_SIZE_MB must be positive")
    if value.EMAIL_REQUEST_TIMEOUT_SECONDS < 1:
        raise ValueError("EMAIL_REQUEST_TIMEOUT_SECONDS must be positive")
    if value.EMAIL_MAX_RETRIES < 0:
        raise ValueError("EMAIL_MAX_RETRIES must be zero or positive")
    if value.EMAIL_RETRY_DELAY_SECONDS < 1:
        raise ValueError("EMAIL_RETRY_DELAY_SECONDS must be positive")
    frontend = (value.FRONTEND_URL or "").strip()
    if value.ENVIRONMENT.lower() == "production":
        if not frontend.startswith("https://"):
            raise ValueError("FRONTEND_URL must use HTTPS in production")
        base = (value.ZEPTO_BASE_URL or "").strip()
        if base and not base.startswith("https://"):
            raise ValueError("ZEPTO_BASE_URL must use HTTPS in production")
    return value


settings = _validate_settings(Settings())
