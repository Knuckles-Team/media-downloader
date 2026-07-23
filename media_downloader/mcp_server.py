import warnings

# Filter RequestsDependencyWarning early to prevent log spam
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    try:
        from requests.exceptions import RequestsDependencyWarning

        warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
    except ImportError:
        pass

# General urllib3/chardet mismatch warnings
warnings.filterwarnings("ignore", message=".*urllib3.*or chardet.*")
warnings.filterwarnings("ignore", message=".*urllib3.*or charset_normalizer.*")
"""
Media Downloader MCP Server.

Wraps the MediaDownloader class using yt-dlp to download video or audio from various platforms.
"""

import logging
import os
import sys
from typing import Any

from agent_utilities.core.config import load_config
from agent_utilities.mcp.server_factory import create_mcp_server
from agent_utilities.mcp.verbose_tools import register_tool_surface
from fastmcp import Context, FastMCP
from fastmcp.utilities.logging import get_logger
from pydantic import Field

from media_downloader.media_downloader import MediaDownloader

__version__ = "4.0.0"

logger = get_logger("MediaDownloaderMCPServer")
logger.setLevel(logging.INFO)


def get_client() -> MediaDownloader:
    """Return a lightweight MediaDownloader client for the tool surface."""
    return MediaDownloader(links=[])


def register_prompts(mcp: FastMCP):
    @mcp.prompt
    def download_video(video_url: str) -> str:
        """Generates a prompt for downloading a video."""
        return f"Download the following video: {video_url}."

    @mcp.prompt
    def download_audio(audio_url: str) -> str:
        """Generates a prompt for downloading audio."""
        return f"Download the following media as audio only: {audio_url}."


def get_mcp_instance() -> tuple[Any, Any, Any, list[str]]:
    """Initialize and return the MCP instance, args, and middlewares."""
    load_config()

    args, mcp, middlewares = create_mcp_server(
        name="MediaDownloader",
        version=__version__,
        instructions="Media Downloader MCP Server - Download videos and audio from various platforms.",
    )

    @mcp.tool(name="download_media")
    async def download_media(
        video_url: str = Field(description="URL of the video/media to download"),
        download_directory: str = Field(
            default=".", description="Directory to save downloads"
        ),
        audio_only: bool = Field(
            default=False, description="Extract audio and convert to MP3"
        ),
        ctx: Context | None = Field(
            default=None, description="MCP context for progress reporting"
        ),
    ) -> dict:
        """Download video or audio from supported sites (YouTube, Rumble, etc.)."""
        if ctx:
            await ctx.info("Downloading the requested media URL")

        try:
            from media_downloader.media_downloader import MediaDownloader

            downloader = MediaDownloader(
                links=[video_url],
                download_directory=download_directory,
                audio=audio_only,
            )

            result_file = downloader.download_all()
            if result_file and os.path.exists(result_file):
                relative_file = os.path.relpath(
                    result_file, downloader.output_root
                ).replace(os.sep, "/")
                if ctx:
                    await ctx.info(f"Download complete: {relative_file}")
                resp: dict[str, Any] = {"status": "success", "file": relative_file}
                # Native epistemic-graph ingestion result (blob + :MediaAsset), when
                # a live engine was reachable; None otherwise. CONCEPT:AU-KG.ingest.list-durable-media
                if downloader.last_kg_asset:
                    resp["kg_asset"] = downloader.last_kg_asset
                return resp
            else:
                return {
                    "status": "error",
                    "message": "Download failed or did not return a valid file path.",
                }
        except Exception as e:
            logger.error("Download error (%s)", type(e).__name__)
            return {"status": "error", "message": "Download request failed"}

    registered_tags = register_tool_surface(
        mcp,
        client_cls=MediaDownloader,
        get_client=get_client,
        service="media-downloader",
        tools_module=sys.modules[__name__],
    )

    register_prompts(mcp)

    for mw in middlewares:
        mcp.add_middleware(mw)
    return mcp, args, middlewares, registered_tags


def mcp_server() -> None:
    mcp, args, middlewares, registered_tags = get_mcp_instance()
    print(f"{'media-downloader'} MCP v{__version__}", file=sys.stderr)
    print("\nStarting MCP Server", file=sys.stderr)
    print(f"  Transport: {args.transport.upper()}", file=sys.stderr)
    print(f"  Auth: {args.auth_type}", file=sys.stderr)
    print(f"  Dynamic Tags Loaded: {len(set(registered_tags))}", file=sys.stderr)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        logger.error("Invalid transport", extra={"transport": args.transport})
        sys.exit(1)


if __name__ == "__main__":
    mcp_server()
