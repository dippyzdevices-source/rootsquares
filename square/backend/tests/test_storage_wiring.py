"""Tests for storage wiring (1 tests), e.g. testing config uses a fake storage service."""
from app import create_app
from app.storage.service import FakeStorageService, get_public_storage


def test_testing_config_uses_a_fake_storage_service():
    app = create_app("testing")
    with app.app_context():
        assert isinstance(get_public_storage(), FakeStorageService)
