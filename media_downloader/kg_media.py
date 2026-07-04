"""Native epistemic-graph ingestion for downloaded media.

CONCEPT:AU-KG.ingest.list-durable-media. When a live epistemic-graph engine is
reachable, a downloaded file is stored as a content-addressed **blob** with a
``:MediaAsset`` graph node (carrying its yt-dlp metadata) in ONE cross-modal ACID
commit, via the agent-utilities ``MediaStore``. This makes the raw bytes — not just
a filesystem path — durable, deduped, and queryable inside the knowledge graph.

Entirely best-effort and dependency-guarded: if agent-utilities' KG stack or a live
engine is not present, every entry point here **no-ops** (returns ``None``), so the
downloader keeps working with zero KG infrastructure. This is the native ingestion
seam the ``media-downloader`` package contributes to the KG — the downloader calls it
automatically after each successful download.
"""

from __future__ import annotations

import logging
import mimetypes
import os
from typing import Any

logger = logging.getLogger("MediaDownloader.kg")

# yt-dlp info keys worth carrying onto the :MediaAsset node.
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


def _media_store() -> Any | None:
    """Build a ``MediaStore`` over a live engine, or ``None`` when unavailable."""
    try:
        from agent_utilities.knowledge_graph.core.graph_compute import (
            GraphComputeEngine,
        )
        from agent_utilities.knowledge_graph.memory.media_store import MediaStore
    except Exception as e:  # noqa: BLE001 — agent-utilities KG stack absent
        logger.debug("KG media ingest unavailable (import): %s", e)
        return None
    try:
        engine = GraphComputeEngine()
        if getattr(engine, "_client", None) is None:
            logger.debug("KG media ingest: no live engine client")
            return None
        return MediaStore(engine)
    except Exception as e:  # noqa: BLE001 — no reachable engine
        logger.debug("KG media ingest: engine unreachable: %s", e)
        return None


def ingest_media_file(
    file_path: str | None,
    *,
    info: dict[str, Any] | None = None,
    source_url: str = "",
    source: str = "media-downloader",
    media_store: Any | None = None,
) -> dict[str, Any] | None:
    """Store a downloaded file as a blob + ``:MediaAsset`` in the knowledge graph.

    Returns ``{asset_id, digest, size_bytes, media_type}`` on success, or ``None``
    when there is no engine, no file, or the store failed (never raises).
    ``media_store`` may be injected (tests); otherwise one is built on demand.
    """
    if not file_path or not os.path.exists(file_path):
        return None
    store = media_store if media_store is not None else _media_store()
    if store is None:
        return None

    info = info or {}
    mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    if mime.startswith("audio"):
        media_type = "audio"
    elif mime.startswith("video"):
        media_type = "video"
    elif mime.startswith("image"):
        media_type = "image"
    else:
        media_type = "file"

    try:
        with open(file_path, "rb") as fh:
            data = fh.read()
    except OSError as e:
        logger.warning("KG media ingest: cannot read %s: %s", file_path, e)
        return None

    extra = {k: info[k] for k in _INFO_FIELDS if info.get(k) is not None}
    if source_url:
        extra["source_url"] = source_url
    name = info.get("title") or os.path.basename(file_path)

    try:
        stored = store.store_media(
            data,
            media_type=media_type,
            mime_type=mime,
            source=source,
            name=name,
            extra=extra,
        )
    except Exception as e:  # noqa: BLE001 — engine/store failure is non-fatal
        logger.warning("KG media ingest: store_media failed: %s", e)
        return None
    if stored is None:
        return None

    logger.info(
        "KG media ingest: stored %s (%s bytes) as asset %s digest %s",
        name,
        len(data),
        stored.asset_id,
        stored.digest[:16],
    )
    return {
        "asset_id": stored.asset_id,
        "digest": stored.digest,
        "size_bytes": len(data),
        "media_type": media_type,
    }
