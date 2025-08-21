#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import getopt
import logging
import requests
import yt_dlp
from multiprocessing import Pool


# Configure logging
def setup_logging(is_mcp_server=False, log_file="media_downloader.log"):
    logger = logging.getLogger("MediaDownloader")
    logger.setLevel(logging.DEBUG)

    # Clear any existing handlers to avoid duplicate logs
    logger.handlers.clear()

    if is_mcp_server:
        # Log to a file when running as MCP server
        handler = logging.FileHandler(log_file)
    else:
        # Log to console (stdout) when running standalone
        handler = logging.StreamHandler(sys.stdout)

    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


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
                        self.append_link(vid)
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
                            self.append_link(vid)
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


def media_downloader(argv):
    logger = setup_logging(is_mcp_server=False)
    video_downloader_instance = MediaDownloader()
    try:
        opts, args = getopt.getopt(
            argv,
            "hac:d:f:l:",
            ["help", "audio", "channel=", "directory=", "file=", "links="],
        )
    except getopt.GetoptError:
        usage()
        logger.error("Incorrect arguments")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-a", "--audio"):
            video_downloader_instance.audio = True
        elif opt in ("-c", "--channel"):
            video_downloader_instance.get_channel_videos(arg)
        elif opt in ("-d", "--directory"):
            video_downloader_instance.download_directory = arg
        elif opt in ("-f", "--file"):
            video_downloader_instance.open_file(arg)
        elif opt in ("-l", "--links"):
            url_list = arg.replace(" ", "").split(",")
            for url in url_list:
                video_downloader_instance.links.extend(url_list)

    video_downloader_instance.download_all()


def usage():
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


def main():
    media_downloader(sys.argv[1:])


if __name__ == "__main__":
    media_downloader(sys.argv[1:])
