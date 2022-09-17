#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import getopt
import requests
import youtube_dl
from multiprocessing import Pool


class StdOutLogger(object):
    def debug(self, msg):
        print(f'{msg}')

    def warning(self, msg):
        print(f'{msg}')

    def error(self, msg):
        print(f'{msg}')


class MediaDownloader:

    def __init__(self):
        self.links = []
        self.download_directory = f'{os.path.expanduser("~")}/Downloads'
        self.audio = False

    def open_file(self, file):
        youtube_urls = open(file, 'r')
        for url in youtube_urls:
            self.links.append(url)
        self.links = list(dict.fromkeys(self.links))

    def get_save_path(self):
        return self.download_directory

    def set_save_path(self, download_directory):
        self.download_directory = download_directory
        self.download_directory = self.download_directory.replace(os.sep, '/')

    def reset_links(self):
        print("Links Reset")
        self.links = []

    def extend_links(self, urls):
        print("URL Extended: ", urls)
        self.links.extend(urls)
        self.links = list(dict.fromkeys(self.links))

    def append_link(self, url):
        print("URL Appended: ", url)
        self.links.append(url)
        self.links = list(dict.fromkeys(self.links))

    def get_links(self):
        return self.links

    def set_audio(self, audio=False):
        self.audio = audio

    def download_all(self):
        pool = Pool(processes=os.cpu_count())
        try:
            pool.map(self.download_video, self.links)
        finally:
            pool.close()
            pool.join()
        self.reset_links()

    def download_video(self, link):
        outtmpl = f'{self.download_directory}/%(uploader)s - %(title)s.%(ext)s'
        if "rumble.com" in link:
                rumble_url = requests.get(link)
                for rumble_embedded_url in rumble_url.text.split(","):
                    if "embedUrl" in rumble_embedded_url:
                        rumble_embedded_url = re.sub('"', '', re.sub('"embedUrl":', '', rumble_embedded_url))
                        link = rumble_embedded_url
                        outtmpl = f'{self.download_directory}/%(title)s.%(ext)s'

        if self.audio:
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'progress_with_newline': True,
                'logger': StdOutLogger(),
                'outtmpl': outtmpl
            }
        else:
            ydl_opts = {
                'format': 'best',
                'progress_with_newline': True,
                'logger': StdOutLogger(),
                'outtmpl': outtmpl
            }
        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                print(ydl.download([link]))
        except Exception as e:
            try:
                if self.audio:
                    outtmpl = f'{self.download_directory}/%(id)s.%(ext)s'
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'progress_with_newline': True,
                        'logger': StdOutLogger(),
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '320',
                        }],
                        'outtmpl': outtmpl
                    }
                else:
                    ydl_opts = {
                        'format': 'best',
                        'progress_with_newline': True,
                        'logger': StdOutLogger(),
                        'outtmpl': outtmpl
                    }
                with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                    print(ydl.download([link]))
            except Exception as e:
                print(f"Unable to download video: {link}")

    def get_channel_videos(self, channel, limit=-1):
        vids = None
        username = channel
        attempts = 0
        while attempts < 3:
            url = f"https://www.youtube.com/user/{username}/videos"
            page = requests.get(url).content
            data = str(page).split(' ')
            item = 'href="/watch?'
            vids = [line.replace('href="', 'youtube.com') for line in data if
                    item in line]  # list of all videos listed twice
            # print(vids)  # index the latest video
            x = 0
            if vids:
                # print("Link Set")
                for vid in vids:
                    if limit < 0:
                        self.links.append(vid)
                    elif x >= limit:
                        break
                    else:
                        self.links.append(vid)
                    x += 1
            else:
                url = f"https://www.youtube.com/c/{channel}/videos"
                print("URL: ", url)
                page = requests.get(url).content
                print("Page: ", page)
                data = str(page).split(' ')
                print("Data: ", data)
                item = 'https://i.ytimg.com/vi/'
                vids = []
                for line in data:
                    if item in line:
                        vid = line
                        #vid = line.replace('https://i.ytimg.com/vi/', '')
                        try:
                            found = re.search('https://i.ytimg.com/vi/(.+?)/hqdefault.', vid).group(1)
                        except AttributeError:
                            # AAA, ZZZ not found in the original string
                            found = ''  # apply your error handling
                        print("Vid, ", vid)
                        vid = f"https://www.youtube.com/watch?v={found}"
                        vids.append(vid)
                print(vids)  # index the latest video
                x = 0
                if vids:
                    # print("Link Set")
                    for vid in vids:
                        if limit < 0:
                            self.links.append(vid)
                        elif x >= limit:
                            break
                        else:
                            self.links.append(vid)
                        x += 1
                else:
                    print("Trying Old Method")
                    vids = [line.replace('href="', 'youtube.com') for line in data if
                            item in line]  # list of all videos listed twice
                    if vids:
                        for vid in vids:
                            if limit < 0:
                                self.links.append(vid)
                            elif x >= limit:
                                break
                            else:
                                self.links.append(vid)
                            x += 1
                    else:
                        print("Could not find User or Channel")
            attempts += 1


def media_downloader(argv):
    video_downloader_instance = MediaDownloader()
    audio_only = False
    try:
        opts, args = getopt.getopt(argv, "hac:d:f:l:", ["help", "audio", "channel=", "directory=", "file=", "links="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-a", "--audio"):
            video_downloader_instance.set_audio(audio=True)
        elif opt in ("-c", "--channel"):
            video_downloader_instance.get_channel_videos(arg)
        elif opt in ("-d", "--directory"):
            video_downloader_instance.set_save_path(arg)
        elif opt in ("-f", "--file"):
            video_downloader_instance.open_file(arg)
        elif opt in ("-l", "--links"):
            url_list = arg.replace(" ", "")
            url_list = url_list.split(",")
            for url in url_list:
                video_downloader_instance.append_link(url)

    video_downloader_instance.download_all()


def usage():
    print(f'Usage:\n'
          f'-h | --help      [ See usage ]\n'
          f'-a | --audio     [ Download audio only ]\n'
          f'-c | --channel   [ YouTube Channel/User - Downloads all videos ]\n'
          f'-d | --directory [ Location where the images will be saved ]\n'
          f'-f | --file      [ Text file to read the URLs from ]\n'
          f'-l | --links     [ Comma separated URLs (No spaces) ]\n'
          f'\n'
          f'media-downloader -f "file_of_urls.txt" -l "URL1,URL2,URL3" -c "WhiteHouse" -d "~/Downloads"\n')


def main():
    media_downloader(sys.argv[1:])


if __name__ == "__main__":
    media_downloader(sys.argv[1:])
