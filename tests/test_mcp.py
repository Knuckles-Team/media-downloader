#!/usr/bin/python
# coding: utf-8
import subprocess
import json


def test_server(
    video_url: str, download_directory: str = ".", audio_only: bool = False
):
    payload = {
        "tool": "download_media",
        "args": {
            "video_url": video_url,
            "download_directory": download_directory,
            "audio_only": audio_only,
        },
    }
    try:
        # Run the server as a subprocess and pipe the JSON request
        process = subprocess.run(
            ["python", "-m", "media_downloader", "--transport=stdio"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
        )
        print("Server response:", process.stdout)
        if process.stderr:
            print("Errors:", process.stderr)
        # Parse the response to extract the result
        try:
            response = json.loads(process.stdout)
            if "result" in response:
                print(f"Downloaded file path: {response['result']}")
            elif "error" in response:
                print(f"Error: {response['error']}")
        except json.JSONDecodeError:
            print("Invalid JSON response:", process.stdout)
    except Exception as e:
        print(f"Failed to send request: {e}")


if __name__ == "__main__":
    # Replace with a valid URL supported by MediaDownloader
    test_server(
        video_url="https://www.youtube.com/watch?v=Tkv_guk57i0",
        download_directory="./downloads",
        audio_only=False,
    )
