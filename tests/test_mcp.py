import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def video_url():
    return "https://www.youtube.com/watch?v=Tkv_guk57i0"


@pytest.fixture
def download_directory():
    return "./downloads"


@pytest.fixture
def audio_only():
    return False


def test_server(
    video_url: str, download_directory: str = ".", audio_only: bool = False
):
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "download_media",
            "arguments": {
                "video_url": video_url,
                "download_directory": download_directory,
                "audio_only": audio_only,
            },
        },
        "id": 1,
    }

    mock_stdout = json.dumps(
        {
            "jsonrpc": "2.0",
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "status": "success",
                                "file": f"{download_directory}/mock_video.mp4",
                            }
                        ),
                    }
                ]
            },
            "id": 1,
        }
    )

    with patch("subprocess.run") as mock_run:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = mock_stdout
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        process = subprocess.run(
            ["python", "-m", "media_downloader.mcp_server", "--transport=stdio"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
        )

        mock_run.assert_called_once_with(
            ["python", "-m", "media_downloader.mcp_server", "--transport=stdio"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
        )

        assert process.returncode == 0
        response = json.loads(process.stdout)
        assert "result" in response
        result_content = response["result"]["content"][0]["text"]
        result_dict = json.loads(result_content)
        assert result_dict["status"] == "success"
        assert "file" in result_dict
