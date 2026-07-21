# Deployment

<!-- BEGIN GENERATED: deployment-options -->
## Deployment Options

`media-downloader` supports local stdio, a loopback-only development listener, a
least-privilege stdio container, and a remote authenticated HTTPS boundary.
Provider endpoint, credential, selector, identity, and trust material are supplied
at runtime through `AgentConfig`; none is stored in this repository.

### Installed stdio process

```json
{
  "mcpServers": {
    "media-downloader": {
      "command": "media-downloader-mcp",
      "args": [],
      "env": {"MCP_TOOL_MODE": "intent"}
    }
  }
}
```

### Loopback development listener

```bash
media-downloader-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

Do not expose this listener beyond loopback. Network deployments require direct TLS
or an explicitly trusted TLS-terminating ingress, configured authentication, exact
`MCP_ALLOWED_HOSTS`, and an exact trusted-proxy CIDR policy.

### Least-privilege local container

```bash
docker run -i --rm \
  --read-only \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --pids-limit=256 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m \
  -e TRANSPORT=stdio \
  registry.example.invalid/media-downloader@sha256:<digest> media-downloader-mcp
```

The operator projects the selected AgentConfig profile into the process at runtime;
the image remains immutable and contains no environment connection profile.

### Remote authenticated HTTPS endpoint

```json
{
  "mcpServers": {
    "media-downloader": {"url": "https://service.example.invalid/mcp"}
  }
}
```

Store the real remote URL, outbound identity reference, and TLS-profile reference in
`AgentConfig`, not in MCP client JSON or documentation.
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
    image: example/media-downloader@sha256:<digest>
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
    image: example/media-downloader@sha256:<digest>
    hostname: media-downloader-mcp
    environment:
      - HOST=0.0.0.0
      - PORT=8000
      - TRANSPORT=streamable-http
    ports: ["8000:8000"]

  media-downloader-agent:
    image: example/media-downloader@sha256:<digest>
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
# Internal (self-signed) — homelab .example.invalid zone
media-downloader.example.invalid {
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
curl -s "http://technitium.example.invalid:5380/api/zones/records/add" \
  --data-urlencode "token=$TECHNITIUM_DNS_TOKEN" \
  --data-urlencode "domain=media-downloader.example.invalid" \
  --data-urlencode "zone=arpa" \
  --data-urlencode "type=A" \
  --data-urlencode "ipAddress=192.0.2.10" \
  --data-urlencode "ttl=3600"
```

…or add an **A record** `media-downloader.example.invalid → <caddy-host-ip>` in the Technitium
web console (`http://technitium.example.invalid:5380`). The ecosystem
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

For a remote HTTP server, point the client at `http://media-downloader.example.invalid/mcp`
instead.
