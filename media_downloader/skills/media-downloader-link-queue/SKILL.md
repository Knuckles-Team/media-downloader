---
name: media-downloader-link-queue
skill_type: skill
description: >-
  Find a channel's videos, queue links and download video or audio from supported sites.
  Do NOT use for tasks outside the media-downloader connector.
license: MIT
tags: [media-downloader, mcp]
metadata:
  author: Knuckles-Team
  version: '1.0.0'
---

# Media downloads

Use the typed tools of the `media-downloader` connector: one tool per upstream API operation, named `<operation>`. Each tool takes typed parameters; there is no `action` or `params_json` routing.

## Steps

1. List what exists first with `media_downloader_get_channel_videos` using `channel` and `limit`, and verify the returned videos match the channel asked for.
2. Download one link with `media_downloader_download_video` using `link`, and verify the response reports a saved file.
3. Download a URL by type with `download_media`, setting `audio_only` when audio is wanted, and verify the `file` field points inside `download_directory`.
4. Run `media_downloader_download_all` only when the whole queue is intended, and verify the reported count matches the queued links.

## Failure recovery

| Failure | Cause | Recovery |
|---|---|---|
| `media_downloader_get_channel_videos` returns nothing | The channel value is wrong or the channel has no public videos | Pass the channel in the form the site uses and check the `limit` value |
| A download is refused | The URL is private or blocked by the security policy | Report the refusal as returned and use a public URL |
| Output lands in an unexpected place | `MEDIA_DOWNLOADER_OUTPUT_ROOT` or `download_directory` is not set | Set `MEDIA_DOWNLOADER_OUTPUT_ROOT` for the server or pass `download_directory` |

## Where the data lives

- **media-channel-videos** (`MEDIA_DOWNLOADER_OUTPUT_ROOT`): holds MediaOccurrence; read with `media_downloader_get_channel_videos`.
- **media-watch-skills** (`MEDIA_DOWNLOADER_SKILLS_DIR`): holds MediaArtifact; read with `list_watch_skills`.

## Workflows (tool-use contracts)

Each workflow is a tool-use contract in the connector ontology. Run the steps in order; read before you write.

### `media-downloader-manage-link-download`

1. `download_media` (`audio_only`, `download_directory`, `video_url`) - Download media.
2. `media_downloader_download_all` (no parameters) - Run media downloader download all.
3. `media_downloader_download_video` (`extra_opts`, `link`) - Run media downloader download video.

### `media-downloader-inspect-channel`

1. `media_downloader_get_channel_videos` (`channel`, `limit`) - Run media downloader get channel videos.

## Guardrails

- Read before you write: list what exists (channel videos, watch skills) before downloading.
- Download only content the operator is entitled to fetch; stay inside the configured output root.
- Never print cookies, tokens or private source URLs.
- Report a tool refusal or HTTP error as it is; never retry past a refusal or invent a result.
