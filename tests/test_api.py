import pytest
from fastapi.testclient import TestClient
from backend.main import app

def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

def test_info():
    with TestClient(app) as client:
        response = client.get("/api/info")
        assert response.status_code == 200
        data = response.json()
        assert "hostname" in data
        assert "os" in data
        assert "kernel" in data
        assert "total_memory" in data

def test_history():
    with TestClient(app) as client:
        response = client.get("/api/history")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

def test_spa_serving():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "ResMon Web" in response.text

@pytest.mark.timeout(5)
def test_websocket():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/metrics") as websocket:
            data = websocket.receive_json()
            assert "timestamp" in data
            assert "cpu" in data
            assert "memory" in data

            websocket.send_text("ping")
            pong = websocket.receive_text()
            assert pong == "pong"
