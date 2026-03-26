from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_health_check_includes_services():
    response = client.get("/health")
    data = response.json()
    assert "services" in data
    assert "database" in data["services"]
    assert "redis" in data["services"]
