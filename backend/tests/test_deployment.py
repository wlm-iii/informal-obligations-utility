"""Exercise the Docker ASGI mount using a temporary frontend build stand-in."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def deployed_client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    public = tmp_path / "public"
    public.mkdir()
    (public / "index.html").write_text("<html>IOU test shell</html>")
    (public / "asset.txt").write_text("static asset")
    # Deployment entry point requires built frontend assets at import time.
    from main import app

    with TestClient(app) as client:
        yield client


def test_hosted_api_prefix(deployed_client):
    response = deployed_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_api_route_is_not_html(deployed_client):
    response = deployed_client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_spa_fallback(deployed_client):
    response = deployed_client.get("/future-ui-route")
    assert response.status_code == 200
    assert "IOU test shell" in response.text


def test_static_asset(deployed_client):
    assert deployed_client.get("/asset.txt").text == "static asset"
