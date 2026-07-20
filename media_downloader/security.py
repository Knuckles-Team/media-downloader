"""Network and filesystem trust boundaries for media ingestion."""

from __future__ import annotations

import ipaddress
import os
import socket
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

_MAX_REDIRECTS = 5
_MAX_METADATA_BYTES = 2 * 1024 * 1024


class MediaSecurityError(ValueError):
    """Raised when a media request crosses an administrator-defined boundary."""


def _private_host_allowlist() -> set[str]:
    hosts: set[str] = set()
    for item in os.environ.get("MEDIA_DOWNLOADER_ALLOW_PRIVATE_HOSTS", "").split(","):
        host = item.strip().lower().rstrip(".")
        if not host:
            continue
        if any(char in host for char in "*/:@"):
            raise MediaSecurityError("Private-host allowlist entries must be exact hosts")
        hosts.add(host)
    return hosts


def validate_media_url(url: str) -> str:
    """Validate an HTTP(S) URL and resolve every address before network access."""
    if not isinstance(url, str) or len(url) > 8_192 or "\x00" in url:
        raise MediaSecurityError("Invalid media URL")
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise MediaSecurityError("Only HTTP(S) media URLs are permitted")
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise MediaSecurityError("Media URLs may not contain credentials")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise MediaSecurityError("Invalid media URL port") from exc
    host = parsed.hostname.lower().rstrip(".")
    allowed_private = host in _private_host_allowlist()
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise MediaSecurityError("Media host could not be resolved") from exc
    if not addresses:
        raise MediaSecurityError("Media host did not resolve")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError as exc:
            raise MediaSecurityError("Media host resolved to an invalid address") from exc
        if not ip.is_global and not allowed_private:
            raise MediaSecurityError("Media URL resolves to a non-public address")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, ""))


def safe_metadata_get(url: str, *, timeout: float = 10.0) -> requests.Response:
    """GET a small metadata page with manual, revalidated redirects."""
    current = validate_media_url(url)
    for _ in range(_MAX_REDIRECTS + 1):
        response = requests.get(
            current,
            timeout=timeout,
            allow_redirects=False,
            stream=True,
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("location")
            response.close()
            if not location:
                raise MediaSecurityError("Media redirect omitted its destination")
            current = validate_media_url(urljoin(current, location))
            continue
        response.raise_for_status()
        payload = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            payload.extend(chunk)
            if len(payload) > _MAX_METADATA_BYTES:
                response.close()
                raise MediaSecurityError("Media metadata response exceeded its size limit")
        response._content = bytes(payload)  # bounded body for existing callers
        response.url = current
        return response
    raise MediaSecurityError("Media redirect limit exceeded")


def resolve_output_directory(
    requested: str | None, *, output_root: str | None = None
) -> tuple[Path, Path]:
    """Resolve a download directory beneath a stable administrator-owned root."""
    configured_root = (
        output_root
        or os.environ.get("MEDIA_DOWNLOADER_OUTPUT_ROOT")
        or os.environ.get("WORKSPACE_PATH")
        or str(Path.home() / "Downloads")
    )
    raw_root = Path(configured_root).expanduser()
    if raw_root.is_symlink():
        raise MediaSecurityError("Media output root may not be a symbolic link")
    raw_root.mkdir(parents=True, exist_ok=True)
    root = raw_root.resolve(strict=True)

    candidate = Path(requested).expanduser() if requested else root
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise MediaSecurityError("Download directory is outside the media output root") from exc
    candidate.mkdir(parents=True, exist_ok=True)
    candidate = candidate.resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise MediaSecurityError("Download directory escaped through a symbolic link") from exc
    return root, candidate


def contained_output_path(path: str, root: Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise MediaSecurityError("Downloader produced a path outside its output root") from exc
    return candidate


def public_source_url(url: str) -> str:
    """Retain only a source origin before persisting provenance."""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, "", "", ""))
