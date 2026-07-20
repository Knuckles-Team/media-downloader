"""Native epistemic-graph media ingestion — Wire-First live-path coverage.

Exercises the real ``ingest_media_file`` seam with a fake ``MediaStore`` (no engine
required) and asserts the download path invokes it. CONCEPT:AU-KG.ingest.list-durable-media.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from media_downloader.kg_media import ingest_media_file


@dataclass
class _Stored:
    asset_id: str
    digest: str


class _FakeMediaStore:
    """Captures the store_media call the way the real MediaStore is invoked."""

    def __init__(self):
        self.calls = []

    def store_media(self, data, **kw):
        self.calls.append((data, kw))
        return _Stored(asset_id="media:deadbeef", digest="deadbeef")


def test_ingest_media_file_stores_bytes_and_metadata(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"\x00\x01video-bytes\x02")
    store = _FakeMediaStore()

    res = ingest_media_file(
        str(f),
        info={"id": "abc123", "title": "Clip", "uploader": "Chan", "duration": 5},
        source_url="https://example.test/watch?v=abc123",
        media_store=store,
    )

    assert res is not None
    assert res["asset_id"] == "media:deadbeef"
    assert res["digest"] == "deadbeef"
    assert res["media_type"] == "video"
    assert res["size_bytes"] == f.stat().st_size

    # store_media was called with the raw bytes + the propagated metadata.
    assert len(store.calls) == 1
    data, kw = store.calls[0]
    assert data == f.read_bytes()
    assert kw["source"] == "media-downloader"
    assert kw["mime_type"] == "video/mp4"
    assert kw["name"] == "media-abc123"
    assert kw["extra"]["id"] == "abc123"
    assert "title" not in kw["extra"]
    assert "uploader" not in kw["extra"]
    assert kw["extra"]["source_url"] == "https://example.test"


def test_ingest_media_file_noops_without_engine(tmp_path):
    """No injected store + no reachable engine -> clean no-op (never raises)."""
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")
    # media_store defaults to _media_store(), which returns None with no engine.
    assert ingest_media_file(str(f)) is None


def test_ingest_media_file_noops_on_missing_file():
    assert ingest_media_file("/no/such/file.mp4", media_store=_FakeMediaStore()) is None


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
