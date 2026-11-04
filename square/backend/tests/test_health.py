"""Tests for health (1 tests), e.g. health returns ok status."""
import pytest

from app import create_app


@pytest.fixture()
def client():
    app = create_app("testing")
    return app.test_client()


def test_health_returns_ok_status(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
