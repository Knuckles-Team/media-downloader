# CONN-MEDIA-DOWNLOADER — Channel video listing

Owner: media-downloader. Cross-repo IDs: none.

## Purpose and user stories

An agent must list the videos of a YouTube channel before it downloads them. The tool must return the found video links.

## Why a new spec

The `specs/` tree held only the template and the index.
No local spec owned this behavior, so this spec is the first capability spec.

## Scope and interfaces

The connector owns its media operations and their MCP tool annotations.
The connector SDK owns tool registration, transport and the shared client contracts.
Code: ../../media_downloader/media_downloader.py ../../tests/test_coverage_booster.py

## Open questions

- None.

## Delivery mapping

Component: media-downloader connector

Code: ../../media_downloader/__init__.py

## User Scenarios & Testing

### User Story 1 - Channel video links returned (Priority: P1)

The fleet operator and the engine rely on this behaviour of `media-downloader`: `MediaDownloader.get_channel_videos` in `media_downloader/media_downloader.py` must return the found video links, limited by `limit`. It is proven independently of the other stories.

**Acceptance Scenarios**:

1. **Given** the `media-downloader` connector built from the default branch, **When** `tests/test_coverage_booster.py::test_get_channel_videos_returns_links` runs, **Then** `test_get_channel_videos_returns_links` in `tests/test_coverage_booster.py` must show two returned links for `limit=2`, equal to `self.links`.

### User Story 2 - Embedded video IDs read (Priority: P1)

The fleet operator and the engine rely on this behaviour of `media-downloader`: `_canonical_channel_video_links` in `media_downloader/media_downloader.py` must read the `videoId` values from the page's embedded initial data when the page has no `href="/watch?` anchors. It is proven independently of the other stories.

**Acceptance Scenarios**:

1. **Given** the `media-downloader` connector built from the default branch, **When** `tests/test_coverage_booster.py::test_get_channel_videos_reads_embedded_video_ids` runs, **Then** `test_get_channel_videos_reads_embedded_video_ids` in `tests/test_coverage_booster.py` must show two unique watch links for `limit=2`.

### Edge Cases

- The vendor service is unreachable or rejects the credential: the connector returns the SDK typed error and never a partial result.
- An argument outside the documented inputs is refused with the SDK typed refusal and causes no effect on the vendor service.

## Requirements

- **FR-001**: Channel video links returned. Rows: `CONN-MEDIA-DOWNLOADER-R001`.
- **FR-002**: Embedded video IDs read. Rows: `CONN-MEDIA-DOWNLOADER-R001.1`.

## Success Criteria

- **SC-001**: `test_get_channel_videos_returns_links` in `tests/test_coverage_booster.py` must show two returned links for `limit=2`, equal to `self.links`. Rows: `CONN-MEDIA-DOWNLOADER-R001`.
- **SC-002**: `test_get_channel_videos_reads_embedded_video_ids` in `tests/test_coverage_booster.py` must show two unique watch links for `limit=2`. Rows: `CONN-MEDIA-DOWNLOADER-R001.1`.

## Assumptions

- The `media-downloader` package keeps the entry point and module layout named in the rows.
- The shared SDK supplies the transport, authentication, retry and certification helpers the rows reuse.

## Traceability

| Label | Rows | Design section | Test ID | Evidence |
|---|---|---|---|---|
| FR-001 | `CONN-MEDIA-DOWNLOADER-R001` | plan.md Production caller chain | T-001 | tests/test_coverage_booster.py::test_get_channel_videos_returns_links |
| FR-002 | `CONN-MEDIA-DOWNLOADER-R001.1` | plan.md Production caller chain | T-002 | tests/test_coverage_booster.py::test_get_channel_videos_reads_embedded_video_ids |
