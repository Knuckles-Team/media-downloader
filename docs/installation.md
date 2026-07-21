# Installation

`media-downloader` is a standard Python package and a prebuilt container image. Pick
the path that matches how you want to run it.

## Requirements

- **Python 3.11 – 3.14**.
- **`ffmpeg`** on the host for audio extraction / MP3 conversion (`yt-dlp`
  post-processing). On Debian/Ubuntu: `apt-get install ffmpeg`.

## From PyPI (recommended)

```bash
pip install media-downloader
```

### Optional extras

The base install ships the CLI and the `MediaDownloader` Python API. Install the
extra for the runtime you need:

| Extra | Install | Pulls in |
|---|---|---|
| `mcp` | `pip install "media-downloader[mcp]"` | FastMCP MCP-server runtime (`agent-utilities[mcp]`) |
| `agent` | `pip install "media-downloader[agent]"` | Pydantic-AI agent + Logfire tracing (`agent-utilities[agent-runtime,logfire]`) |
| `all` | `pip install "media-downloader[all]"` | The MCP server and the agent together |
| `test` | `pip install "media-downloader[test]"` | `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-xdist` |

```bash
# Typical: run the MCP server and the A2A agent
pip install "media-downloader[all]"
```

## From source

```bash
git clone https://github.com/Knuckles-Team/media-downloader.git
cd media-downloader
pip install -e ".[all]"          # editable install with every runtime extra
```

With [`uv`](https://docs.astral.sh/uv/):

```bash
uv pip install -e ".[all]"
uv run media-downloader-mcp
```

## Prebuilt Docker image

A multi-stage runtime image is published on every release (entrypoint
`media-downloader-mcp`, `ffmpeg` included):

```bash
docker pull example/media-downloader@sha256:<digest>

docker run --rm -i \
  example/media-downloader@sha256:<digest>        # stdio transport (default)
```

For an HTTP server with a published port, see [Deployment](deployment.md).

## Verify the install

```bash
media-downloader --help
media-downloader-mcp --help
python -c "import media_downloader; print(media_downloader.__version__)"
```

## Next steps

- **[Deployment](deployment.md)** — run it as a long-lived MCP server (and agent) behind Caddy + DNS.
- **[Usage](usage.md)** — call the tools, the Python API, and the CLI.
- **[Configuration](deployment.md#configuration-environment)** — every environment variable.
