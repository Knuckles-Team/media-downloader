# Usage — MCP / API / CLI

`media-downloader` exposes the same capability three ways: as an **MCP tool** an agent
calls, as a **Python API** (`MediaDownloader`) you import, and as a **CLI**.

## As an MCP server

Once [deployed](deployment.md), the server registers the `download_media` tool and two
prompts. No external service is required — downloads run against any site `yt-dlp`
supports.

| Surface | Name | Purpose |
|---|---|---|
| Tool | `download_media` | Download video or audio (MP3) from a URL to a directory |
| Prompt | `download_video` | Compose a "download this video" request |
| Prompt | `download_audio` | Compose a "download this as audio only" request |

The `download_media` tool accepts:

| Parameter | Default | Meaning |
|---|---|---|
| `video_url` | — | URL of the video / media to download |
| `download_directory` | `.` | Directory to save the result |
| `audio_only` | `false` | Extract audio and convert to MP3 |

Example agent prompts that map onto the tool:

- *"Download this YouTube video to /data/videos"* → `download_media`
- *"Grab the audio from this Rumble link as an MP3"* → `download_media` with `audio_only=true`

## As a Python API

`MediaDownloader` (`media_downloader.media_downloader`) drives `yt-dlp` directly. It
handles parallel batch downloads, audio extraction, and per-download progress
callbacks.

```python
from media_downloader.media_downloader import MediaDownloader

downloader = MediaDownloader(
    links=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    download_directory="./Downloads",
    audio=False,
)

# Download every queued link in parallel; returns a downloaded file path
result = downloader.download_all()
print(result)
```

Audio-only (MP3) extraction:

```python
downloader = MediaDownloader(
    links=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    download_directory="./Music",
    audio=True,
)
downloader.download_all()
```

Queue URLs from a file, or enumerate a channel:

```python
downloader = MediaDownloader(download_directory="./Downloads")

downloader.open_file("urls.txt")            # one URL per line, de-duplicated
downloader.get_channel_videos("SomeChannel", limit=10)
downloader.download_all()
```

Report progress with a callback:

```python
def on_progress(progress, total=100):
    print(f"{progress:.0f}% of {total}")

downloader.set_progress_callback(on_progress)
downloader.download_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
```

## As a CLI

The `media-downloader` console script downloads from the command line:

```bash
# A comma-separated list of URLs
media-downloader --links "https://youtu.be/a,https://youtu.be/b" --directory ./Downloads

# Audio only (MP3)
media-downloader --audio --links "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Read URLs from a file
media-downloader --file urls.txt --directory ./Downloads

# Every video from a channel
media-downloader --channel "SomeChannel" --directory ./Downloads
```

| Flag | Meaning |
|---|---|
| `-l`, `--links` | Comma-separated list of URLs to download |
| `-f`, `--file` | Read URLs from a file (one per line) |
| `-c`, `--channel` | Download videos from a channel |
| `-d`, `--directory` | Target download directory |
| `-a`, `--audio` | Download audio only (MP3) |
| `--help` | Show usage |
