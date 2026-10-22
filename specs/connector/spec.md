# CONN-MEDIA-DOWNLOADER — Channel video listing

Owner: media-downloader. Cross-repo IDs: none.

## Purpose and user stories

An agent must list the videos of a YouTube channel before it downloads them. The tool must return the found video links.

## Requirements and acceptance

- FR-001: `MediaDownloader.get_channel_videos` in `media_downloader/media_downloader.py` must return the found video links, limited by `limit`. It must return an empty list when no channel is found.
- SC-001: `tests/test_coverage_booster.py` shows that the method returns the links and that the queued links match them, with no network call.

## Why a new spec

The `specs/` tree held only the template and the index.
No local spec owned this behavior, so this spec is the first capability spec.

## Scope and interfaces

The connector owns its media operations and their MCP tool annotations.
The connector SDK owns tool registration, transport and the shared client contracts.
Code: ../../media_downloader/media_downloader.py ../../tests/test_coverage_booster.py

## Traceability

| Requirement | Design section | Test ID | Evidence |
|---|---|---|---|
| FR-001 | plan.md#architecture | T-001 | `tests/test_coverage_booster.py` |

## Open questions

- None.
