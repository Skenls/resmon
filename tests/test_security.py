import pytest
from starlette.requests import Request

from backend.auth import get_client_ip
from backend.config import Settings, validate_security
from backend.main import resolve_spa_file


def test_spa_path_traversal_falls_back_to_index():
    result = resolve_spa_file("../../backend/config.py")
    assert result.endswith("index.html")


def test_spa_unknown_file_falls_back_to_index():
    result = resolve_spa_file("assets/nope.js")
    assert result.endswith("index.html")


def test_validate_security_rejects_empty_password():
    settings = Settings(AUTH_ENABLED=True, AUTH_PASSWORD="", SECRET_KEY="x" * 40)
    with pytest.raises(RuntimeError):
        validate_security(settings)


def test_validate_security_rejects_known_secret():
    settings = Settings(
        AUTH_ENABLED=True,
        AUTH_PASSWORD="x" * 20,
        SECRET_KEY="resmon-default-secret-change-in-production",
    )
    with pytest.raises(RuntimeError):
        validate_security(settings)


def test_validate_security_accepts_strong_values():
    settings = Settings(AUTH_ENABLED=True, AUTH_PASSWORD="x" * 20, SECRET_KEY="y" * 40)
    validate_security(settings)


def test_validate_security_allows_explicitly_disabled_auth():
    settings = Settings(AUTH_ENABLED=False, AUTH_PASSWORD="", SECRET_KEY="")
    validate_security(settings)


def test_client_ip_ignores_forwarded_header():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", b"1.2.3.4")],
            "client": ("5.6.7.8", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )
    assert get_client_ip(request) == "5.6.7.8"
