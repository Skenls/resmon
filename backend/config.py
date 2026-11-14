import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PORT: int = 8080
    HOST: str = "0.0.0.0"
    UPDATE_INTERVAL: float = 1.0
    HISTORY_POINTS: int = 900
    HOST_PROC: str = "/host/proc" if os.path.exists("/host/proc") else "/proc"
    HOST_UFW: str = "/host/etc/ufw"
    HOST_JOURNAL_DIR: str = "/host/var/log/journal"
    HOST_RUN_JOURNAL_DIR: str = "/host/run/log/journal"
    HOST_SYS: str = "/host/sys" if os.path.exists("/host/sys") else "/sys"
    LOG_LEVEL: str = "info"

    # MCP settings
    MCP_ENABLED: bool = False
    MCP_API_KEY: str = ""

    # Authentication settings
    AUTH_ENABLED: bool = True
    AUTH_USERNAME: str = "admin"
    AUTH_PASSWORD: str = ""
    SECRET_KEY: str = ""
    COOKIE_SECURE: bool = False
    MAX_WS_CLIENTS: int = 100

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


INSECURE_PASSWORDS = {
    "",
    "changeme",
    "password",
    "admin",
    "changeme_to_a_strong_password",
    "replace_with_a_long_random_password",
}
INSECURE_SECRET_KEYS = {
    "",
    "resmon-default-secret-change-in-production",
    "change_this_to_a_random_secret_key_for_sessions",
    "replace_with_a_random_secret_hex",
}


def validate_security(settings: Settings) -> None:
    """Fail closed instead of starting with an open dashboard or forgeable sessions."""
    if not settings.AUTH_ENABLED:
        return
    if settings.AUTH_PASSWORD in INSECURE_PASSWORDS:
        raise RuntimeError("AUTH_PASSWORD is empty or a known placeholder")
    if settings.SECRET_KEY in INSECURE_SECRET_KEYS:
        raise RuntimeError("SECRET_KEY is empty or a known placeholder")


_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
