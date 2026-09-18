import os
from backend.config import get_settings

def test_settings_defaults():
    settings = get_settings()
    assert settings.PORT == 8080
    assert settings.HOST == "0.0.0.0"
    assert settings.UPDATE_INTERVAL == 1.0
    assert settings.HISTORY_POINTS == 900
    assert settings.HOST_PROC in ["/host/proc", "/proc"]
    assert settings.HOST_SYS in ["/host/sys", "/sys"]
    assert settings.LOG_LEVEL == "info"
