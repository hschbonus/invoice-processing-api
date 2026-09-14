from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_application_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["environment"] in {"development", "test", "production"}
