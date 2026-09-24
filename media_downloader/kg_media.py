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

from media_downloader.security import public_source_url

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


def _media_store(*args: object, **kwargs: object) -> object:
    """Build a ``MediaStore`` over a live engine, or ``None`` when unavailable.

    SDK-GAP: No-op: nothing left to register/write; preserves the graceful-degradation contract.
    """
    return None


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


def _store_media_bytes(
    store: Any,
    data: bytes,
    media_type: str,
    mime: str,
    source: str,
    name: str,
    extra: dict[str, Any],
) -> Any | None:
    try:
        return store.store_media(
            data,
            media_type=media_type,
            mime_type=mime,
            source=source,
            name=name,
            extra=extra,
        )
    except Exception as e:  # noqa: BLE001 — engine/store failure is non-fatal
        logger.warning("Operation failed: error_type=%s", type(e).__name__)
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
    media_type = _media_type_for_mime(mime)

    data = _read_media_bytes(file_path)
    if data is None:
        return None

    extra, name = _media_extra_and_name(info, source_url)

    stored = _store_media_bytes(store, data, media_type, mime, source, name, extra)
    if stored is None:
        return None

    logger.info(
        "KG media ingest: stored media bytes (%s bytes) as asset %s digest %s",
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


class KnowledgeGraphIngestUnavailable(RuntimeError):
    """Direct-to-graph ingestion is unavailable from this connector.

    SDK-GAP (EH-48x, /var/tmp/l9/finish/au-decon-G4c/SDK-GAPS.md): raised in
    place of the old ``agent_utilities.knowledge_graph`` native-ingest call --
    agent-connector-sdk has no facade over EG's typed ingestion protocol yet,
    and the fleet precedent (agents/world-reference-mcp) moves direct-to-graph
    delivery to agent_connector_sdk.runner/sinks at the deployment layer, out
    of connector scope.
    """


def _kg_unavailable(name: str) -> None:
    raise KnowledgeGraphIngestUnavailable(
        f"{name}: direct-to-graph ingestion moved out of connector code "
        "(agent-utilities removed); no agent-connector-sdk facade exists yet "
        "-- see SDK-GAPS.md"
    )
