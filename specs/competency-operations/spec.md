# CONN-MEDIA-DOWNLOADER-COMPETENCY-OPERATIONS — Download history

Owner: media-downloader. Cross-repo IDs: MEDULLA-MEDIA-VOCAB-R023, MEDULLA-MEDIA-VOCAB-R025, MEDULLA-MEDIA-VOCAB-R027.

## Purpose and user stories

Medulla answers a connector competency question over this connector's virtual graph. The question needs the operation below, which the connector does not serve today. Until it lands, Medulla answers with a typed abstention that names this operation.

## Why a new spec

No local spec owns connector operations that competency questions need. This spec owns them. It moved here from Medulla (MEDULLA-MEDIA-VOCAB-R023, MEDULLA-MEDIA-VOCAB-R025, MEDULLA-MEDIA-VOCAB-R027), where the rows described this connector's behaviour.

## Delivery mapping

Component: media-downloader connector

Code: ../../media_downloader/__init__.py

## User Scenarios & Testing

### User Story 1 - The connector must serve a `list_downloads` operation that returns job id, source URL, status, error, completedAt and output path for each download (Priority: P1)

The fleet operator and the engine rely on this behaviour of `media-downloader`: The connector must serve a `list_downloads` operation that returns job id, source URL, status, error, completedAt and output path for each download. It is proven independently of the other stories.

**Acceptance Scenarios**:

1. **Given** the `media-downloader` connector built from the default branch, **When** `tests/test_list_downloads.py::test_list_downloads_returns_the_documented_fields` runs, **Then** the operation returns the documented fields.

### Edge Cases

- The vendor service is unreachable or rejects the credential: the connector returns the SDK typed error and never a partial result.
- An argument outside the documented inputs is refused with the SDK typed refusal and causes no effect on the vendor service.

## Requirements

- **FR-001**: The connector must serve a `list_downloads` operation that returns job id, source URL, status, error, completedAt and output path for each download. Rows: `CONN-MEDIA-DOWNLOADER-COMPETENCY-OPERATIONS-R001`.

## Success Criteria

- **SC-001**: The operation returns the documented fields. Rows: `CONN-MEDIA-DOWNLOADER-COMPETENCY-OPERATIONS-R001`.

## Assumptions

- The `media-downloader` package keeps the entry point and module layout named in the rows.
- The shared SDK supplies the transport, authentication, retry and certification helpers the rows reuse.

## Traceability

| Label | Rows | Design section | Test ID | Evidence |
|---|---|---|---|---|
| FR-001 | `CONN-MEDIA-DOWNLOADER-COMPETENCY-OPERATIONS-R001` | plan.md Production caller chain | T-001 | tests/test_list_downloads.py::test_list_downloads_returns_the_documented_fields |
