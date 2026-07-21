# Media Audio

Extract audio as MP3 from a video/media URL via the media-downloader MCP server, natively storing the resulting audio into epistemic-graph as a content-addressed blob + :MediaAsset. Use when the agent needs the audio track (podcast, music, lecture) rather than the full video. Do NOT use for full-video download (media-download) or for transcription (use the audio-transcriber package).

# Media Audio

Extract the audio track of a media URL to MP3 and durably store it in the KG.

## When to use
- Pull just the audio (MP3) from a video/media URL.
- Persist the audio bytes + metadata into epistemic-graph as a `:MediaAsset`.

## When NOT to use
- Full-video download → `media-download`.
- Speech-to-text transcription → the `audio-transcriber` package.

## Prerequisites & environment
Connect via the `mcp-client` skill against the **`media-downloader`** MCP server.
Requires `ffmpeg` on the server for MP3 extraction. `GRAPH_SERVICE_ENDPOINTS`
(optional) enables native KG ingestion; it auto-no-ops when absent.

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
{"video_url":"[configured-endpoint]>","audio_only":true,"download_directory":"/data/audio"}
```

## Gotchas
- MP3 extraction needs `ffmpeg`; without it the download falls back to the source container.
- The stored `:MediaAsset` `media_type` is `audio` (mime `audio/mpeg`).
- Native ingestion is best-effort — no engine → file still saved, `kg_asset` absent.

## Related
- Reuses the shared **media** ontology federated by jellyfin-mcp.
- Pairs with the `audio-transcriber` package to turn stored audio into transcripts.
