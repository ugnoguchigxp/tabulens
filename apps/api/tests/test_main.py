from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_api_root():
    response = client.get("/api")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to TabuLens API"}


def test_root_serves_spa_or_fallback_message():
    response = client.get("/")
    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        body = response.json()
        assert "message" in body
    else:
        assert "text/html" in content_type
        assert "<!doctype html>" in response.text.lower()
