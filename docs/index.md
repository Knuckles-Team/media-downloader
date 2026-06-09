# media-downloader

A **CLI / API + MCP server + A2A agent** for downloading audio and video from the
internet — built on `yt-dlp` and the agent-utilities ecosystem.

!!! info "Official documentation"
    This site is the canonical reference for `media-downloader`, maintained alongside
    every release.

[![PyPI](https://img.shields.io/pypi/v/media-downloader)](https://pypi.org/project/media-downloader/)
![MCP Server](https://badge.mcpx.dev?type=server 'MCP Server')
[![License](https://img.shields.io/pypi/l/media-downloader)](https://github.com/Knuckles-Team/media-downloader/blob/main/LICENSE)
[![GitHub](https://img.shields.io/badge/source-GitHub-181717?logo=github)](https://github.com/Knuckles-Team/media-downloader)

## Overview

`media-downloader` wraps `yt-dlp` in a typed, deterministic tool surface and exposes
the same capability three ways:

- **`MediaDownloader`** — a Python class that downloads video or audio (MP3) from
  YouTube, Rumble, and every other site `yt-dlp` supports, with parallel batch
  downloads and progress callbacks.
- **An MCP server** (`media-downloader-mcp`) — the `download_media` tool an agent
  calls, plus `download_video` / `download_audio` prompts.
- **A Pydantic-AI agent** (`media-downloader-agent`) — a conversational A2A server
  with an optional web UI that drives the MCP tool surface.

Every layer inherits the agent-utilities enterprise foundation: OpenTelemetry
tracing, Eunomia policy authorization, and prompt-injection defenses.

## Explore the documentation

<div class="grid cards" markdown>

- :material-rocket-launch: **[Installation](installation.md)** — pip, source, extras, and the prebuilt Docker image.
- :material-server-network: **[Deployment](deployment.md)** — run the MCP server, the agent server, Docker Compose, Caddy + Technitium.
- :material-console: **[Usage](usage.md)** — the MCP tools, the `MediaDownloader` Python API, and the CLI.
- :material-sitemap: **[Overview](overview.md)** — the ecosystem role, enterprise readiness, and architecture.
- :material-tag-multiple: **[Concepts](concepts.md)** — the `CONCEPT:MDLD-*` registry.

</div>

## Quick start

```bash
pip install "media-downloader[mcp]"
media-downloader-mcp             # stdio MCP server (default transport)
```

Or download from the command line directly:

```bash
pip install media-downloader
media-downloader --links "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --directory ./Downloads
```

See **[Installation](installation.md)** and **[Deployment](deployment.md)** for the
full matrix (PyPI extras, Docker image, all transports, reverse proxy, DNS).
