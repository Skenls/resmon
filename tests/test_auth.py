import base64
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import get_settings

@pytest.fixture(autouse=True)
def configure_auth():
    settings = get_settings()
    orig_enabled = settings.AUTH_ENABLED
    orig_user = settings.AUTH_USERNAME
    orig_pass = settings.AUTH_PASSWORD

    settings.AUTH_ENABLED = True
    settings.AUTH_USERNAME = "admin"
    settings.AUTH_PASSWORD = "secretpassword"

    yield

    settings.AUTH_ENABLED = orig_enabled
    settings.AUTH_USERNAME = orig_user
    settings.AUTH_PASSWORD = orig_pass

def test_unauthorized_request_returns_401_challenge():
    with TestClient(app) as client:
        response = client.get("/api/info")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        assert "Basic" in response.headers["WWW-Authenticate"]

def test_invalid_credentials_returns_401():
    with TestClient(app) as client:
        auth_header = "Basic " + base64.b64encode(b"admin:wrongpass").decode()
        response = client.get("/api/info", headers={"Authorization": auth_header})
        assert response.status_code == 401

def test_valid_credentials_returns_200_and_sets_cookie():
    with TestClient(app) as client:
        auth_header = "Basic " + base64.b64encode(b"admin:secretpassword").decode()
        response = client.get("/api/info", headers={"Authorization": auth_header})
        assert response.status_code == 200
        assert "hostname" in response.json()
        assert "resmon_session" in response.cookies

@pytest.mark.timeout(5)
def test_websocket_requires_auth():
    with TestClient(app) as client:
        # Without auth cookie or header, WS connect should fail or close
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/metrics") as ws:
                ws.receive_json()

@pytest.mark.timeout(5)
def test_websocket_with_authenticated_session_cookie():
    with TestClient(app) as client:
        # Authenticate first via REST
        auth_header = "Basic " + base64.b64encode(b"admin:secretpassword").decode()
        res = client.get("/api/health", headers={"Authorization": auth_header})
        assert res.status_code == 200
        assert "resmon_session" in client.cookies

        # Connect to websocket carrying session cookie
        with client.websocket_connect("/ws/metrics") as ws:
            data = ws.receive_json()
            assert "timestamp" in data
            assert "cpu" in data

def test_bruteforce_lockout():
    with TestClient(app) as client:
        auth_header = "Basic " + base64.b64encode(b"admin:wrongpass").decode()
        for _ in range(5):
            res = client.get("/api/info", headers={"Authorization": auth_header})
            assert res.status_code == 401

        # 6th attempt should be rate-limited with 429
        res = client.get("/api/info", headers={"Authorization": auth_header})
        assert res.status_code == 429
        assert "locked out" in res.json()["detail"]

