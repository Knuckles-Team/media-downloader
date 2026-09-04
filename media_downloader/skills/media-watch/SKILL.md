---
name: media-watch
skill_type: skill
description: >-
  Watch a video by URL through the media-downloader MCP server and turn it into a
  reusable skill: pull the captions, extract scene-change key frames whose
  filenames carry their timestamp, then read both and write down what the video
  teaches, the steps, and the warnings. Works on tutorials, demos, talks, Loom and
  TikTok clips, podcasts, and screen recordings of something broken. Use when the
  agent must understand or reproduce what a video shows rather than merely archive
  it. Do NOT use for plain video download (media-download), audio-only MP3
  extraction (media-audio), or transcribing a file that is already on disk
  (audio-transcriber-transcription).
license: MIT
tags: [media-downloader, watch, captions, key-frames, transcript, skill-builder, mcp]
metadata:
  author: Genius
  version: '0.1.0'
---
# Media Watch

Turn a video into something an agent can work from: the transcript plus what was
actually on screen.

## When to use
- Learn a method from a tutorial, demo, conference talk, or screen recording.
- Capture what a video shows that the narration never says out loud — a command
  typed on screen, a menu path, a config value, an error message.
- Turn a video into a reusable skill, checklist, or runbook.

## When NOT to use
- Just archiving a video → `media-download`.
- Only the audio track as MP3 → `media-audio`.
- A media file already on disk → `audio-transcriber-transcription`.
- Querying media already in the KG → query the `:MediaAsset` nodes directly.

## Prerequisites & environment
Connect via the `mcp-client` skill against the **`media-downloader`** MCP server.
`ffmpeg` and `ffprobe` must be on `PATH` for key frames; without them the run
still returns captions and reports `frames.status: "unavailable"`.

| Variable | Required | Notes |
|----------|----------|-------|
| `MEDIA_DOWNLOADER_OUTPUT_ROOT` | optional | Root the bundle is written beneath |
| `GRAPH_SERVICE_ENDPOINTS` | optional | Engine endpoint for native KG ingestion |

`MCP_TOOL_MODE` (`condensed`|`verbose`|`both`) selects the tool surface.

## Tools & actions
| Tool | Purpose |
|------|---------|
| `watch_media` | Download a URL with captions + key frames; returns the bundle manifest |
| `list_watch_skills` | What video-built skills exist and which videos each already has |
| `build_watch_skill` | Write a new skill from a bundle, or extend an existing one |
| `transcribe_audio` | (audio-transcriber package) fallback when captions are missing |

### Key parameters
- `video_url` — the media URL (required).
- `download_directory` — where the bundle is written (default `.`).
- `max_frames` — cap on extracted key frames (default 24).
- `scene_threshold` — ffmpeg scene sensitivity, 0-1 (default 0.3); lower finds more.
- `subtitle_languages` — comma-separated caption codes (default `en,en-orig`).

## Recipes

Watch a video and build a skill from it:

```json
{"video_url": "<the video URL>", "download_directory": "/data/media", "max_frames": 24}
```

The bundle directory contains `manifest.json`, `transcript.txt`, the raw `.vtt`,
the media file, and `frames/frame_<n>_t<seconds>.jpg`.

### The analysis contract

**Read `manifest.json` first.** If `status` is not `success`, say what is missing
before producing anything. If `captions.status` is `missing`, stop and report it;
the `captions.fallback` block names the audio-transcriber skill and the file to
run it against — `transcribe_audio(audio_file=<media_file>, export_formats=["txt","vtt"])`.
Resume only once a transcript exists, and mark it ASR-derived.

Then work **only from this video** — the frames and the captions, nothing else:

1. Read `transcript.txt` end to end.
2. Read every frame in `frames/`. Each filename carries its timestamp, so line a
   frame up against the transcript lines at that time to see what was on screen
   while it was being said.
3. Identify the one thing the video teaches.
4. Extract every step, decision, and example, in the order they appear.
5. Note anything shown on screen that the speaker never says out loud.

Then produce, in this order:

- **What this video teaches** — one line.
- **The steps** — written as instructions an AI could follow.
- **Mistakes and warnings** — every one the creator gives.
- **A skill file** — a complete `SKILL.md` that can be saved and reused.

Rules: use only what is in the frames and captions. Mark anything you inferred as
inferred. If the download failed or the captions were missing, say so before you
build anything.

## Building and extending a skill

Turning the analysis into a saved skill is a two-step job, and the split matters:
**you write the body, `build_watch_skill` owns the mechanics** — frontmatter, the
provenance every claim stays traceable to, the sources table, the version bump,
and the derived `WORKFLOW.md`.

Before writing, call `list_watch_skills` on the skills root. It says whether this
video extends a skill that already exists and whether that skill already covers
it. Then pick a mode:

| Mode | Use when |
|------|----------|
| `create` | No existing skill covers this subject. Needs a `description`. |
| `append` | A later video adds a section without changing what the earlier ones meant. |
| `replace` | A later video changes the picture, and the whole body needs rewriting. Provenance is kept. |

`append` refuses a video the skill already lists, so re-running is safe.
`replace` keeps every recorded source and bumps the version like `append` does.

Because provenance records what each video actually yielded — transcript lines,
frame count, or their absence — a skill built from a caption-only bundle stays
auditable as caption-only months later. Say so in the body too: a reader should
not have to check the sources table to learn that nothing on screen was seen.

## Gotchas
- `status: "partial"` means captions or frames are missing — the analysis is
  incomplete by definition, so report it rather than papering over the gap.
- Frames are capped by scene score, not by time: the highest-scoring changes are
  kept and re-sorted chronologically, so gaps between frames are expected and do
  not mean anything was dropped silently.
- `mode: "interval"` means too few scene changes were found and frames are evenly
  spaced instead — common for a static talking head, and weaker evidence of what
  was on screen.
- Caption language codes are not wildcards. `en.*` asks a site for every
  translated track and earns a rate-limit error; name the codes you want.
  The default is English (`en,en-orig`), and the requested order wins over
  track size, so the transcript language is a choice rather than an accident.
- A site can serve the captions and then refuse the video. That is reported as
  `partial` with `frames.status: "unavailable"` and the transcript intact -
  not as a failure. `status: "error"` means nothing at all was obtained.
- The bundle directory is named from a digest of the URL, so re-running the same
  URL reuses and refreshes it rather than piling up copies.
- A video with no captions is normal for screen recordings; that is what the
  audio-transcriber fallback is for.

## Related
- `media-download` — archive a video without analysing it.
- `media-audio` — the audio track only, as MP3.
- `audio-transcriber-transcription` — the captions fallback, and any file already
  on disk.
- Reuses the shared media ontology (`:MediaAsset`, `:Blob`) federated by the
  jellyfin-mcp package.
