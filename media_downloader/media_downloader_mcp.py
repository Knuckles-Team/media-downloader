#!/usr/bin/python
# coding: utf-8
import argparse
import os
import sys
import logging
from typing import Optional
from media_downloader import MediaDownloader, setup_logging
from fastmcp import FastMCP, Context
from pydantic import Field

# Initialize logging for MCP server (logs to file)
setup_logging(is_mcp_server=True, log_file="media_downloader_mcp.log")

mcp = FastMCP(name="MediaDownloaderServer")


def to_boolean(string):
    # Normalize the string: strip whitespace and convert to lowercase
    normalized = str(string).strip().lower()

    # Define valid true/false values
    true_values = {"t", "true", "y", "yes", "1"}
    false_values = {"f", "false", "n", "no", "0"}

    if normalized in true_values:
        return True
    elif normalized in false_values:
        return False
    else:
        raise ValueError(f"Cannot convert '{string}' to boolean")


@mcp.tool(
    annotations={
        "title": "Download Media",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    tags={"collection_management"},
)
async def download_media(
    video_url: str = Field(description="Video URL to Download", default=None),
    download_directory: Optional[str] = Field(
        description="The directory where the media will be saved. If None, uses default directory.",
        default=os.environ.get("DOWNLOAD_DIRECTORY", None),
    ),
    audio_only: Optional[bool] = Field(
        description="Downloads only the audio",
        default=to_boolean(os.environ.get("AUDIO_ONLY", False)),
    ),
    ctx: Context = Field(
        description="MCP context for progress reporting.", default=None
    ),
) -> str:
    """
    Downloads media from a given URL to the specified directory. Download as a video or audio file
    Returns the location of the Downloaded file
    """
    logger = logging.getLogger("MediaDownloader")
    logger.debug(
        f"Starting download for URL: {video_url}, directory: {download_directory}, audio_only: {audio_only}"
    )

    try:
        if not video_url:
            raise ValueError("video_url must not be empty")

        download_directory = f'{os.path.expanduser("~")}/Downloads'
        os.makedirs(download_directory, exist_ok=True)

        downloader = MediaDownloader(
            download_directory=download_directory, audio=audio_only
        )

        # Set progress callback for yt_dlp
        async def progress_callback(progress, total=None):
            if ctx:
                await ctx.report_progress(progress=progress, total=total)
                logger.debug(f"Reported progress: {progress}/{total}")

        downloader.set_progress_callback(progress_callback)

        # Report initial progress
        if ctx:
            await ctx.report_progress(progress=0, total=100)
            logger.debug("Reported initial progress: 0/100")

        # Perform the download
        file_path = downloader.download_video(link=video_url)

        if not file_path or not os.path.exists(file_path):
            raise RuntimeError("Download failed or file not found")

        # Report completion
        if ctx:
            await ctx.report_progress(progress=100, total=100)
            logger.debug("Reported final progress: 100/100")

        logger.debug(f"Download completed, file path: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Failed to download media: {str(e)}")
        raise RuntimeError(f"Failed to download media: {str(e)}")


def media_downloader_mcp():
    parser = argparse.ArgumentParser(description="Run media downloader MCP server.")

    parser.add_argument(
        "-t",
        "--transport",
        default="stdio",
        choices=["stdio", "http", "sse"],
        help="Transport method: 'stdio', 'http', or 'sse' [legacy] (default: stdio)",
    )
    parser.add_argument(
        "-s",
        "--host",
        default="0.0.0.0",
        help="Host address for HTTP transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8000,
        help="Port number for HTTP transport (default: 8000)",
    )

    args = parser.parse_args()

    if args.port < 0 or args.port > 65535:
        print(f"Error: Port {args.port} is out of valid range (0-65535).")
        sys.exit(1)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        logger = logging.getLogger("MediaDownloader")
        logger.error("Transport not supported")
        sys.exit(1)


if __name__ == "__main__":
    media_downloader_mcp()
