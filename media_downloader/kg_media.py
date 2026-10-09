"""Native epistemic-graph ingestion for downloaded media.

CONCEPT:AU-KG.ingest.list-durable-media. When a live epistemic-graph engine is
reachable, a downloaded file is stored as a content-addressed **blob** with a
``MediaArtifact`` graph node (carrying its yt-dlp metadata) via the
agent-connector-sdk knowledge-ingest facade. This makes the raw bytes - not
just a filesystem path - durable, deduped, and queryable inside the
knowledge graph.

Entirely best-effort: if no epistemic-graph endpoint is configured, or the
configured engine is unreachable, every entry point here **no-ops** (returns
``None``), so the downloader keeps working with zero KG infrastructure. This
is the native ingestion seam the ``media-downloader`` package contributes to
the KG - the downloader calls it automatically after each successful
download.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
from typing import Any

from agent_connector_sdk.ingest import (
    ChangeSet,
    IngestBinding,
    IngestError,
    KnowledgeIngest,
    MediaAsset,
    ingest_changes,
)

from media_downloader.security import public_source_url

logger = logging.getLogger("MediaDownloader.kg")

# This connector's own manifest declares `MediaArtifact` (not the SDK's generic
# `MediaAsset` default) as the resource a stored media blob becomes.
_BINDING = IngestBinding(
    connector="media-downloader", stream="media", media_type="MediaArtifact"
)

# yt-dlp info keys worth carrying onto the MediaArtifact node.
_INFO_FIELDS = (
    "id",
    "title",
    "uploader",
    "channel",
    "duration",
    "webpage_url",
    "ext",
    "resolution",
    "fps",
    "upload_date",
)


_MIME_PREFIX_TO_MEDIA_TYPE = (
    ("audio", "audio"),
    ("video", "video"),
    ("image", "image"),
)


def _media_type_for_mime(mime: str) -> str:
    for prefix, media_type in _MIME_PREFIX_TO_MEDIA_TYPE:
        if mime.startswith(prefix):
            return media_type
    return "file"


def _read_media_bytes(file_path: str) -> bytes | None:
    try:
        with open(file_path, "rb") as fh:
            return fh.read()
    except OSError as e:
        logger.warning(
            "KG media ingest: cannot read media bytes (%s)", type(e).__name__
        )
        return None


def _media_extra_and_name(
    info: dict[str, Any], source_url: str
) -> tuple[dict[str, Any], str]:
    extra = {k: info[k] for k in _INFO_FIELDS if info.get(k) is not None}
    if extra.get("webpage_url"):
        extra["webpage_url"] = public_source_url(str(extra["webpage_url"]))
    if source_url:
        extra["source_url"] = public_source_url(source_url)
    name = info.get("title") or (
        f"media-{info['id']}" if info.get("id") else "downloaded-media"
    )
    return extra, name


def ingest_media_file(
    file_path: str | None,
    *,
    info: dict[str, Any] | None = None,
    source_url: str = "",
    source: str = "media-downloader",
    ingest: KnowledgeIngest | None = None,
) -> dict[str, Any] | None:
    """Store a downloaded file as a blob + ``MediaArtifact`` in the knowledge graph.

    Returns ``{asset_id, digest, size_bytes, media_type}`` on success, or ``None``
    when there is no engine, no file, or the store failed (never raises).
    ``ingest`` may be injected (tests); otherwise the process's installed/
    configured :class:`KnowledgeIngest` is used via ``submit_blocking`` - safe
    here because the ingest client runs on its own dedicated connection
    thread, never the caller's.
    """
    if not file_path or not os.path.exists(file_path):
        return None

    info = info or {}
    mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    media_type = _media_type_for_mime(mime)

    data = _read_media_bytes(file_path)
    if data is None:
        return None

    extra, name = _media_extra_and_name(info, source_url)
    asset = MediaAsset(data=data, mime_type=mime, name=name, properties=extra)
    change_set = ChangeSet(media=(asset,))

    try:
        if ingest is not None:
            ingest.submit_blocking(_BINDING, change_set)
        else:
            ingest_changes(_BINDING, change_set)
    except IngestError as e:  # no engine configured/reachable, or commit refused
        logger.debug("Operation failed: error_type=%s", type(e).__name__)
        return None
    except Exception as e:  # noqa: BLE001 — never let best-effort ingest fail the download
        logger.warning("Operation failed: error_type=%s", type(e).__name__)
        return None

    digest = hashlib.sha256(data).hexdigest()
    asset_id = asset.id or f"blob:{digest}"
    logger.info(
        "KG media ingest: stored media bytes (%s bytes) as asset %s digest %s",
        len(data),
        asset_id,
        digest[:16],
    )
    return {
        "asset_id": asset_id,
        "digest": digest,
        "size_bytes": len(data),
        "media_type": media_type,
    }
