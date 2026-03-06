#!/usr/bin/python
# coding: utf-8
from dotenv import load_dotenv, find_dotenv
import os
import sys
import logging
from typing import Optional, Dict, Any, List

import subprocess
from starlette.requests import Request
from starlette.responses import JSONResponse
from pydantic import Field
from fastmcp import FastMCP, Context
from fastmcp.utilities.logging import get_logger
from media_downloader.media_downloader import MediaDownloader
from agent_utilities.base_utilities import to_boolean
from agent_utilities.mcp_utilities import (
    create_mcp_server,
    config,
)

__version__ = "2.2.26"

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = get_logger("MediaDownloaderMCPServer")


def register_misc_tools(mcp: FastMCP):
    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "OK"})


def register_collection_management_tools(mcp: FastMCP):
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
    async def run_command(
        command: str = Field(description="The command to run"),
        ctx: Context = Field(
            description="MCP context for progress reporting.", default=None
        ),
    ) -> Dict[str, Any]:
        """
        Run a bash command on the local system.
        """
        logger.debug(f"Running command: {command}")
        if ctx:
            await ctx.report_progress(progress=0, total=100)
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, check=False
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            if ctx:
                await ctx.report_progress(progress=100, total=100)
            return {
                "status": 200 if result.returncode == 0 else 500,
                "output": output,
                "return_code": result.returncode,
            }
        except Exception as e:
            return {"status": 500, "error": str(e)}

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
    ) -> Dict[str, Any]:
        """
        Downloads media from a given URL to the specified directory. Download as a video or audio file.
        Returns a Dictionary response with status, download directory, audio only, and other details.
        """
        logger.debug(
            f"Starting download for URL: {video_url}, directory: {download_directory}, audio_only: {audio_only}"
        )

        try:
            if not video_url:
                return {
                    "status": 400,
                    "message": "Invalid input: video_url must not be empty",
                    "data": {
                        "video_url": video_url,
                        "download_directory": download_directory,
                        "audio_only": audio_only,
                    },
                    "error": "video_url must not be empty",
                }

            if download_directory:
                download_directory = os.path.expanduser(download_directory)
            else:
                download_directory = f'{os.path.expanduser("~")}/Downloads'
            os.makedirs(download_directory, exist_ok=True)

            downloader = MediaDownloader(
                download_directory=download_directory, audio=audio_only
            )

            async def progress_callback(progress, total=None):
                if ctx:
                    await ctx.report_progress(progress=progress, total=total)
                    logger.debug(f"Reported progress: {progress}/{total}")

            downloader.set_progress_callback(progress_callback)

            if ctx:
                await ctx.report_progress(progress=0, total=100)
                logger.debug("Reported initial progress: 0/100")

            file_path = downloader.download_video(link=video_url)

            if not file_path or not os.path.exists(file_path):
                return {
                    "status": 500,
                    "message": "Download failed: file not found",
                    "data": {
                        "video_url": video_url,
                        "download_directory": download_directory,
                        "audio_only": audio_only,
                    },
                    "error": "Download failed or file not found",
                }

            if ctx:
                await ctx.report_progress(progress=100, total=100)
                logger.debug("Reported final progress: 100/100")

            logger.debug(f"Download completed, file path: {file_path}")
            return {
                "status": 200,
                "message": "Media downloaded successfully",
                "data": {
                    "file_path": file_path,
                    "download_directory": download_directory,
                    "audio_only": audio_only,
                    "video_url": video_url,
                },
            }
        except Exception as e:
            logger.error(
                f"Failed to download media: {str(e)}\nParams: video_url: {video_url}, download directory: {download_directory}, audio only: {audio_only}"
            )
            return {
                "status": 500,
                "message": "Failed to download media",
                "data": {
                    "video_url": video_url,
                    "download_directory": download_directory,
                    "audio_only": audio_only,
                },
                "error": str(e),
            }


def register_text_editor_tools(mcp: FastMCP):
    @mcp.tool(
        annotations={
            "title": "Text Editor",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        tags={"text_editor", "files"},
    )
    async def text_editor(
        command: str = Field(
            description="The command to perform: view, create, str_replace, insert, undo_edit"
        ),
        path: str = Field(description="Path to the file"),
        file_text: Optional[str] = Field(
            description="Content to write or insert", default=None
        ),
        view_range: Optional[List[int]] = Field(
            description="Line range to view [start, end]", default=None
        ),
        old_str: Optional[str] = Field(description="String to replace", default=None),
        new_str: Optional[str] = Field(description="Replacement string", default=None),
        insert_line: Optional[int] = Field(
            description="Line number to insert at", default=None
        ),
        ctx: Context = Field(
            description="MCP context for progress reporting.", default=None
        ),
    ) -> Dict[str, Any]:
        """
        View and edit files on the local filesystem.
        """
        logger.debug(f"Text editor command: {command} on {path}")
        expanded_path = os.path.abspath(os.path.expanduser(path))

        try:
            if command == "view":
                if not os.path.exists(expanded_path):
                    return {"status": 404, "error": "File not found"}
                with open(expanded_path, "r") as f:
                    lines = f.readlines()
                content = "".join(lines)
                if view_range and len(view_range) == 2:
                    start, end = view_range
                    start = max(1, start)
                    end = min(len(lines), end)
                    content = "".join(lines[start - 1 : end])
                return {"status": 200, "content": content, "path": expanded_path}

            elif command == "create":
                if os.path.exists(expanded_path):
                    return {"status": 400, "error": "File already exists"}
                os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
                with open(expanded_path, "w") as f:
                    f.write(file_text or "")
                return {"status": 200, "message": "File created", "path": expanded_path}

            elif command == "str_replace":
                if not os.path.exists(expanded_path):
                    return {"status": 404, "error": "File not found"}
                with open(expanded_path, "r") as f:
                    content = f.read()
                if old_str not in content:
                    return {"status": 400, "error": "Target string not found"}
                new_content = content.replace(old_str, new_str or "", 1)
                with open(expanded_path, "w") as f:
                    f.write(new_content)
                return {"status": 200, "message": "File updated", "path": expanded_path}

            elif command == "insert":
                if not os.path.exists(expanded_path):
                    return {"status": 404, "error": "File not found"}
                with open(expanded_path, "r") as f:
                    lines = f.readlines()
                if insert_line is None:
                    return {"status": 400, "error": "insert_line required"}
                idx = max(0, insert_line)
                new_lines = file_text.splitlines(keepends=True)
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines[-1] += "\n"

                lines[idx:idx] = new_lines
                with open(expanded_path, "w") as f:
                    f.writelines(lines)
                return {
                    "status": 200,
                    "message": "Content inserted",
                    "path": expanded_path,
                }

            return {"status": 400, "error": f"Unknown command {command}"}

        except Exception as e:
            return {"status": 500, "error": str(e)}


def register_prompts(mcp: FastMCP):
    @mcp.prompt
    def download_video(video_url) -> str:
        """
        Generates a prompt for downloading a video.
        """
        return f"Download the following video: {video_url}."

    @mcp.prompt
    def download_audio(audio_url) -> str:
        """
        Generates a prompt for downloading audio.
        """
        return f"Download the following media as audio only: {audio_url}."


def mcp_server():
    load_dotenv(find_dotenv())

    args, mcp, middlewares = create_mcp_server(
        name="MediaDownloader",
        version=__version__,
        instructions="Media Downloader MCP Server - Download videos and audio from various platforms.",
    )

    DEFAULT_MISCTOOL = to_boolean(os.getenv("MISCTOOL", "True"))
    if DEFAULT_MISCTOOL:
        register_misc_tools(mcp)
    DEFAULT_COLLECTION_MANAGEMENTTOOL = to_boolean(
        os.getenv("COLLECTION_MANAGEMENTTOOL", "True")
    )
    if DEFAULT_COLLECTION_MANAGEMENTTOOL:
        register_collection_management_tools(mcp)
    DEFAULT_TEXT_EDITORTOOL = to_boolean(os.getenv("TEXT_EDITORTOOL", "True"))
    if DEFAULT_TEXT_EDITORTOOL:
        register_text_editor_tools(mcp)
    register_prompts(mcp)

    for mw in middlewares:
        mcp.add_middleware(mw)

    print(f"Media Downloader MCP v{__version__}")
    print("\nStarting Media Downloader MCP Server")
    print(f"  Transport: {args.transport.upper()}")
    print(f"  Auth: {args.auth_type}")
    print(f"  Delegation: {'ON' if config['enable_delegation'] else 'OFF'}")
    print(f"  Eunomia: {args.eunomia_type}")

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
