"""Native epistemic-graph media ingestion — Wire-First live-path coverage.

Exercises the real ``ingest_media_file`` seam with a fake ingest *transport*
(no engine required) so the SDK's own request-building/validation contract
runs on top of it, and asserts the download path invokes it.
CONCEPT:AU-KG.ingest.list-durable-media.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import threading
from types import SimpleNamespace

import pytest
from agent_connector_sdk.ingest import KnowledgeIngest

from media_downloader.kg_media import ingest_media_file


class _FakeTransport:
    """Captures the committed request; stores blobs content-addressed."""

    def __init__(self):
        self.requests = []

    async def source_status(self, connector, stream):
        return SimpleNamespace(accepted_checkpoint=None)

    async def submit(self, request):
        self.requests.append(request)
        return SimpleNamespace(
            affected_count=len(request.records),
            relationship_count=len(request.relationships),
        )

    async def store_blob(self, data):
        return hashlib.sha256(data).hexdigest()


def _background_loop() -> asyncio.AbstractEventLoop:
    """A dedicated loop+thread, mirroring how the real engine client connects."""
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    return loop


@pytest.fixture
def ingest():
    transport = _FakeTransport()
    loop = _background_loop()
    service = KnowledgeIngest(transport, loop=loop)
    yield service, transport
    loop.call_soon_threadsafe(loop.stop)


def test_ingest_media_file_stores_bytes_and_metadata(tmp_path, ingest):
    service, transport = ingest
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"\x00\x01video-bytes\x02")
    digest = hashlib.sha256(f.read_bytes()).hexdigest()

    res = ingest_media_file(
        str(f),
        info={"id": "abc123", "title": "Clip", "uploader": "Chan", "duration": 5},
        source_url="https://example.test/watch?v=abc123",
        ingest=service,
    )

    assert res is not None
    assert res["asset_id"] == f"blob:{digest}"
    assert res["digest"] == digest
    assert res["media_type"] == "video"
    assert res["size_bytes"] == f.stat().st_size

    # One request, carrying exactly one record: the stored media asset.
    assert len(transport.requests) == 1
    record = transport.requests[0].records[0]
    assert record.record_id == f"blob:{digest}"
    assert record.payload["mime_type"] == "video/mp4"
    assert record.payload["blob_digest"] == digest
    # Title is preferred for the display name when present; the KG still
    # captures the richer id/title/uploader metadata.
    assert record.payload["name"] == "Clip"
    assert record.payload["id"] == "abc123"
    assert record.payload["title"] == "Clip"
    assert record.payload["uploader"] == "Chan"
    # The SDK's PersistencePrivacyGuard treats "source_url" as a location
    # field and redacts it outright (our own scheme+host truncation in
    # public_source_url() no longer matters for this specific key).
    assert record.payload["source_url"] == "[REDACTED_LOCATION]"


def test_ingest_media_file_name_falls_back_without_title(tmp_path, ingest):
    service, transport = ingest
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"\x00\x01video-bytes\x02")

    ingest_media_file(str(f), info={"id": "abc123", "duration": 5}, ingest=service)

    record = transport.requests[0].records[0]
    assert record.payload["name"] == "media-abc123"


def test_ingest_media_file_noops_without_engine(tmp_path, monkeypatch):
    """No injected service + no configured engine -> clean no-op (never raises)."""
    monkeypatch.delenv("EPISTEMIC_GRAPH_ENDPOINT", raising=False)
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")
    assert ingest_media_file(str(f)) is None


def test_ingest_media_file_noops_on_missing_file(ingest):
    service, _transport = ingest
    assert ingest_media_file("/no/such/file.mp4", ingest=service) is None


def test_download_video_invokes_native_ingest(monkeypatch, tmp_path):
    """The download path natively calls ingestion and records the asset."""
    from media_downloader.media_downloader import MediaDownloader

    dl = MediaDownloader(
        download_directory=str(tmp_path),
        output_root=str(tmp_path),
        ingest_to_kg=True,
    )
    captured = {}

    def _fake_ingest(path, **kw):
        captured["path"] = path
        captured["kw"] = kw
        return {"asset_id": "media:x", "digest": "x", "size_bytes": 1, "media_type": "video"}

    monkeypatch.setattr("media_downloader.kg_media.ingest_media_file", _fake_ingest)
    dl._maybe_ingest("/tmp/out.mp4", {"id": "z"}, "https://example.test/z")

    assert captured["path"] == "/tmp/out.mp4"
    assert dl.last_kg_asset == {
        "asset_id": "media:x",
        "digest": "x",
        "size_bytes": 1,
        "media_type": "video",
    }


def test_ingest_disabled_when_flag_off(tmp_path):
    from media_downloader.media_downloader import MediaDownloader

    dl = MediaDownloader(
        download_directory=str(tmp_path),
        output_root=str(tmp_path),
        ingest_to_kg=False,
    )
    dl._maybe_ingest("/tmp/out.mp4", {}, "u")
    assert dl.last_kg_asset is None
    assert os.path.basename(__file__) == "test_kg_media.py"
