---
name: media-downloader-development
skill_type: skill
domain: development
description: >-
  Develop, test, gate, and release the media-downloader connector. Use this
  skill when changing the connector's API mappings, MCP tools, packaging,
  documentation, or repository gates.
license: MIT
tags: [media-downloader, development, connector, test, gates]
tier: repository
metadata:
  author: Genius
  version: '0.1.0'
---

# media-downloader development

This repository owns the media-downloader connector. Shared connector
contracts and transports belong to `scion-sdk`; admission, serving, and
durable graph state belong to their owning repositories. Read `AGENTS.md`
before changing code and keep provider credentials and endpoints out of
source, logs, and skill content.

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
