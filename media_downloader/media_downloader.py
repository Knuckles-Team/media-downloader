#!/usr/bin/env python3


import argparse
import logging
import os
import re
import sys
from multiprocessing import Pool
from urllib.parse import urlsplit

import yt_dlp

from media_downloader.security import (
    MediaSecurityError,
    contained_output_path,
    public_source_url,
    resolve_output_directory,
    safe_metadata_get,
    validate_media_url,
)

__version__ = "3.0.1"


class YtDlpLogger:
    def __init__(self, logger):
        self.logger = logger

    def debug(self, msg):
        self.logger.debug("yt-dlp diagnostic event")

    def warning(self, msg):
        self.logger.warning("yt-dlp warning event")

    def error(self, msg):
        self.logger.error("yt-dlp error event")


class SafeYoutubeDL(yt_dlp.YoutubeDL):
    """Revalidate every URL crossing yt-dlp's central request boundary."""

    def urlopen(self, req):
        request_url = req if isinstance(req, str) else getattr(req, "url", None)
        if not request_url:
            raise MediaSecurityError("Downloader request omitted its URL")
        validate_media_url(request_url)
        response = super().urlopen(req)
        final_url = getattr(response, "url", None)
        if final_url:
            validate_media_url(final_url)
        return response


class MediaDownloader:
    def __init__(
        self,
        links: list | None = None,
        download_directory: str | None = None,
        audio: bool = False,
        ingest_to_kg: bool = True,
        output_root: str | None = None,
    ):
        self.links = links if links is not None else []
        self.output_root, output_directory = resolve_output_directory(
            download_directory, output_root=output_root
        )
        self.download_directory = str(output_directory)
        self.audio = audio
        # Native KG ingestion is on by default; it auto-no-ops when no epistemic-graph
        # engine is reachable, so it costs nothing without KG infrastructure.
        self.ingest_to_kg = ingest_to_kg
        self.last_kg_asset: dict | None = None
        self.logger = logging.getLogger("MediaDownloader")
        self.progress_callback = None

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def open_file(self, file):
        youtube_urls = open(file)
        for url in youtube_urls:
            self.links.append(url)
        self.links = list(dict.fromkeys(self.links))

    def download_video(self, link):
        link = validate_media_url(link.strip())
        self.logger.debug("Downloading media from host %s", urlsplit(link).hostname)
        outtmpl = f"{self.download_directory}/%(uploader)s - %(title)s.%(ext)s"
        host = (urlsplit(link).hostname or "").lower()
        if host == "rumble.com" or host.endswith(".rumble.com"):
            self.logger.debug("Processing Rumble media URL")
            rumble_url = safe_metadata_get(link, timeout=10)
            for rumble_embedded_url in rumble_url.text.split(","):
                if "embedUrl" in rumble_embedded_url:
                    rumble_embedded_url = re.sub(
                        '"', "", re.sub('"embedUrl":', "", rumble_embedded_url)
                    )
                    link = validate_media_url(rumble_embedded_url.strip())
                    outtmpl = f"{self.download_directory}/%(title)s.%(ext)s"
                    self.logger.debug("Validated the embedded Rumble media URL")

        ydl_opts = {
            "format": "bestaudio/best" if self.audio else "best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self.progress_hook],
            "logger": YtDlpLogger(self.logger),
            "restrictfilenames": True,
            "windowsfilenames": True,
            "noplaylist": True,
        }
        if self.audio:
            ydl_opts["postprocessors"] = [
                {  # type: ignore
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }
            ]

        try:
            with SafeYoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                path = ydl.prepare_filename(info)
                path = str(contained_output_path(path, self.output_root))
                self._maybe_ingest(path, info, link)
                return path
        except Exception as e:
            self.logger.error("Media download failed (%s)", type(e).__name__)
            try:
                outtmpl = f"{self.download_directory}/%(id)s.%(ext)s"
                ydl_opts["outtmpl"] = outtmpl
                with SafeYoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=True)
                    path = ydl.prepare_filename(info)
                    path = str(contained_output_path(path, self.output_root))
                    self._maybe_ingest(path, info, link)
                    return path
            except Exception as e:
                self.logger.error("Media download retry failed (%s)", type(e).__name__)
                return None

    def _maybe_ingest(self, path, info, link):
        """Natively store a freshly downloaded file into the knowledge graph.

        Default-on and best-effort: no-ops when ``ingest_to_kg`` is off or no live
        epistemic-graph engine is reachable. Records the result on
        ``self.last_kg_asset`` (``{asset_id, digest, size_bytes, media_type}``).
        """
        if not self.ingest_to_kg or not path:
            return
        from media_downloader.kg_media import ingest_media_file

        self.last_kg_asset = ingest_media_file(
            path, info=info, source_url=public_source_url(link)
        )

    def get_channel_videos(self, channel, limit=-1):
        self.logger.debug("Fetching videos for a channel (limit=%s)", limit)
        username = channel
        attempts = 0
        while attempts < 3:
            url = f"https://www.youtube.com/user/{username}/videos"
            self.logger.debug("Trying a canonical YouTube channel URL")
            page = safe_metadata_get(url, timeout=10).content
            data = str(page).split(" ")
            item = 'href="/watch?'
            vids = [
                line.replace('href="', "youtube.com") for line in data if item in line
            ]
            if vids:
                self.logger.debug(f"Found {len(vids)} videos")
                x = 0
                for vid in vids:
                    if limit < 0 or x < limit:
                        self.links.append(vid)
                    x += 1
                return
            else:
                url = f"https://www.youtube.com/c/{channel}/videos"
                self.logger.debug("Trying the alternate canonical YouTube channel URL")
                page = safe_metadata_get(url, timeout=10).content
                data = str(page).split(" ")
                item = "https://i.ytimg.com/vi/"
                vids = []
                for line in data:
                    if item in line:
                        try:
                            match = re.search(
                                "https://i.ytimg.com/vi/(.+?)/hqdefault.", line
                            )
                            if match:
                                found = match.group(1)
                                vid = f"https://www.youtube.com/watch?v={found}"
                                vids.append(vid)
                        except AttributeError:
                            continue
                if vids:
                    self.logger.debug(f"Found {len(vids)} videos")
                    x = 0
                    for vid in vids:
                        if limit < 0 or x < limit:
                            self.links.append(vid)
                        x += 1
                    return
            attempts += 1
        self.logger.error("Could not find the requested channel")

    def progress_hook(self, d):
        if self.progress_callback and d["status"] == "downloading":
            if d.get("total_bytes") and d.get("downloaded_bytes"):
                progress = (d["downloaded_bytes"] / d["total_bytes"]) * 100
                self.progress_callback(progress=progress, total=100)
            elif d.get("downloaded_bytes"):
                self.progress_callback(progress=d["downloaded_bytes"])
        elif d["status"] == "finished":
            if self.progress_callback:
                self.progress_callback(progress=100, total=100)

    def download_all(self):
        self.logger.debug(f"Downloading {len(self.links)} links")
        if len(self.links) > 1_000:
            raise MediaSecurityError("Media link count limit exceeded")
        max_workers = max(1, min(int(os.environ.get("MEDIA_DOWNLOADER_MAX_WORKERS", "4")), 4))
        worker_count = min(max_workers, max(1, len(self.links)))
        pool = Pool(processes=worker_count)
        try:
            results = pool.map(self.download_video, self.links)
            self.links = []
            for result in results:
                if result and os.path.exists(result):
                    return result
            return None
        finally:
            pool.close()
            pool.join()


def media_downloader():
    parser = argparse.ArgumentParser(
        add_help=False, description="Download media from various sources."
    )
    parser.add_argument(
        "-a", "--audio", action="store_true", help="Download audio only"
    )
    parser.add_argument("-c", "--channel", help="Download videos from a channel URL")
    parser.add_argument("-d", "--directory", help="Specify download directory")
    parser.add_argument("-f", "--file", help="Read URLs from a file")
    parser.add_argument(
        "-l", "--links", help="Comma-separated list of URLs to download"
    )

    parser.add_argument("--help", action="store_true", help="Show usage")

    args = parser.parse_args()

    if hasattr(args, "help") and args.help:
        parser.print_help()
        sys.exit(0)

    logger = logging.getLogger("MediaDownloader")
    logger.setLevel(logging.DEBUG)

    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)

    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    video_downloader_instance = MediaDownloader(download_directory=args.directory)

    if args.audio:
        video_downloader_instance.audio = True
    if args.channel:
        video_downloader_instance.get_channel_videos(args.channel)
    if args.file:
        video_downloader_instance.open_file(args.file)
    if args.links:
        url_list = args.links.replace(" ", "").split(",")
        video_downloader_instance.links.extend(url_list)

    logger.info("Kicking off downloads...")
    video_downloader_instance.download_all()


if __name__ == "__main__":
    media_downloader()
