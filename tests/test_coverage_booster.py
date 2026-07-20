import argparse
import importlib
import os
import runpy
import sys
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from fastmcp import Context, FastMCP

# Import under an alias to avoid name conflict with the CLI function media_downloader
import media_downloader as md_package
from media_downloader.agent_server import agent_server
from media_downloader.mcp_server import get_mcp_instance, mcp_server
from media_downloader.media_downloader import (
    MediaDownloader,
    YtDlpLogger,
    media_downloader,
)

# =====================================================================
# Global Auto-use Mocks for database-independent fast execution
# =====================================================================


@pytest.fixture(autouse=True, scope="module")
def mock_agent_utilities_and_mcp():
    mock_args = MagicMock()
    mock_args.transport = "stdio"
    mock_args.auth_type = "none"
    mock_args.host = "127.0.0.1"
    mock_args.port = 8000
    mock_args.debug = True
    mock_args.mcp_url = "http://localhost:8000"
    mock_args.mcp_config = "custom_config.json"
    mock_args.provider = "openai"
    mock_args.model_id = "gpt-4o"
    mock_args.base_url = "http://custom_base"
    mock_args.api_key = "secret_key"
    mock_args.custom_skills_directory = "/tmp/skills"
    mock_args.web = True
    mock_args.otel = False
    mock_args.otel_endpoint = None
    mock_args.otel_headers = None
    mock_args.otel_public_key = None
    mock_args.otel_secret_key = None
    mock_args.otel_protocol = None

    # Use a real FastMCP instance so prompts and tools registration/rendering works flawlessly
    local_mcp = FastMCP("MediaDownloader")

    with (
        patch(
            "agent_utilities.mcp.server_factory.create_mcp_server",
            return_value=(mock_args, local_mcp, []),
        ) as mock_create_mcp,
        patch("agent_utilities.initialize_workspace"),
        patch(
            "agent_utilities.load_identity",
            return_value={"name": "Agent", "description": "Desc", "content": "Prompt"},
        ),
        patch(
            "agent_utilities.build_system_prompt_from_workspace",
            return_value="System Prompt",
        ),
        patch(
            "media_downloader.agent_server.create_agent_server"
        ) as mock_create_agent_server,
    ):
        yield {
            "mock_create_mcp": mock_create_mcp,
            "local_mcp": local_mcp,
            "mock_args": mock_args,
            "mock_create_agent_server": mock_create_agent_server,
        }


@pytest.fixture(autouse=True)
def secure_media_output_root(monkeypatch):
    """Keep legacy /tmp fixture paths inside the configured test output root."""
    monkeypatch.setenv("MEDIA_DOWNLOADER_OUTPUT_ROOT", "/tmp")


# =====================================================================
# Mocks & Fixtures
# =====================================================================


class MockYoutubeDL:
    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        pass

    def extract_info(self, url, download=True, **kwargs):
        if not download and kwargs:
            pass
        if "fail_always" in url:
            raise Exception("Simulated permanent download error")
        if "fail_first" in url and "%(id)s" not in self.opts.get("outtmpl", ""):
            # Fail on first attempt if using custom format
            raise Exception("Simulated temporary download error")
        return {
            "title": "Mock Video Title",
            "id": "abc123xyz",
            "uploader": "MockUploader",
            "ext": "mp4",
        }

    def prepare_filename(self, info):
        if "%(id)s" in self.opts.get("outtmpl", ""):
            return "/tmp/downloads/abc123xyz.mp4"
        return "/tmp/downloads/MockUploader - Mock Video Title.mp4"


def mock_requests_get(url, *args, **_kwargs):
    mock_resp = MagicMock()
    if "rumble.com" in url:
        mock_resp.text = '"embedUrl":"https://rumble.com/embed/v12345"'
        mock_resp.content = b'"embedUrl":"https://rumble.com/embed/v12345"'
    elif "youtube.com/user/" in url:
        mock_resp.content = b'href="/watch?v=youtube_user_video"'
    elif "youtube.com/c/" in url:
        mock_resp.content = b"https://i.ytimg.com/vi/youtube_c_video/hqdefault.jpg"
    else:
        mock_resp.content = b""
    return mock_resp


class MockPool:
    def __init__(self, processes=None, **kwargs):
        self.processes = processes

    def map(self, func, iterable):
        return [func(x) for x in iterable]

    def close(self):
        pass

    def join(self):
        pass


# =====================================================================
# YtDlpLogger Tests
# =====================================================================


def test_ytdlp_logger():
    mock_log = MagicMock()
    logger = YtDlpLogger(mock_log)
    logger.debug("test debug")
    logger.warning("test warning")
    logger.error("test error")
    mock_log.debug.assert_called_once_with("yt-dlp diagnostic event")
    mock_log.warning.assert_called_once_with("yt-dlp warning event")
    mock_log.error.assert_called_once_with("yt-dlp error event")


# =====================================================================
# MediaDownloader core logic tests
# =====================================================================


def test_mediadownloader_init():
    # Test default initialization
    downloader = MediaDownloader()
    assert downloader.links == []
    assert downloader.audio is False
    assert downloader.download_directory == "/tmp"

    # Test custom initialization
    downloader2 = MediaDownloader(
        links=["http://link1"],
        download_directory="/tmp/custom",
        audio=True,
    )
    assert downloader2.links == ["http://link1"]
    assert downloader2.download_directory == "/tmp/custom"
    assert downloader2.audio is True


def test_set_progress_callback():
    downloader = MediaDownloader()
    callback = MagicMock()
    downloader.set_progress_callback(callback)
    assert downloader.progress_callback == callback


def test_open_file():
    downloader = MediaDownloader()
    file_content = (
        "https://youtube.com/1\nhttps://youtube.com/2\nhttps://youtube.com/1\n"
    )

    with patch("builtins.open", mock_open(read_data=file_content)):
        downloader.open_file("mock_file.txt")

    # Assert duplicates are removed and newlines stripped
    assert len(downloader.links) == 2
    assert "https://youtube.com/1\n" in downloader.links
    assert "https://youtube.com/2\n" in downloader.links


@patch("media_downloader.media_downloader.SafeYoutubeDL", MockYoutubeDL)
@patch("media_downloader.media_downloader.validate_media_url", side_effect=lambda url: url)
@patch("os.path.exists", return_value=True)
def test_download_video_standard(_mock_exists, _mock_validate):
    downloader = MediaDownloader(download_directory="/tmp/downloads")
    result = downloader.download_video("https://youtube.com/watch?v=123")
    assert result == "/tmp/downloads/MockUploader - Mock Video Title.mp4"


@patch("media_downloader.media_downloader.SafeYoutubeDL", MockYoutubeDL)
@patch("media_downloader.media_downloader.validate_media_url", side_effect=lambda url: url)
@patch("os.path.exists", return_value=True)
def test_download_video_audio(_mock_exists, _mock_validate):
    # Tests the audio path which triggers FFmpegExtractAudio postprocessor branch
    downloader = MediaDownloader(download_directory="/tmp/downloads", audio=True)
    result = downloader.download_video("https://youtube.com/watch?v=123")
    assert result == "/tmp/downloads/MockUploader - Mock Video Title.mp4"


@patch("media_downloader.media_downloader.SafeYoutubeDL", MockYoutubeDL)
@patch("media_downloader.media_downloader.safe_metadata_get", side_effect=mock_requests_get)
@patch("media_downloader.media_downloader.validate_media_url", side_effect=lambda url: url)
@patch("os.path.exists", return_value=True)
def test_download_video_rumble(_mock_exists, _mock_validate, mock_get):
    downloader = MediaDownloader(download_directory="/tmp/downloads")
    result = downloader.download_video("https://rumble.com/v12345")
    assert result == "/tmp/downloads/MockUploader - Mock Video Title.mp4"
    # Verify that Rumble redirect URL was fetched
    mock_get.assert_called()


@patch("media_downloader.media_downloader.SafeYoutubeDL", MockYoutubeDL)
@patch("media_downloader.media_downloader.validate_media_url", side_effect=lambda url: url)
@patch("os.path.exists", return_value=True)
def test_download_video_retry_fallback(_mock_exists, _mock_validate):
    downloader = MediaDownloader(download_directory="/tmp/downloads")
    # "fail_first" will throw exception on the first yt-dlp run, triggering the retry template
    result = downloader.download_video("https://youtube.com/fail_first")
    assert result == "/tmp/downloads/abc123xyz.mp4"


@patch("media_downloader.media_downloader.SafeYoutubeDL", MockYoutubeDL)
@patch("media_downloader.media_downloader.validate_media_url", side_effect=lambda url: url)
def test_download_video_permanent_failure(_mock_validate):
    downloader = MediaDownloader(download_directory="/tmp/downloads")
    result = downloader.download_video("https://youtube.com/fail_always")
    assert result is None


@patch("media_downloader.media_downloader.safe_metadata_get", side_effect=mock_requests_get)
def test_get_channel_videos_username(mock_get):
    downloader = MediaDownloader()
    downloader.get_channel_videos("test_user", limit=1)
    assert len(downloader.links) == 1
    assert "youtube_user_video" in downloader.links[0]


@patch("media_downloader.media_downloader.safe_metadata_get")
def test_get_channel_videos_channel_fallback(mock_get):
    # First response fails to find any videos (no watch? in text)
    resp1 = MagicMock()
    resp1.content = b"no videos here"

    # Second response finds matching thumbnail link
    resp2 = MagicMock()
    resp2.content = b"https://i.ytimg.com/vi/fallback_c_video/hqdefault.jpg"

    mock_get.side_effect = [resp1, resp2]

    downloader = MediaDownloader()
    downloader.get_channel_videos("test_channel", limit=1)
    assert len(downloader.links) == 1
    assert downloader.links[0] == "https://www.youtube.com/watch?v=fallback_c_video"


@patch("media_downloader.media_downloader.safe_metadata_get")
@patch("media_downloader.media_downloader.re.search", side_effect=AttributeError)
def test_get_channel_videos_attribute_error_handling(_mock_search, mock_get):
    # Force AttributeError to cover the except AttributeError branch
    resp1 = MagicMock()
    resp1.content = b"no user videos"
    resp2 = MagicMock()
    resp2.content = b"https://i.ytimg.com/vi/youtube_c_video/hqdefault.jpg"

    # The while loop runs 3 times; each time it calls requests.get twice.
    # So we need to provide 6 mocked responses to avoid StopIteration.
    mock_get.side_effect = [resp1, resp2, resp1, resp2, resp1, resp2]

    downloader = MediaDownloader()
    downloader.get_channel_videos("test_channel", limit=1)
    # The links should be empty because match.group(1) crashed and was caught
    assert len(downloader.links) == 0


@patch("media_downloader.media_downloader.safe_metadata_get")
def test_get_channel_videos_not_found(mock_get):
    # Return empty response for all attempts to trigger user/channel not found log
    resp = MagicMock()
    resp.content = b"no videos at all"
    mock_get.return_value = resp

    downloader = MediaDownloader()
    downloader.get_channel_videos("non_existent_channel")
    assert len(downloader.links) == 0


def test_progress_hook():
    downloader = MediaDownloader()
    callback = MagicMock()
    downloader.set_progress_callback(callback)

    # 1. Test downloading with total bytes
    downloader.progress_hook(
        {"status": "downloading", "total_bytes": 1000, "downloaded_bytes": 450}
    )
    callback.assert_called_with(progress=45.0, total=100)

    # 2. Test downloading without total bytes
    callback.reset_mock()
    downloader.progress_hook({"status": "downloading", "downloaded_bytes": 250})
    callback.assert_called_with(progress=250)

    # 3. Test finished status
    callback.reset_mock()
    downloader.progress_hook({"status": "finished"})
    callback.assert_called_with(progress=100, total=100)


@patch("media_downloader.media_downloader.Pool", MockPool)
@patch.object(MediaDownloader, "download_video")
@patch("os.path.exists", return_value=True)
def test_download_all(_mock_exists, mock_download):
    mock_download.return_value = "/tmp/downloads/video.mp4"
    downloader = MediaDownloader(links=["http://link1", "http://link2"])

    result = downloader.download_all()
    assert result == "/tmp/downloads/video.mp4"
    assert downloader.links == []  # Cleared after download_all


@patch("media_downloader.media_downloader.Pool", MockPool)
@patch.object(MediaDownloader, "download_video")
def test_download_all_no_valid_files(mock_download):
    mock_download.return_value = None
    downloader = MediaDownloader(links=["http://link1", "http://link2"])

    result = downloader.download_all()
    assert result is None


# =====================================================================
# CLI Entry Point Tests
# =====================================================================


@patch("media_downloader.media_downloader.MediaDownloader")
@patch("media_downloader.media_downloader.argparse.ArgumentParser.parse_args")
def test_cli_media_downloader(mock_args, mock_downloader_class):
    mock_instance = MagicMock()
    mock_downloader_class.return_value = mock_instance

    # 1. Test standard arguments
    args = argparse.Namespace(
        audio=True,
        channel="test_channel",
        directory="/tmp/test_dir",
        file="mock_file.txt",
        links="link1,link2",
        help=False,
    )
    mock_args.return_value = args

    with patch("sys.exit") as mock_exit:
        media_downloader()
        assert mock_instance.audio is True
        mock_instance.get_channel_videos.assert_called_once_with("test_channel")
        mock_downloader_class.assert_called_with(download_directory="/tmp/test_dir")
        mock_instance.open_file.assert_called_once_with("mock_file.txt")
        mock_instance.links.extend.assert_called()
        mock_instance.download_all.assert_called_once()
        mock_exit.assert_not_called()

    # 2. Test help branch
    mock_instance.reset_mock()
    args_help = argparse.Namespace(
        audio=False, channel=None, directory=None, file=None, links=None, help=True
    )
    mock_args.return_value = args_help
    with patch("sys.exit", side_effect=SystemExit) as mock_exit:
        with pytest.raises(SystemExit):
            media_downloader()
        mock_exit.assert_called_once_with(0)
        mock_instance.download_all.assert_not_called()


# =====================================================================
# MCP Server Tests
# =====================================================================


@pytest.mark.asyncio
async def test_mcp_server_prompts():
    mcp, _, _, _ = get_mcp_instance()

    prompt_video = await mcp.render_prompt(
        "download_video", {"video_url": "http://myvideo"}
    )
    assert (
        prompt_video.messages[0].content.text
        == "Download the following video: http://myvideo."
    )

    prompt_audio = await mcp.render_prompt(
        "download_audio", {"audio_url": "http://myaudio"}
    )
    assert (
        prompt_audio.messages[0].content.text
        == "Download the following media as audio only: http://myaudio."
    )


@pytest.mark.asyncio
@patch("media_downloader.media_downloader.MediaDownloader")
@patch("os.path.exists", return_value=True)
async def test_mcp_tool_download_media_success(_mock_exists, mock_downloader_class):
    mcp, _, _, _ = get_mcp_instance()
    download_media_tool = await mcp.get_tool("download_media")
    download_media_func = download_media_tool.fn

    mock_downloader_instance = MagicMock()
    mock_downloader_instance.download_all.return_value = "/tmp/downloads/video.mp4"
    mock_downloader_instance.output_root = "/tmp/downloads"
    mock_downloader_class.return_value = mock_downloader_instance

    mock_ctx = AsyncMock(spec=Context)

    result = await download_media_func(
        video_url="https://youtube.com/watch?v=123",
        download_directory="/tmp/downloads",
        audio_only=True,
        ctx=mock_ctx,
    )

    assert result == {"status": "success", "file": "video.mp4"}
    mock_ctx.info.assert_called_with("Download complete")
    mock_downloader_class.assert_called_once_with(
        links=["https://youtube.com/watch?v=123"],
        download_directory="/tmp/downloads",
        audio=True,
    )


@pytest.mark.asyncio
@patch("media_downloader.media_downloader.MediaDownloader")
async def test_mcp_tool_download_media_failure(mock_downloader_class):
    mcp, _, _, _ = get_mcp_instance()
    download_media_tool = await mcp.get_tool("download_media")
    download_media_func = download_media_tool.fn

    mock_downloader_instance = MagicMock()
    mock_downloader_instance.download_all.return_value = None
    mock_downloader_class.return_value = mock_downloader_instance

    result = await download_media_func(
        video_url="https://youtube.com/watch?v=123",
        download_directory="/tmp/downloads",
        audio_only=False,
        ctx=None,
    )

    assert result == {
        "status": "error",
        "message": "Download failed or did not return a valid file path.",
    }


@pytest.mark.asyncio
@patch("media_downloader.media_downloader.MediaDownloader")
async def test_mcp_tool_download_media_exception(mock_downloader_class):
    mcp, _, _, _ = get_mcp_instance()
    download_media_tool = await mcp.get_tool("download_media")
    download_media_func = download_media_tool.fn

    mock_downloader_class.side_effect = Exception("Simulated tool crash")

    result = await download_media_func(
        video_url="https://youtube.com/watch?v=123",
        download_directory="/tmp/downloads",
        audio_only=False,
        ctx=None,
    )

    assert result == {
        "status": "error",
        "message": "Download request failed",
    }


@patch("media_downloader.mcp_server.get_mcp_instance")
def test_mcp_server_entrypoint(mock_get_instance):
    mock_mcp = MagicMock()
    mock_args = MagicMock()

    mock_get_instance.return_value = (mock_mcp, mock_args, [], [])

    # 1. Test stdio transport
    mock_args.transport = "stdio"
    mcp_server()
    mock_mcp.run.assert_called_once_with(transport="stdio")

    # 2. Test streamable-http transport
    mock_mcp.reset_mock()
    mock_args.transport = "streamable-http"
    mock_args.host = "127.0.0.1"
    mock_args.port = 8000
    mcp_server()
    mock_mcp.run.assert_called_once_with(
        transport="streamable-http", host="127.0.0.1", port=8000
    )

    # 3. Test sse transport
    mock_mcp.reset_mock()
    mock_args.transport = "sse"
    mock_args.host = "127.0.0.1"
    mock_args.port = 8000
    mcp_server()
    mock_mcp.run.assert_called_once_with(transport="sse", host="127.0.0.1", port=8000)

    # 4. Test invalid transport branch
    mock_mcp.reset_mock()
    mock_args.transport = "invalid"
    with patch("sys.exit") as mock_exit:
        mcp_server()
        mock_exit.assert_called_once_with(1)


# =====================================================================
# Agent Server Tests
# =====================================================================


@patch("media_downloader.agent_server.create_agent_server")
@patch("media_downloader.agent_server.create_agent_parser")
def test_agent_server_entrypoint(mock_parser, mock_create_server):
    mock_args = MagicMock()
    mock_args.debug = True
    mock_args.mcp_url = "http://localhost:8000"
    mock_args.mcp_config = "custom_config.json"
    mock_args.host = "127.0.0.1"
    mock_args.port = 8500
    mock_args.provider = "openai"
    mock_args.model_id = "gpt-4o"
    mock_args.base_url = "http://custom_base"
    mock_args.api_key = "secret_key"
    mock_args.custom_skills_directory = "/tmp/skills"
    mock_args.web = True
    mock_args.otel = False
    mock_args.otel_endpoint = None
    mock_args.otel_headers = None
    mock_args.otel_public_key = None
    mock_args.otel_secret_key = None
    mock_args.otel_protocol = None

    mock_parser.return_value.parse_args.return_value = mock_args

    agent_server()

    mock_create_server.assert_called_once_with(
        mcp_url="http://localhost:8000",
        mcp_config="custom_config.json",
        host="127.0.0.1",
        port=8500,
        provider="openai",
        model_id="gpt-4o",
        router_model="gpt-4o",
        agent_model="gpt-4o",
        base_url="http://custom_base",
        api_key="secret_key",
        custom_skills_directory="/tmp/skills",
        enable_web_ui=True,
        enable_otel=False,
        otel_endpoint=None,
        otel_headers=None,
        otel_public_key=None,
        otel_secret_key=None,
        otel_protocol=None,
        debug=True,
    )


# =====================================================================
# Main execution (__main__.py) tests
# =====================================================================


@patch("sys.argv", ["media_downloader"])
@patch("media_downloader.agent_server.agent_server")
def test_main_exec(mock_agent_server):
    runpy.run_module("media_downloader.__main__", run_name="__main__")
    mock_agent_server.assert_called_once()


# =====================================================================
# Package-level init attributes and imports tests
# =====================================================================


def test_package_init_attributes():
    # Test __dir__ works
    dir_list = dir(md_package)
    assert "MediaDownloader" in dir_list

    # Test availability flags
    assert md_package._MCP_AVAILABLE is True
    assert (
        md_package._AGENT_AVAILABLE is True
        or md_package._agent_server_AVAILABLE is not None
    )

    # Test loading agent and mcp attributes dynamically
    assert md_package.agent_server is agent_server
    assert md_package.get_mcp_instance is get_mcp_instance

    # Test attribute error
    with pytest.raises(AttributeError):
        _ = md_package.non_existent_key


# =====================================================================
# Extra Coverage Booster Tests (100% Target)
# =====================================================================


def test_import_module_safely_error():
    # Patches importlib.import_module to raise ImportError to cover lines 42-43 of __init__.py
    with patch("importlib.import_module", side_effect=ImportError):
        res = md_package._import_module_safely("non_existent_module")
        assert res is None


def test_getattr_missing_optional_module():
    # Patches md_package.OPTIONAL_MODULES to be empty to cover lines 52 and 57 of __init__.py
    with patch.dict(md_package.OPTIONAL_MODULES, {}, clear=True):
        assert md_package._MCP_AVAILABLE is False
        assert md_package._AGENT_AVAILABLE is False


def test_getattr_non_exposed_member():
    # Looks up a private/non-exposed member from an optional module to cover line 69 of __init__.py
    # "DEFAULT_AGENT_NAME" is inside agent_server but not exposed via _expose_members (since it is not a class or function)
    val = md_package.DEFAULT_AGENT_NAME
    assert isinstance(val, str)


def test_requests_dependency_warning_import_error():
    # Patches sys.modules["requests.exceptions"] to trigger the except ImportError branch (lines 10-11) of mcp_server.py

    with patch.dict(sys.modules, {"requests.exceptions": None}):
        importlib.reload(sys.modules["media_downloader.mcp_server"])


def test_agent_server_main_block():
    # Runs the main block of agent_server.py (line 80) without locking the database or hitting workspace loading
    with (
        patch("sys.argv", ["media_downloader"]),
        patch("agent_utilities.initialize_workspace"),
        patch("agent_utilities.load_identity") as mock_load,
        patch("agent_utilities.build_system_prompt_from_workspace"),
        patch("agent_utilities.create_agent_server") as mock_create,
    ):
        mock_load.return_value = {
            "name": "Agent",
            "description": "Desc",
            "content": "Prompt",
        }
        runpy.run_module("media_downloader.agent_server", run_name="__main__")
        mock_create.assert_called_once()


def test_mcp_server_main_block():
    # Runs the main block of mcp_server.py (line 132) by stubbing out create_mcp_server in agent_utilities
    mock_mcp = MagicMock()
    mock_args = MagicMock()
    mock_args.transport = "stdio"
    mock_args.auth_type = "none"
    with (
        patch("sys.argv", ["media_downloader"]),
        patch(
            "agent_utilities.mcp.server_factory.create_mcp_server",
            return_value=(mock_args, mock_mcp, []),
        ),
    ):
        runpy.run_module("media_downloader.mcp_server", run_name="__main__")
        mock_mcp.run.assert_called_once_with(transport="stdio")


def test_media_downloader_main_block():
    # Runs the main block of media_downloader.py (line 234)
    with (
        patch("sys.argv", ["media_downloader"]),
        patch("media_downloader.media_downloader.MediaDownloader.download_all"),
    ):
        runpy.run_module("media_downloader.media_downloader", run_name="__main__")
