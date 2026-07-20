"""Adversarial source tests for media egress and output containment."""

import socket
from unittest.mock import MagicMock, patch

import pytest

from media_downloader.security import (
    MediaSecurityError,
    resolve_output_directory,
    safe_metadata_get,
    validate_media_url,
)


def _addr(ip: str):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]


def test_private_dns_answer_is_rejected():
    with patch("socket.getaddrinfo", return_value=_addr("127.0.0.1")):
        with pytest.raises(MediaSecurityError, match="non-public"):
            validate_media_url("https://media.example/video")


def test_url_credentials_and_non_http_schemes_are_rejected():
    with pytest.raises(MediaSecurityError, match="credentials"):
        validate_media_url("https://user:secret@example.test/video")
    with pytest.raises(MediaSecurityError, match="HTTP"):
        validate_media_url("file:///etc/passwd")


def test_redirect_target_is_revalidated_before_second_request():
    response = MagicMock()
    response.is_redirect = True
    response.is_permanent_redirect = False
    response.headers = {"location": "http://127.0.0.1/admin"}

    def resolve(host, *_args, **_kwargs):
        return _addr("93.184.216.34") if host == "public.example" else _addr("127.0.0.1")

    with (
        patch("socket.getaddrinfo", side_effect=resolve),
        patch("media_downloader.security.requests.get", return_value=response) as get,
    ):
        with pytest.raises(MediaSecurityError, match="non-public"):
            safe_metadata_get("https://public.example/video")
    get.assert_called_once()


def test_output_directory_rejects_parent_and_symlink_escape(tmp_path):
    root = tmp_path / "media"
    root.mkdir()
    with pytest.raises(MediaSecurityError, match="outside"):
        resolve_output_directory("../outside", output_root=str(root))

    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(MediaSecurityError, match="outside|symbolic"):
        resolve_output_directory("link", output_root=str(root))
