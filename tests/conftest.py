"""Shared test fixtures for Media Downloader."""

import pytest


@pytest.fixture
def mock_env(monkeypatch):
    """Set standard test environment variables."""
    monkeypatch.setenv("MEDIA_URL", "https://test.example.com")
    monkeypatch.setenv("MEDIA_TOKEN", "test-token-12345")
    monkeypatch.setenv("MEDIA_SSL_VERIFY", "False")
