# Deployment

<!-- BEGIN GENERATED: deployment-options -->
## Deployment Options

`media-downloader` exposes its MCP server (console script `media-downloader-mcp`) four ways. Pick the row that
matches where the server runs relative to your MCP client, then copy the matching
`mcp_config.json` below. Add the service-connection environment variables documented in the **Configuration** section.

| # | Option | Transport | Where it runs | `mcp_config.json` key |
|---|--------|-----------|---------------|------------------------|
| 1 | stdio | `stdio` | client launches a subprocess | `command` |
| 2 | Streamable-HTTP (local) | `streamable-http` | a local network port | `command` or `url` |
| 3 | Local container / uv | `stdio` or `streamable-http` | Docker / Podman / uv on this host | `command` or `url` |
| 4 | Remote URL | `streamable-http` | a remote host behind Caddy | `url` |

### 1. stdio (local subprocess)

The client launches the server over stdio via `uvx` — best for local IDEs
(Cursor, Claude Desktop, VS Code):

```json
{
  "mcpServers": {
    "media-downloader-mcp": {
      "command": "uvx",
      "args": ["--from", "media-downloader", "media-downloader-mcp"]
    }
  }
}
```

### 2. Streamable-HTTP (local process)

Run the server as a long-lived HTTP process:

```bash
uvx --from media-downloader media-downloader-mcp --transport streamable-http --host 0.0.0.0 --port 8000
curl -s http://localhost:8000/health        # {"status":"OK"}
```

Then either let the client launch it:

```json
{
  "mcpServers": {
    "media-downloader-mcp": {
      "command": "uvx",
      "args": ["--from", "media-downloader", "media-downloader-mcp", "--transport", "streamable-http", "--port", "8000"],
      "env": {
        "TRANSPORT": "streamable-http",
        "HOST": "0.0.0.0",
        "PORT": "8000"
      }
    }
  }
}
```

…or connect to the already-running process by URL:

```json
{
  "mcpServers": {
    "media-downloader-mcp": { "url": "http://localhost:8000/mcp" }
  }
}
```

### 3. Local container / uv

**(a) Launch a container directly from `mcp_config.json`** (stdio over the container —
no ports to manage). Swap `docker` for `podman` for a daemonless runtime:

```json
{
  "mcpServers": {
    "media-downloader-mcp": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "TRANSPORT=stdio",
        "knucklessg1/media-downloader:latest"
      ]
    }
  }
}
```

**(b) Run a local streamable-http container, then connect by URL:**

```bash
docker run -d --name media-downloader-mcp -p 8000:8000 \
  -e TRANSPORT=streamable-http \
  -e PORT=8000 \
  knucklessg1/media-downloader:latest
# or, from a clone of this repo:
docker compose -f docker/mcp.compose.yml up -d
```

```json
{
  "mcpServers": {
    "media-downloader-mcp": { "url": "http://localhost:8000/mcp" }
  }
}
```

**(c) From a local checkout with `uv`:**

```bash
uv run media-downloader-mcp --transport streamable-http --port 8000
```

### 4. Remote URL (deployed behind Caddy)

When the server is deployed remotely (e.g. as a Docker service) and published through
Caddy on the internal `*.arpa` zone, connect with the `"url"` key — no local process or
image required:

```json
{
  "mcpServers": {
    "media-downloader-mcp": { "url": "http://media-downloader-mcp.arpa/mcp" }
  }
}
```

Caddy reverse-proxies `http://media-downloader-mcp.arpa` to the container's `:8000`
streamable-http listener; `http://media-downloader-mcp.arpa/health` returns
`{"status":"OK"}` when the service is live.
<!-- END GENERATED: deployment-options -->

This page covers running `media-downloader` as a long-lived server: the transports, a
Docker Compose stack, putting it behind a Caddy reverse proxy, and giving it a DNS
name with Technitium. It also documents the optional **A2A agent server**.

> `media-downloader` ships an **MCP server** (console script `media-downloader-mcp`)
> and a **Pydantic-AI agent server** (console script `media-downloader-agent`). The
> agent connects to the MCP server over `MCP_URL` and exposes a conversational A2A
> interface with an optional web UI.

## Run the MCP server

The transport is selected with `--transport` (or the `TRANSPORT` env var):

=== "stdio (default)"

    ```bash
    media-downloader-mcp
    ```
    For IDE / desktop MCP clients that launch the server as a subprocess.

=== "streamable-http"

    ```bash
    media-downloader-mcp --transport streamable-http --host 0.0.0.0 --port 8000
    ```
    A network server with a `/health` endpoint and `/mcp` route.

=== "sse"

    ```bash
    media-downloader-mcp --transport sse --host 0.0.0.0 --port 8000
    ```

Health check (HTTP transports):

```bash
curl -s http://localhost:8000/health        # {"status":"OK"}
```

## Configuration (environment)

`media-downloader` is configured entirely from the environment. The **required** set
is small — the downloader needs no external service. Copy
[`.env.example`](https://github.com/Knuckles-Team/media-downloader/blob/main/.env.example)
to `.env` and fill in only what you use:

| Var | Default | Meaning |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address for HTTP transports |
| `PORT` | `8000` | Listen port for HTTP transports |
| `TRANSPORT` | `stdio` | `stdio`, `streamable-http`, or `sse` |
| `YT_DLP_PATH` | `/usr/bin/yt-dlp` | Path to the `yt-dlp` binary |
| `BREW_INSTALL_CMD` | `brew install yt-dlp` | Install hint surfaced for macOS hosts |
| `ENABLE_OTEL` | `True` | Emit OpenTelemetry traces |
| `EUNOMIA_TYPE` | `none` | Authorization mode: `none`, `embedded`, or `remote` |
| `EUNOMIA_POLICY_FILE` | `mcp_policies.json` | Local policy file for `embedded` mode |

Optional telemetry (`OTEL_EXPORTER_OTLP_*`) and Eunomia remote (`EUNOMIA_REMOTE_URL`)
variables are documented inline in `.env.example`; each remains inactive when its
credentials are absent.

## Docker Compose

The repo ships [`docker/mcp.compose.yml`](https://github.com/Knuckles-Team/media-downloader/blob/main/docker/mcp.compose.yml).
It reads a sibling `.env` and publishes the HTTP server on `:8000`:

```yaml
services:
  media-downloader-mcp:
    image: knucklessg1/media-downloader:latest
    container_name: media-downloader-mcp
    hostname: media-downloader-mcp
    restart: always
    env_file:
      - ../.env
    environment:
      - PYTHONUNBUFFERED=1
      - HOST=0.0.0.0
      - PORT=8000
      - TRANSPORT=streamable-http
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
```

```bash
cp .env.example .env          # then edit values
docker compose -f docker/mcp.compose.yml up -d
docker compose -f docker/mcp.compose.yml logs -f
```

## Agent server (A2A)

`media-downloader` also ships a Pydantic-AI agent. The console script
`media-downloader-agent` connects to the MCP server over `MCP_URL` and serves a
conversational A2A endpoint (with an optional web UI) on its own port:

```bash
export MCP_URL=http://localhost:8000/mcp
media-downloader-agent --provider openai --model-id gpt-4o --host 0.0.0.0 --port 9000
```

The repo ships [`docker/agent.compose.yml`](https://github.com/Knuckles-Team/media-downloader/blob/main/docker/agent.compose.yml),
which provisions the MCP server and the agent together. The agent waits on the MCP
server and is wired to it by container name:

```yaml
services:
  media-downloader-mcp:
    image: knucklessg1/media-downloader:latest
    hostname: media-downloader-mcp
    environment:
      - HOST=0.0.0.0
      - PORT=8000
      - TRANSPORT=streamable-http
    ports: ["8000:8000"]

  media-downloader-agent:
    image: knucklessg1/media-downloader:latest
    depends_on: [media-downloader-mcp]
    command: ["media-downloader-agent"]
    environment:
      - HOST=0.0.0.0
      - PORT=9000
      - MCP_URL=http://media-downloader-mcp:8000/mcp
      - PROVIDER=${PROVIDER:-openai}
      - MODEL_ID=${MODEL_ID:-gpt-4o}
      - ENABLE_WEB_UI=True
    ports: ["9000:9000"]
```

```bash
docker compose -f docker/agent.compose.yml up -d
```

| Service | Port | Role |
|---|---|---|
| `media-downloader-mcp` | `8000` | MCP tool surface (`/mcp`, `/health`) |
| `media-downloader-agent` | `9000` | A2A agent + web UI, wired via `MCP_URL` |

## Behind a Caddy reverse proxy

Expose the HTTP server on a hostname with automatic TLS. Add to your `Caddyfile`:

```caddy
# Internal (self-signed) — homelab .arpa zone
media-downloader.arpa {
    tls internal
    reverse_proxy media-downloader-mcp:8000
}
```

```caddy
# Public — automatic Let's Encrypt
media-downloader.example.com {
    reverse_proxy media-downloader-mcp:8000
}
```

Reload Caddy:

```bash
docker compose -f services/caddy/compose.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## DNS with Technitium

Point the hostname at the host running Caddy. Via the Technitium API:

```bash
curl -s "http://technitium.arpa:5380/api/zones/records/add" \
  --data-urlencode "token=$TECHNITIUM_DNS_TOKEN" \
  --data-urlencode "domain=media-downloader.arpa" \
  --data-urlencode "zone=arpa" \
  --data-urlencode "type=A" \
  --data-urlencode "ipAddress=10.0.0.10" \
  --data-urlencode "ttl=3600"
```

…or add an **A record** `media-downloader.arpa → <caddy-host-ip>` in the Technitium
web console (`http://technitium.arpa:5380`). The ecosystem
[`technitium-dns-mcp`](https://knuckles-team.github.io/technitium-dns-mcp/) automates
this as a tool.

## Register with an MCP client

Add to your client's `mcp_config.json`:

```json
{
  "mcpServers": {
    "media-downloader": {
      "command": "uv",
      "args": ["run", "media-downloader-mcp"],
      "env": {
        "DOWNLOAD_DIRECTORY": "/data/downloads",
        "AUDIO_ONLY": "False"
      }
    }
  }
}
```

For a remote HTTP server, point the client at `http://media-downloader.arpa/mcp`
instead.
