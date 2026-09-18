import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PORT: int = 8080
    HOST: str = "0.0.0.0"
    UPDATE_INTERVAL: float = 1.0
    HISTORY_POINTS: int = 900
    HOST_PROC: str = "/host/proc" if os.path.exists("/host/proc") else "/proc"
    HOST_SYS: str = "/host/sys" if os.path.exists("/host/sys") else "/sys"
    LOG_LEVEL: str = "info"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
