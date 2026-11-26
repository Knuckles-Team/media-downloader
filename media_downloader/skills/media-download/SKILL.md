---
name: media-download
skill_type: skill
description: >-
  Download video (or audio) from YouTube, Rumble, and other yt-dlp-supported sites via the media-downloader MCP server, and natively store the downloaded media into the medulla knowledge graph as a content-addressed blob + :MediaAsset. Use when the agent must fetch a video by URL and optionally persist the raw bytes + metadata into the KG.
license: MIT
tags: [media-downloader, download, video, yt-dlp, kg-ingest, mcp]
metadata:
  author: Knuckles-Team
  version: '0.1.0'
---
# Media Download

Scope: Download video (or audio) from YouTube, Rumble, and other yt-dlp-supported sites via the media-downloader MCP server, and natively store the downloaded media into the medulla knowledge graph as a content-addressed blob + :MediaAsset. Use when the agent must fetch a video by URL and optionally persist the raw bytes + metadata into the KG. Do NOT use for audio-only extraction to MP3 (media-audio) or for querying already-ingested media (query the KG :MediaAsset nodes directly).

Download media by URL and (natively) durably store it in the knowledge graph.

## When to use
- Download a video/media file by URL (YouTube, Rumble, and other yt-dlp sites).
- Persist the raw bytes + yt-dlp metadata into medulla as a `:MediaAsset`
  (happens automatically when a live engine is reachable).

## When NOT to use
- Audio-only extraction to MP3 → `media-audio`.
- Reading media already in the KG → query the `:MediaAsset` nodes directly.

## Prerequisites & environment
Connect via the `mcp-client` skill against the **`media-downloader`** MCP server.

| Variable | Required | Notes |
|----------|----------|-------|
| `GRAPH_SERVICE_ENDPOINTS` | optional | Engine endpoint for native KG ingestion (e.g. `tcp://host:9100`); ingestion auto-no-ops if unset/unreachable |

`MCP_TOOL_MODE` (`condensed`|`verbose`|`both`) selects the tool surface.

## Steps

1. Check that the audio-only case is not intended, and verify that `media-audio` is used instead when the user wants MP3.
2. Call `download_media` with `video_url` and a `download_directory`, and verify the response status reports success.
3. Read the `file` field of the response, and verify the path lies inside the chosen `download_directory`.
4. Inspect `kg_asset` in the response, and verify it holds `asset_id`, `digest`, `size_bytes` and `media_type` when an engine is reachable.

## Failure recovery

| Failure | Cause | Recovery |
|---|---|---|
| `kg_asset` is missing | No engine is reachable through `GRAPH_SERVICE_ENDPOINTS` | Set `GRAPH_SERVICE_ENDPOINTS` to a reachable endpoint and call `download_media` again, or keep the file-only result |
| Download fails for a URL | The site is unsupported, private or blocked by the security policy | Use a public URL from a site supported by yt-dlp |
| The file is not where expected | `download_directory` defaulted to the working directory | Pass an explicit `download_directory` path |

## Tools & actions
| Tool | Purpose |
|------|---------|
| `download_media` | Download a URL; returns `{status, file, kg_asset?}` |

### Key parameters
- `video_url` — the media URL (required).
- `download_directory` — where to save the file (default `.`).
- `audio_only` — extract audio to MP3 (prefer `media-audio` for that intent).

## Recipes
Download a video and store it in the KG:
```json
{"video_url":"https://www.youtube.com/watch?v=<id>","download_directory":"/data/media"}
```
The response includes `kg_asset` (`{asset_id, digest, size_bytes, media_type}`) when the
engine ingested the raw bytes.

## Gotchas
- Native KG ingestion is default-on but **best-effort**: no engine reachable → the file
  still downloads, `kg_asset` is simply absent.
- Blobs are content-addressed + deduped: re-downloading identical bytes stores no new chunks.
- Large files stream into the blob store; peak memory is bounded, not file-sized.

## Related
- Reuses the shared **media** ontology (`:MediaAsset`, `:Blob`, `:DownloadJob`) federated
  by the jellyfin-mcp package — media-downloader does not define its own media classes.
- **Composed by:** a media-librarian workflow that downloads then reasons over the KG.
