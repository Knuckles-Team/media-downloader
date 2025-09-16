#!/usr/bin/env python
# coding: utf-8

from media_downloader.media_downloader import (
    media_downloader,
    setup_logging,
    MediaDownloader,
)
from media_downloader.media_downloader_mcp import (
    media_downloader_mcp,
)

"""
media-downloader

Download videos and audio from the internet!
"""

__all__ = [
    "media_downloader",
    "media_downloader_mcp",
    "setup_logging",
    "MediaDownloader",
]
