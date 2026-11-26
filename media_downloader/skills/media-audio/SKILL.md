---
name: media-audio
skill_type: skill
description: >-
  Extract audio as MP3 from a video/media URL via the media-downloader MCP server,
  natively storing the resulting audio into medulla as a content-addressed
  blob + :MediaAsset. Use when the agent needs the audio track (podcast, music,
  lecture) rather than the full video. Do NOT use for full-video download
  (media-download) or for transcription (use the audio-transcriber package).
license: MIT
tags: [media-downloader, audio, mp3, yt-dlp, kg-ingest, mcp]
metadata:
  author: Knuckles-Team
  version: '0.1.0'
---
# Media Audio

Extract the audio track of a media URL to MP3 and durably store it in the KG.

## When to use
- Pull just the audio (MP3) from a video/media URL.
- Persist the audio bytes + metadata into medulla as a `:MediaAsset`.

## When NOT to use
- Full-video download → `media-download`.
- Speech-to-text transcription → the `audio-transcriber` package.

## Prerequisites & environment
Connect via the `mcp-client` skill against the **`media-downloader`** MCP server.
Requires `ffmpeg` on the server for MP3 extraction. `GRAPH_SERVICE_ENDPOINTS`
(optional) enables native KG ingestion; it auto-no-ops when absent.

## Steps

1. Confirm the server is ready for MP3 extraction by checking `ffmpeg -version` on the server host, and verify a version line is printed.
2. Call `download_media` with `video_url`, `audio_only` set to true and a `download_directory`, and verify the response status reports success.
3. Check the `file` field of the response, and verify the path ends in `.mp3` inside `download_directory`.
4. Inspect `kg_asset` in the response, and verify `media_type` is `audio` when an engine endpoint is configured.

## Failure recovery

| Failure | Cause | Recovery |
|---|---|---|
| The saved file is not an MP3 | `ffmpeg` is missing on the server | Install `ffmpeg` on the server host and call `download_media` again with `audio_only` true |
| `kg_asset` is absent | `GRAPH_SERVICE_ENDPOINTS` is unset or unreachable | Set `GRAPH_SERVICE_ENDPOINTS` to a reachable engine endpoint, or accept the file-only result |
| The call returns an error for the URL | The URL is private, unsupported or blocked by the security policy | Pass a public URL from a site supported by yt-dlp |

## Tools & actions
| Tool | Purpose |
|------|---------|
| `download_media` | Set `audio_only=true` to extract MP3; returns `{status, file, kg_asset?}` |

### Key parameters
- `video_url` — the media URL (required).
- `audio_only` — **true** for this skill.
- `download_directory` — where to save the MP3 (default `.`).

## Recipes
Extract audio and store it in the KG:
```json
{"video_url":"https://www.youtube.com/watch?v=<id>","audio_only":true,"download_directory":"/data/audio"}
```

## Gotchas
- MP3 extraction needs `ffmpeg`; without it the download falls back to the source container.
- The stored `:MediaAsset` `media_type` is `audio` (mime `audio/mpeg`).
- Native ingestion is best-effort — no engine → file still saved, `kg_asset` absent.

## Related
- Reuses the shared **media** ontology federated by jellyfin-mcp.
- Pairs with the `audio-transcriber` package to turn stored audio into transcripts.
