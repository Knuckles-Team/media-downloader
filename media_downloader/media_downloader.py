#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import argparse
import logging
import requests
import yt_dlp
from multiprocessing import Pool

__version__ = "2.1.36"


class YtDlpLogger:
    def __init__(self, logger):
        self.logger = logger

    def debug(self, msg):
        self.logger.debug(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)


class MediaDownloader:
    def __init__(
        self, links: list = [], download_directory: str = None, audio: bool = False
    ):
        self.links = links
        if download_directory:
            self.download_directory = download_directory
        else:
            self.download_directory = f'{os.path.expanduser("~")}/Downloads'
        self.audio = audio
        self.logger = logging.getLogger("MediaDownloader")
        self.progress_callback = None  # Store callback for progress updates

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def open_file(self, file):
        youtube_urls = open(file, "r")
        for url in youtube_urls:
            self.links.append(url)
        self.links = list(dict.fromkeys(self.links))

    def download_video(self, link):
        self.logger.debug(f"Downloading video: {link}")
        outtmpl = f"{self.download_directory}/%(uploader)s - %(title)s.%(ext)s"
        if "rumble.com" in link:
            self.logger.debug(f"Processing Rumble URL: {link}")
            rumble_url = requests.get(link)
            for rumble_embedded_url in rumble_url.text.split(","):
                if "embedUrl" in rumble_embedded_url:
                    rumble_embedded_url = re.sub(
                        '"', "", re.sub('"embedUrl":', "", rumble_embedded_url)
                    )
                    link = rumble_embedded_url
                    outtmpl = f"{self.download_directory}/%(title)s.%(ext)s"
                    self.logger.debug(f"Updated Rumble URL: {link}")

        ydl_opts = {
            "format": "bestaudio/best" if self.audio else "best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self.progress_hook],  # Add progress hook
            "logger": YtDlpLogger(self.logger),
        }
        if self.audio:
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }
            ]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                return ydl.prepare_filename(info)
        except Exception as e:
            self.logger.error(f"Failed to download {link}: {str(e)}")
            try:
                outtmpl = f"{self.download_directory}/%(id)s.%(ext)s"
                ydl_opts["outtmpl"] = outtmpl
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=True)
                    return ydl.prepare_filename(info)
            except Exception as e:
                self.logger.error(f"Retry failed for {link}: {str(e)}")
                return None

    def get_channel_videos(self, channel, limit=-1):
        self.logger.debug(f"Fetching videos for channel: {channel}, limit: {limit}")
        username = channel
        attempts = 0
        while attempts < 3:
            url = f"https://www.youtube.com/user/{username}/videos"
            self.logger.debug(f"Trying URL: {url}")
            page = requests.get(url).content
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
                self.logger.debug(f"Trying URL: {url}")
                page = requests.get(url).content
                data = str(page).split(" ")
                item = "https://i.ytimg.com/vi/"
                vids = []
                for line in data:
                    if item in line:
                        try:
                            found = re.search(
                                "https://i.ytimg.com/vi/(.+?)/hqdefault.", line
                            ).group(1)
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
        self.logger.error(f"Could not find user or channel: {channel}")

    def progress_hook(self, d):
        if self.progress_callback and d["status"] == "downloading":
            if d.get("total_bytes") and d.get("downloaded_bytes"):
                progress = (d["downloaded_bytes"] / d["total_bytes"]) * 100
                self.progress_callback(progress=progress, total=100)
            elif d.get("downloaded_bytes"):
                # Indeterminate progress if total_bytes is unavailable
                self.progress_callback(progress=d["downloaded_bytes"])
        elif d["status"] == "finished":
            if self.progress_callback:
                self.progress_callback(progress=100, total=100)

    def download_all(self):
        self.logger.debug(f"Downloading {len(self.links)} links")
        pool = Pool(processes=os.cpu_count())
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


def usage():
    print(f"media_downloader v{__version__}")
    print(
        "Media-Downloader: A tool to download any video off the internet!\n"
        "\nUsage:\n"
        "-h | --help      [ See usage ]\n"
        "-a | --audio     [ Download audio only ]\n"
        "-c | --channel   [ YouTube Channel/User - Downloads all videos ]\n"
        "-d | --directory [ Location where the images will be saved ]\n"
        "-f | --file      [ Text file to read the URLs from ]\n"
        "-l | --links     [ Comma separated URLs (No spaces) ]\n"
        "\nExample:\n"
        'media-downloader -f "file_of_urls.txt" -l "URL1,URL2,URL3" -c "WhiteHouse" -d "~/Downloads"\n'
    )


def media_downloader():
    parser = argparse.ArgumentParser(description="Download media from various sources.")
    parser.add_argument(
        "-a", "--audio", action="store_true", help="Download audio only"
    )
    parser.add_argument("-c", "--channel", help="Download videos from a channel URL")
    parser.add_argument("-d", "--directory", help="Specify download directory")
    parser.add_argument("-f", "--file", help="Read URLs from a file")
    parser.add_argument(
        "-l", "--links", help="Comma-separated list of URLs to download"
    )

    args = parser.parse_args()

    logger = logging.getLogger("MediaDownloader")
    logger.setLevel(logging.DEBUG)

    # Clear any existing handlers to avoid duplicate logs
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)

    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    video_downloader_instance = MediaDownloader()

    if args.audio:
        video_downloader_instance.audio = True
    if args.channel:
        video_downloader_instance.get_channel_videos(args.channel)
    if args.directory:
        video_downloader_instance.download_directory = args.directory
    if args.file:
        video_downloader_instance.open_file(args.file)
    if args.links:
        url_list = args.links.replace(" ", "").split(",")
        video_downloader_instance.links.extend(url_list)

    logger.info("Kicking off downloads...")
    video_downloader_instance.download_all()


if __name__ == "__main__":
    media_downloader()
