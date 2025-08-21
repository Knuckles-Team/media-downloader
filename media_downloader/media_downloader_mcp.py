#!/usr/bin/python
# coding: utf-8
import getopt
import os
import sys
from media_downloader import MediaDownloader
from fastmcp import FastMCP

mcp = FastMCP(
    name="MediaDownloaderServer",
)


@mcp.tool()
async def download_media(
    video_url: str, download_directory: str = ".", audio_only: bool = False
) -> str:
    """Downloads media from a given URL to the specified directory.

    Args:
        video_url (str): The URL of the media to download.
        download_directory (str): The directory where the media will be saved.
        audio_only (bool): If True, downloads only the audio. Defaults to False.

    Returns:
        str: The path to the downloaded media file.

    Raises:
        ValueError: If the URL or directory is invalid.
        RuntimeError: If the download fails.
    """
    try:
        # Validate inputs
        if not video_url or not download_directory:
            raise ValueError("video_url and download_directory must not be empty")

        # Ensure the download directory exists
        os.makedirs(download_directory, exist_ok=True)

        # Initialize MediaDownloader
        downloader = MediaDownloader()
        downloader.set_audio(audio=audio_only)
        downloader.set_save_path(download_directory)
        downloader.append_link(video_url)

        # Perform the download
        downloader.download_all()

        # Assume download_all() saves the file and the path can be retrieved
        # Adjust this based on actual MediaDownloader behavior
        save_path = os.path.join(download_directory, video_url.split("/")[-1])
        if not os.path.exists(save_path):
            raise RuntimeError("Download failed or file not found")

        return download_directory
    except Exception as e:
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
            port = arg
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "http":
        mcp.run(transport="http", host=host, port=port)
    else:
        print("Transport not supported")
        sys.exit(1)

def client():
    # Connect to the server (update host/port if using http)
    client = MCPClient(host="localhost", port=5000)

    # Call the download_media tool
    response = client.call_tool(
        "download_media",
        {
            "video_url": "https://example.com/video.mp4",
            "download_directory": "./downloads",
            "audio_only": False,
        },
    )

    print(f"Downloaded file path: {response}")


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    media_downloader_mcp(sys.argv[1:])
