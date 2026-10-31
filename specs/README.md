# media-downloader specifications

These specs follow the ecosystem [spec standard](https://github.com/Knuckles-Team/pipelines/blob/main/reference/spec-standard.md): one owning spec per capability, extend an existing spec before creating one, audits and reviews land in the owning spec, one ID and title form, one file set. The `spec-standard` gate enforces it.

## Owner

This repository owns the specs with the ID prefix `CONN-MEDIA-DOWNLOADER`. The connector contract, certification, and transport rules belong to [scion-sdk](https://github.com/Knuckles-Team/scion-sdk/tree/main/specs). The spec-delivery page rules belong to [pipelines](https://github.com/Knuckles-Team/pipelines/tree/main/specs).

## Add a spec

Read the existing specs first. Extend the spec that owns the behavior. Create a spec only for a capability that no spec owns. Copy [`_template/`](_template/) to `specs/<area>/`, set the ID to `CONN-MEDIA-DOWNLOADER` or `CONN-MEDIA-DOWNLOADER-<AREA>`, and add one index line below.

## Local specifications

[`CONN-MEDIA-DOWNLOADER`](connector/spec.md) — The connector lists the video links of a YouTube channel.
- [`CONN-MEDIA-DOWNLOADER-COMPETENCY-OPERATIONS`](competency-operations/spec.md) — Download history.
