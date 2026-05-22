# Media Downloader
## CLI or API | MCP | Agent

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

*Version: 2.15.0*

---

## Overview

**Media Downloader** is a production-grade Agent and Model Context Protocol (MCP) server designed to interface directly with Download audio/videos from the internet!
Host an MCP Server for Agentic AI to download videos!.

---

## Key Features

- **Consolidated Action-Routed MCP Tools:** Minimizes token overhead and eliminates tool bloat in LLM contexts by grouping methods into optimized, togglable tool modules.
- **Enterprise-Grade Security:** Comprehensive support for Eunomia policies, OIDC token delegation, and granular execution context tracking.
- **Integrated Graph Agent:** Built-in Pydantic AI agent supporting the Agent Control Protocol (ACP) and standard Web interfaces (AG-UI).
- **Native Telemetry & Tracing:** Out-of-the-box OpenTelemetry exports and native Langfuse tracing.

---

## CLI or API

This agent wraps the Download audio/videos from the internet!
Host an MCP Server for Agentic AI to download videos! API. You can interact with it programmatically or via its integrated execution entrypoints.

Detailed instructions on how to use the underlying API wrappers, extended schema bindings, and developer SDK references are maintained in [docs/index.md](file:///home/apps/workspace/agent-packages/agents/media-downloader/docs/index.md).

---

## MCP

This server utilizes dynamic Action-Routed tools to optimize token overhead and maximize IDE compatibility.

### Available MCP Tools

Detailed tool schemas, parameter shapes, and validation constraints are preserved in [docs/mcp.md](file:///home/apps/workspace/agent-packages/agents/media-downloader/docs/mcp.md).

### MCP Configuration Examples

#### stdio Transport (Recommended for local IDEs e.g., Cursor, Claude Desktop)
Configure your IDE's `mcp.json` to launch the MCP server via `uvx`:

```json
{
  "mcpServers": {
    "media-downloader": {
      "command": "uvx",
      "args": [
        "--from",
        "media-downloader",
        "media-downloader-mcp"
      ],
      "env": {
        "YT_DLP_PATH": "your_yt_dlp_path_here",
        "BREW_INSTALL_CMD": "your_brew_install_cmd_here"
      }
    }
  }
}
```

#### Streamable-HTTP Transport (Recommended for production deployments)
Configure your client's `mcp.json` to launch the Streamable-HTTP server via `uvx` with explicit host and port definition:

```json
{
  "mcpServers": {
    "media-downloader": {
      "command": "uvx",
      "args": [
        "--from",
        "media-downloader",
        "media-downloader-mcp"
      ],
      "env": {
        "TRANSPORT": "streamable-http",
        "HOST": "0.0.0.0",
        "PORT": "8000",
        "YT_DLP_PATH": "your_yt_dlp_path_here",
        "BREW_INSTALL_CMD": "your_brew_install_cmd_here"
      }
    }
  }
}
```

Alternatively, connect to a pre-deployed remote or local Streamable-HTTP instance:

```json
{
  "mcpServers": {
    "media-downloader": {
      "url": "http://localhost:8000/media-downloader/mcp"
    }
  }
}
```

Deploying the Streamable-HTTP server via Docker:

```bash
docker run -d \
  --name media-downloader-mcp \
  -p 8000:8000 \
  -e TRANSPORT=streamable-http \
  -e PORT=8000 \
  -e YT_DLP_PATH="your_value" \
  -e BREW_INSTALL_CMD="your_value" \
  knucklessg1/media-downloader:latest
```

---

## Agent

This repository features a fully integrated Pydantic AI Graph Agent. It communicates over the **Agent Control Protocol (ACP)** and interacts seamlessly with the **Agent Web UI (AG-UI)** and Terminal interface.

### Running the Agent CLI
To start the interactive command-line agent:

```bash
# Set credentials
export YT_DLP_PATH="your_value"
export BREW_INSTALL_CMD="your_value"

# Run the agent server
media-downloader-agent --provider openai --model-id gpt-4o
```

### Docker Compose Orchestration
The following `docker/agent.compose.yml` configures the Agent, Web UI, and Terminal Interface together:

```yaml
version: '3.8'

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
      start_period: 10s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  media-downloader-agent:
    image: knucklessg1/media-downloader:latest
    container_name: media-downloader-agent
    hostname: media-downloader-agent
    restart: always
    depends_on:
      - media-downloader-mcp
    env_file:
      - ../.env
    command: [ "media-downloader-agent" ]
    environment:
      - PYTHONUNBUFFERED=1
      - HOST=0.0.0.0
      - PORT=9000
      - MCP_URL=http://media-downloader-mcp:8000/mcp
      - PROVIDER=${PROVIDER:-openai}
      - MODEL_ID=${MODEL_ID:-gpt-4o}
      - ENABLE_WEB_UI=True
      - ENABLE_OTEL=True
    ports:
      - "9000:9000"
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:9000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

```

Detailed graph node architecture explanations, custom skill configurations, and agentic trace guides are available in [docs/agent.md](file:///home/apps/workspace/agent-packages/agents/media-downloader/docs/agent.md).

---

## Security & Governance

Built directly upon the enterprise-ready [`agent-utilities`](https://github.com/Knuckles-Team/agent-utilities) core, standard security parameters are fully supported:

### Access Control & Policy Enforcement
- **Eunomia Policies:** Fine-grained, policy-driven tool authorization. Supports `none`, local `embedded` (`mcp_policies.json`), or centralized `remote` modes.
- **OIDC Token Delegation:** Compliant with RFC 8693 token exchange for flowing authenticating user credentials from Web UI / ACP → Agent → MCP.
- **Scoped Credentials:** Execution context runs restricted to the specific caller identity.

### Runtime Security Grid
| Feature | Functionality | Enablement |
|---------|---------------|------------|
| **Tool Guard** | Sensitivity inspection with human-in-the-loop validation | Enabled by default |
| **Prompt Injection Defense** | Input scanning, repetition monitoring, and recursive loop blocks | Enabled by default |
| **Context Safety Guard** | Stuck-loop detectors and contextual overflow preemptive alerts | Enabled by default |

---

## Installation

Install the Python package locally:

```bash
# Using uv (highly recommended)
uv pip install media-downloader[all]

# Using standard pip
python -m pip install media-downloader[all]
```

---

## Repository Owners

<img width="100%" height="180em" src="https://github-readme-stats.vercel.app/api?username=Knucklessg1&show_icons=true&hide_border=true&&count_private=true&include_all_commits=true" />

![GitHub followers](https://img.shields.io/github/followers/Knucklessg1)
![GitHub User's stars](https://img.shields.io/github/stars/Knucklessg1)

---

## Contribute

Contributions are welcome! Please ensure code quality by executing local checks before submitting pull requests:
- Format code using `ruff format .`
- Lint code using `ruff check .`
- Validate type-safety with `mypy .`
- Execute test suites using `pytest`
