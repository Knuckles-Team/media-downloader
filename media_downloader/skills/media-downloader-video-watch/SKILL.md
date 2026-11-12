---
name: media-downloader-video-watch
skill_type: skill
description: >-
  Download a video with captions, extract scene-change key frames and build or list
  video-derived skills. Do NOT use for tasks outside the media-downloader connector.
license: MIT
tags: [media-downloader, mcp]
metadata:
  author: Knuckles-Team
  version: '1.0.0'
---

# Video watching and watch skills

Use the typed tools of the `media-downloader` connector: one tool per upstream API operation, named `<operation>`. Each tool takes typed parameters; there is no `action` or `params_json` routing.

## Where the data lives

- **media-channel-videos** (`MEDIA_DOWNLOADER_OUTPUT_ROOT`): holds MediaOccurrence; read with `media_downloader_get_channel_videos`.
- **media-watch-skills** (`MEDIA_DOWNLOADER_SKILLS_DIR`): holds MediaArtifact; read with `list_watch_skills`.

## Workflows (tool-use contracts)

Each workflow is a tool-use contract in the connector ontology. Run the steps in order; read before you write.

### `media-downloader-manage-watch-skill`

1. `list_watch_skills` (`skills_root`) - List watch skills.
2. `build_watch_skill` (`body`, `description`, `manifest_path`, `mode`, `name`, `skills_root`, `tags`) - Run build watch skill.

### `media-downloader-manage-watch`

1. `media_downloader_watch` (`link`, `max_frames`, `min_frames`, `scene_threshold`, `subtitle_langs`) - Run media downloader watch.
2. `watch_media` (`download_directory`, `max_frames`, `scene_threshold`, `subtitle_languages`, `video_url`) - Run watch media.

## Guardrails

- Read before you write: list what exists (channel videos, watch skills) before downloading.
- Download only content the operator is entitled to fetch; stay inside the configured output root.
- Never print cookies, tokens or private source URLs.
- Report a tool refusal or HTTP error as it is; never retry past a refusal or invent a result.
