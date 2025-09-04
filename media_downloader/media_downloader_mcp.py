#!/usr/bin/python
# coding: utf-8
import getopt
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
    true_values = {'t', 'true', 'y', 'yes', '1'}
    false_values = {'f', 'false', 'n', 'no', '0'}

    if normalized in true_values:
        return True
    elif normalized in false_values:
        return False
    else:
        raise ValueError(f"Cannot convert '{string}' to boolean")

environment_download_directory = os.environ.get("DOWNLOAD_DIRECTORY", None)
environment_audio_only = os.environ.get("AUDIO_ONLY", False)

if environment_audio_only:
    environment_audio_only = to_boolean(environment_audio_only)

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
        default=environment_download_directory),
    audio_only: Optional[bool] = Field(description="Downloads only the audio", default=environment_audio_only),
    ctx: Context = Field(description="MCP context for progress reporting.", default=None),
) -> str:
    """Downloads media from a given URL to the specified directory."""
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


def media_downloader_mcp(argv):
    transport = "stdio"
    host = "0.0.0.0"
    port = 8000
    try:
        opts, args = getopt.getopt(
            argv,
            "ht:h:p:",
            ["help", "transport=", "host=", "port="],
        )
    except getopt.GetoptError:
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            sys.exit()
        elif opt in ("-t", "--transport"):
            transport = arg
        elif opt in ("-h", "--host"):
            host = arg
        elif opt in ("-p", "--port"):
            try:
                port = int(arg)  # Attempt to convert port to integer
                if not (0 <= port <= 65535):  # Valid port range
                    print(f"Error: Port {arg} is out of valid range (0-65535).")
                    sys.exit(1)
            except ValueError:
                print(f"Error: Port {arg} is not a valid integer.")
                sys.exit(1)
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "http":
        mcp.run(transport="http", host=host, port=port)
    else:
        logger = logging.getLogger("MediaDownloader")
        logger.error("Transport not supported")
        sys.exit(1)


def main():
    media_downloader_mcp(sys.argv[1:])


if __name__ == "__main__":
    media_downloader_mcp(sys.argv[1:])
