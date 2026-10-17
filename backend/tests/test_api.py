import pytest
from fastapi.testclient import TestClient

from iou.api import app

client = TestClient(app)


def test_health_without_database():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "informal-obligations-utility"}


def test_hello():
    assert client.get("/hello").json() == {"message": "Hello from IOU"}


def test_random_demo_bounds():
    assert client.get("/random", params={"maximum": 0}).json() == {"itemId": 0}
    value = client.get("/random", params={"maximum": 100}).json()["itemId"]
    assert 0 <= value <= 100


@pytest.mark.parametrize("maximum", [-1, 1_000_001, "not-a-number"])
def test_random_demo_rejects_invalid_input(maximum):
    assert client.get("/random", params={"maximum": maximum}).status_code == 422


def test_random_demo_requires_maximum():
    assert client.get("/random").status_code == 422
