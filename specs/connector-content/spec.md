# CONN-MEDIA-DOWNLOADER-CONNECTOR-CONTENT — The connector serves its packaged content

Owner: media-downloader. Cross-repo IDs: `SCION-CONNECTOR-CONTROL-R071`, `SCION-CONNECTOR-CONTROL-R073`.

## Purpose and user stories

The `media-downloader-mcp` server serves its packaged skills, prompts and ontology to any client, with no wiring of its own.

## Delivery mapping

Component: media-downloader connector

Code: ../../media_downloader/__init__.py

## Why a new spec

Searched `specs/` of `media-downloader` with `git grep` for the terms of this spec. No other spec of this repository owns the capability, so this spec owns it.

## User Scenarios & Testing

### User Story 1 - Default content (Priority: P1)

The fleet operator and the engine rely on this behaviour of `media-downloader`: `pyproject.toml` declares `media-downloader-mcp` as the single `scion_sdk.connector` entry point. It is proven independently of the other stories.

**Acceptance Scenarios**:

1. **Given** the `media-downloader` connector built from the default branch, **When** `tests/test_default_content_surfaces.py::test_default_content_surfaces` runs, **Then** `resources/list` includes `skill://` and `ontology://`; `prompts/list` includes each packaged prompt.

### Edge Cases

- The vendor service is unreachable or rejects the credential: the connector returns the SDK typed error and never a partial result.
- An argument outside the documented inputs is refused with the SDK typed refusal and causes no effect on the vendor service.

## Requirements

- **FR-001**: Default content. Rows: `CONN-MEDIA-DOWNLOADER-CONNECTOR-CONTENT-R001`.

## Success Criteria

- **SC-001**: `resources/list` includes `skill://` and `ontology://`; `prompts/list` includes each packaged prompt. Rows: `CONN-MEDIA-DOWNLOADER-CONNECTOR-CONTENT-R001`.

## Assumptions

- The `media-downloader` package keeps the entry point and module layout named in the rows.
- The shared SDK supplies the transport, authentication, retry and certification helpers the rows reuse.

## Traceability

| Label | Rows | Design section | Test ID | Evidence |
|---|---|---|---|---|
| FR-001 | `CONN-MEDIA-DOWNLOADER-CONNECTOR-CONTENT-R001` | plan.md Production caller chain | T-001 | tests/test_default_content_surfaces.py::test_default_content_surfaces |
