# Media Downloader - A2A | AG-UI | MCP

![PyPI - Version](https://img.shields.io/pypi/v/media-downloader)
![MCP Server](https://badge.mcpx.dev?type=server 'MCP Server')
![PyPI - Downloads](https://img.shields.io/pypi/dd/media-downloader)
![GitHub Repo stars](https://img.shields.io/github/stars/Knuckles-Team/media-downloader)
![GitHub forks](https://img.shields.io/github/forks/Knuckles-Team/media-downloader)
![GitHub contributors](https://img.shields.io/github/contributors/Knuckles-Team/media-downloader)
![PyPI - License](https://img.shields.io/pypi/l/media-downloader)
![GitHub](https://img.shields.io/github/license/Knuckles-Team/media-downloader)

![GitHub last commit (by committer)](https://img.shields.io/github/last-commit/Knuckles-Team/media-downloader)
![GitHub pull requests](https://img.shields.io/github/issues-pr/Knuckles-Team/media-downloader)
![GitHub closed pull requests](https://img.shields.io/github/issues-pr-closed/Knuckles-Team/media-downloader)
![GitHub issues](https://img.shields.io/github/issues/Knuckles-Team/media-downloader)

![GitHub top language](https://img.shields.io/github/languages/top/Knuckles-Team/media-downloader)
![GitHub language count](https://img.shields.io/github/languages/count/Knuckles-Team/media-downloader)
![GitHub repo size](https://img.shields.io/github/repo-size/Knuckles-Team/media-downloader)
![GitHub repo file count (file type)](https://img.shields.io/github/directory-file-count/Knuckles-Team/media-downloader)
![PyPI - Wheel](https://img.shields.io/pypi/wheel/media-downloader)
![PyPI - Implementation](https://img.shields.io/pypi/implementation/media-downloader)

*Version: 2.1.36*

## Overview

Download videos and audio from the internet!

This package comes ready with an MCP Server and an A2A Server so you can plug this Agent into any of your existing agentic framework!

You can also plug in the MCP Server directly to your own agent if you prefer!

This repository is actively maintained - Contributions are welcome!

### Supports:
- YouTube
- Twitter
- Rumble
- BitChute
- Vimeo
- And More!

This requires a [javascript runtime](https://github.com/yt-dlp/yt-dlp/issues/15012#issue-3614398875).
However, the container is fully baked and ready to go!

## Usage

### CLI
| Short Flag | Long Flag   | Description                                 |
|------------|-------------|---------------------------------------------|
| -h         | --help      | See usage                                   |
| -a         | --audio     | Download audio only                         |
| -c         | --channel   | YouTube Channel/User - Downloads all videos |
| -f         | --file      | File with video links                       |
| -l         | --links     | Comma separated links                       |
| -d         | --directory | Location to save videos                     |

```bash
media-downloader --file "C:\Users\videos.txt" --directory "C:\Users\Downloads" --channel "WhiteHouse" --links "URL1,URL2,URL3"
```

### MCP CLI

| Short Flag | Long Flag                          | Description                                                                 |
|------------|------------------------------------|-----------------------------------------------------------------------------|
| -h         | --help                             | Display help information                                                    |
| -t         | --transport                        | Transport method: 'stdio', 'http', or 'sse' [legacy] (default: stdio)       |
| -s         | --host                             | Host address for HTTP transport (default: 0.0.0.0)                          |
| -p         | --port                             | Port number for HTTP transport (default: 8000)                              |
|            | --auth-type                        | Authentication type: 'none', 'static', 'jwt', 'oauth-proxy', 'oidc-proxy', 'remote-oauth' (default: none) |
|            | --token-jwks-uri                   | JWKS URI for JWT verification                                              |
|            | --token-issuer                     | Issuer for JWT verification                                                |
|            | --token-audience                   | Audience for JWT verification                                              |
|            | --oauth-upstream-auth-endpoint     | Upstream authorization endpoint for OAuth Proxy                             |
|            | --oauth-upstream-token-endpoint    | Upstream token endpoint for OAuth Proxy                                    |
|            | --oauth-upstream-client-id         | Upstream client ID for OAuth Proxy                                         |
|            | --oauth-upstream-client-secret     | Upstream client secret for OAuth Proxy                                     |
|            | --oauth-base-url                   | Base URL for OAuth Proxy                                                   |
|            | --oidc-config-url                  | OIDC configuration URL                                                     |
|            | --oidc-client-id                   | OIDC client ID                                                             |
|            | --oidc-client-secret               | OIDC client secret                                                         |
|            | --oidc-base-url                    | Base URL for OIDC Proxy                                                    |
|            | --remote-auth-servers              | Comma-separated list of authorization servers for Remote OAuth             |
|            | --remote-base-url                  | Base URL for Remote OAuth                                                  |
|            | --allowed-client-redirect-uris     | Comma-separated list of allowed client redirect URIs                       |
|            | --eunomia-type                     | Eunomia authorization type: 'none', 'embedded', 'remote' (default: none)   |
|            | --eunomia-policy-file              | Policy file for embedded Eunomia (default: mcp_policies.json)              |
|            | --eunomia-remote-url               | URL for remote Eunomia server                                              |

### Using as an MCP Server

The MCP Server can be run in two modes: `stdio` (for local testing) or `http` (for networked access). To start the server, use the following commands:

#### Run in stdio mode (default):
```bash
media-downloader-mcp
```

#### Run in HTTP mode:
```bash
media-downloader-mcp --transport http --host 0.0.0.0 --port 8012
```


AI Prompt:
```text
Download me this video: https://youtube.com/watch?askdjfa
```

AI Response:
```text
Sure thing, the video has been downloaded to:

"C:\Users\User\Downloads\YouTube Video - Episode 1.mp4"
```

### Use in Python

```python
# Import library
from media_downloader.media_downloader import MediaDownloader

# Set URL of video/audio here
url = "https://YootToob.com/video"

# Instantiate vide_downloader_instance
video_downloader_instance = MediaDownloader()

# Set the location to save the video
video_downloader_instance.set_save_path("C:/Users/you/Downloads")

# Add URL to download
video_downloader_instance.append_link(url)

# Download all videos appended
video_downloader_instance.download_all()
```

```python
# Optional - Set Audio to True, Default is False if unspecified.
video_downloader_instance.set_audio(audio=True)

# Optional - Open a file of video/audio URL(s)
video_downloader_instance.open_file("FILE")

# Optional - Enter a YouTube channel name and download their latest videos
video_downloader_instance.get_channel_videos("YT-Channel Name")
```

### Agent-to-Agent (A2A) Server

This package includes an Agent utilizing `pydantic-ai` that can be deployed as an A2A server. This agent is capable of using the `media-downloader` MCP server to fulfill media retrieval requests.

#### Endpoints
- **Web UI**: `http://localhost:8000/` (if enabled)
- **A2A**: `http://localhost:8000/a2a` (Discovery: `/a2a/.well-known/agent.json`)
- **AG-UI**: `http://localhost:8000/ag-ui` (POST)

#### A2A CLI

| Long Flag        | Description                                      | Default                     |
|------------------|--------------------------------------------------|-----------------------------|
| --host           | Host to bind the server to                       | 0.0.0.0                     |
| --port           | Port to bind the server to                       | 8000                        |
| --reload         | Enable auto-reload                               | False                       |
| --provider       | LLM Provider (openai, anthropic, google, etc)    | openai                      |
| --model-id       | LLM Model ID                                     | qwen3:4b                    |
| --base-url       | LLM Base URL (for OpenAI compatible providers)   | http://ollama.arpa/v1       |
| --api-key        | LLM API Key                                      | ollama                      |
| --mcp-url        | MCP Server URL to connect to                     | http://media-downloader-mcp.arpa/mcp |
| --allowed-tools  | List of allowed MCP tools                        | download_media              |
| --web            | Enable Pydantic AI Web UI                        | False                       |

#### Run A2A Server

```bash
media-downloader-agent --provider openai --model-id qwen2.5:7b --mcp-url http://localhost:8004/mcp
```

### Deploy A2A Server as a Service

```bash
docker run -e CMD=media-downloader-agent \
           -e PROVIDER=openai \
           -e MODEL_ID=qwen2.5:7b \
           -p 8000:8000 \
           my-media-downloader-image
```

### Deploy MCP Server as a Service

The MCP server can be deployed using Docker, with configurable authentication, middleware, and Eunomia authorization.

#### Using Docker Run

```bash
docker pull knucklessg1/media-downloader:latest

docker run -d \
  --name media-downloader-mcp \
  -p 8004:8004 \
  -e HOST=0.0.0.0 \
  -e PORT=8004 \
  -e TRANSPORT=http \
  -e AUTH_TYPE=none \
  -e EUNOMIA_TYPE=none \
  -e DOWNLOAD_DIRECTORY=/downloads \
  -e AUDIO_ONLY=false \
  -v "/home/genius/Downloads:/downloads" \
  knucklessg1/media-downloader:latest
```

For advanced authentication (e.g., JWT, OAuth Proxy, OIDC Proxy, Remote OAuth) or Eunomia, add the relevant environment variables:

```bash
docker run -d \
  --name media-downloader-mcp \
  -p 8004:8004 \
  -e HOST=0.0.0.0 \
  -e PORT=8004 \
  -e TRANSPORT=http \
  -e AUTH_TYPE=oidc-proxy \
  -e OIDC_CONFIG_URL=https://provider.com/.well-known/openid-configuration \
  -e OIDC_CLIENT_ID=your-client-id \
  -e OIDC_CLIENT_SECRET=your-client-secret \
  -e OIDC_BASE_URL=https://your-server.com \
  -e ALLOWED_CLIENT_REDIRECT_URIS=http://localhost:*,https://*.example.com/* \
  -e EUNOMIA_TYPE=embedded \
  -e EUNOMIA_POLICY_FILE=/app/mcp_policies.json \
  -e DOWNLOAD_DIRECTORY=/downloads \
  -e AUDIO_ONLY=false \
  -v "/home/genius/Downloads:/downloads" \
  knucklessg1/media-downloader:latest
```

#### Using Docker Compose

Create a `docker-compose.yml` file:

```yaml
services:
  media-downloader-mcp:
    image: knucklessg1/media-downloader:latest
    environment:
      - HOST=0.0.0.0
      - PORT=8004
      - TRANSPORT=http
      - AUTH_TYPE=none
      - EUNOMIA_TYPE=none
      - DOWNLOAD_DIRECTORY=/downloads
      - AUDIO_ONLY=false
    volumes:
      - "/home/genius/Downloads:/downloads"
    ports:
      - 8004:8004
```

For advanced setups with authentication and Eunomia:

```yaml
services:
  media-downloader-mcp:
    image: knucklessg1/media-downloader:latest
    environment:
      - HOST=0.0.0.0
      - PORT=8004
      - TRANSPORT=http
      - AUTH_TYPE=oidc-proxy
      - OIDC_CONFIG_URL=https://provider.com/.well-known/openid-configuration
      - OIDC_CLIENT_ID=your-client-id
      - OIDC_CLIENT_SECRET=your-client-secret
      - OIDC_BASE_URL=https://your-server.com
      - ALLOWED_CLIENT_REDIRECT_URIS=http://localhost:*,https://*.example.com/*
      - EUNOMIA_TYPE=embedded
      - EUNOMIA_POLICY_FILE=/app/mcp_policies.json
      - DOWNLOAD_DIRECTORY=/downloads
      - AUDIO_ONLY=false
    ports:
      - 8004:8004
    volumes:
      - ./mcp_policies.json:/app/mcp_policies.json
      - "/home/genius/Downloads:/downloads"
```

Run the service:

```bash
docker-compose up -d
```

#### Configure `mcp.json` for AI Integration


```json
{
  "mcpServers": {
    "media_downloader": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "media-downloader",
        "media-downloader-mcp"
      ],
      "env": {
        "DOWNLOAD_DIRECTORY": "~/Downloads", // Optional - Can be specified at prompt
        "AUDIO_ONLY": false // Optional - Can be specified at prompt
      },
      "timeout": 300000
    }
  }
}

```

## Install Python Package

```bash
python -m pip install --upgrade media-downloader
```

or

```bash
uv pip install --upgrade media-downloader
```


## Repository Owners

<img width="100%" height="180em" src="https://github-readme-stats.vercel.app/api?username=Knucklessg1&show_icons=true&hide_border=true&&count_private=true&include_all_commits=true" />

![GitHub followers](https://img.shields.io/github/followers/Knucklessg1)
![GitHub User's stars](https://img.shields.io/github/stars/Knucklessg1)
