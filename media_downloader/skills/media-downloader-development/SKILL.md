---
name: media-downloader-development
skill_type: skill
domain: development
description: >-
  Develop, test, gate, and release the media-downloader connector. Use this skill when
  changing the connector's API mappings, MCP tools, packaging, documentation,
  or repository gates.
license: MIT
tags: [media-downloader, development, connector, test, gates]
tier: repository
metadata:
  author: Genius
  version: '0.2.0'
---

# media-downloader development

This repository owns the media-downloader connector: the `yt-dlp` based download library and CLI, its MCP tools, the media graph ingest (`kg_media.py`), and the network/filesystem trust boundaries in `security.py`. Shared connector contracts and transports belong to `scion-sdk`;
admission, serving, and durable graph state belong to their owning
repositories. Read `AGENTS.md` before changing code and keep provider
credentials and endpoints out of source, logs, and skill content.

## Rapid delivery: the 5-minute contract

Specs are already designed. Deliver small, reviewable slices and cite the
owning spec row in the commit trailer.

- Find the owning row first with `git grep -n "<term>" -- specs` and extend
  that spec before adding new requirement text.
- Reuse existing SDK clients, transport policies, and tool factories. Do not
  create a second implementation of a connector capability.
- Keep changes scoped to this connector. A change owned by the SDK, Arbora,
  or the knowledge graph belongs in that repository instead.
- Every delivered requirement needs a bound test. Generated `status.json`
  files are produced by `pipelines-hook spec-status`; never hand-edit them.
- One logical change per commit, with `Spec: <ID>` and the assisting agent
  trailer adjacent in the final paragraph.

## Setup and gates

Use the pinned environment from `uv sync --locked --all-extras`. Run the
repository gate from the checkout root:

```bash
uvx pre-commit run --all-files
```

For focused feedback, run the relevant tests with the repository's pinned
environment, for example:

```bash
uv run --all-extras pytest tests/test_security_boundaries.py -q
uv run --all-extras pytest tests/test_mcp.py tests/test_kg_media.py -q
uv run --all-extras pytest tests/test_publication_workflow.py -q
```

The canonical `.pre-commit-config.yaml` delegates connector-standard,
secrets, spec, tests-fast, and dependency-readiness checks to
`Knuckles-Team/pipelines` at `rev: main`. Do not replace those shared hooks
with local copies or bypass a failing check.

## Connector-specific checks

- Treat every URL as untrusted: requests go through `media_downloader/security.py`
  (redirect limit, metadata size cap, private-host refusal). Private hosts are
  allowed only through the administrator's `MEDIA_DOWNLOADER_ALLOW_PRIVATE_HOSTS`
  exact-host list; never widen that by default.
- Mock `yt-dlp` and all network access in tests; a gate must not download media.
- Output paths must stay inside the configured download directory.
- Entry points: `media-downloader` (CLI, `media_downloader.media_downloader`) and
  `media-downloader-mcp` (`media_downloader.mcp_server`).
- Keep the MCP surface aligned with `scion-sdk`; read the version from package
  metadata rather than spelling it in a module.
- Keep `media_downloader/skills/` package data intact when adding skills.
- Documentation lives under `docs/` and is published by the shared Pages
  workflow; source status records live under `specs/`.

## Delivery discipline

Work in a real Git worktree based on `origin/main`. Inspect the complete diff,
stage only reviewed paths, and verify `git status --short` after every gate.
Do not use `git stash`, `git add -A`, or `git add .`; do not claim Pages
publication until a successful exact-source workflow run and the public page
are both observed.
