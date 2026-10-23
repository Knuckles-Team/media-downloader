# CONN-MEDIA-DOWNLOADER-CONNECTOR-CONTENT — Design and implementation plan

Governing spec: [spec.md](spec.md).

## Architecture

`pyproject.toml` declares `media-downloader-mcp` as the connector identity. `create_mcp_server` resolves the packaged content of `media_downloader` from it.
