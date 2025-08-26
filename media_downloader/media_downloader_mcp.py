#!/usr/bin/python
# coding: utf-8
import getopt
import os
import sys
import logging
from typing import Optional
from media_downloader import MediaDownloader, setup_logging
from fastmcp import FastMCP, Context

# Initialize logging for MCP server (logs to file)
setup_logging(is_mcp_server=True, log_file="media_downloader_mcp.log")

mcp = FastMCP(name="MediaDownloaderServer")

environment_download_directory = os.environ.get("DOWNLOAD_DIRECTORY", None)
environment_audio_only = os.environ.get("AUDIO_ONLY", False)


@mcp.tool()
async def download_media(
    video_url: str,
    download_directory: Optional[str] = environment_download_directory,
    audio_only: Optional[bool] = environment_audio_only,
    ctx: Context = None,
) -> str:
    """Downloads media from a given URL to the specified directory.

    Args:
        video_url (str): The URL of the media to download.
        download_directory (Optional[str]): The directory where the media will be saved. If None, uses default directory.
        audio_only (bool): If True, downloads only the audio. Defaults to False.
        ctx (Context, optional): MCP context for progress reporting.

    Returns:
        str: The path to the downloaded media file.

    Raises:
        ValueError: If the URL is invalid.
        RuntimeError: If the download fails.
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
