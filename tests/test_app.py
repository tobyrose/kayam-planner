from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_homepage_renders_foundation(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Kayam Seasonal Planning System" in response.text
    assert "Planner ready" in response.text
