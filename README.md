# Media Downloader

![PyPI - Version](https://img.shields.io/pypi/v/media-downloader)
![PyPI - Downloads](https://img.shields.io/pypi/dd/media-downloader)
![GitHub Repo stars](https://img.shields.io/github/stars/Knuckles-Team/media-downloader)
![GitHub forks](https://img.shields.io/github/forks/Knuckles-Team/media-downloader)
![GitHub contributors](https://img.shields.io/github/contributors/Knuckles-Team/media-downloader)
![PyPI - License](https://img.shields.io/pypi/l/media-downloader)
![GitHub](https://img.shields.io/github/license/Knuckles-Team/media-downloader)

![GitHub last commit (by committer)](https://img.shields.io/github/last-commit/Knuckles-Team/media-downloader)
![GitHub pull requests](https://img.shields.io/github/issues-pr/Knuckles-Team/media-downloader)
![GitHub closed pull requests](https://img.shields.io/github/issues-pr-closed/Knuckles-Team/media-downloader)
![GitHub issues](https://img.shields.io/github/issues/Knuckles-Team/media-downloader)

![GitHub top language](https://img.shields.io/github/languages/top/Knuckles-Team/media-downloader)
![GitHub language count](https://img.shields.io/github/languages/count/Knuckles-Team/media-downloader)
![GitHub repo size](https://img.shields.io/github/repo-size/Knuckles-Team/media-downloader)
![GitHub repo file count (file type)](https://img.shields.io/github/directory-file-count/Knuckles-Team/media-downloader)
![PyPI - Wheel](https://img.shields.io/pypi/wheel/media-downloader)
![PyPI - Implementation](https://img.shields.io/pypi/implementation/media-downloader)

*Version: 0.11.5*

Download videos and audio from the internet!

This is a wrapper for the pytube library to simplify downloading from these various sources.

This repository is actively maintained - Contributions are welcome!

### Supports:
- YouTube
- Twitter
- Rumble
- BitChute
- Vimeo
- And More!

<details>
  <summary><b>Usage:</b></summary>

| Short Flag | Long Flag   | Description                                 |
|------------|-------------|---------------------------------------------|
| -h         | --help      | See usage                                   |
| -a         | --audio     | Download audio only                         |
| -c         | --channel   | YouTube Channel/User - Downloads all videos |
| -f         | --file      | File with video links                       |
| -l         | --links     | Comma separated links                       |
| -d         | --directory | Location to save videos                     |

</details>

<details>
  <summary><b>Example:</b></summary>

Run through CLI
```bash
media-downloader --file "C:\Users\videos.txt" --directory "C:\Users\Downloads" --channel "WhiteHouse" --links "URL1,URL2,URL3"
```

Use directly in Python
```python
# Import library
from media_downloader import MediaDownloader

# Set URL of video/audio here
url = "https://YootToob.com/video"

# Instantiate vide_downloader_instance
video_downloader_instance = MediaDownloader()

# Set the location to save the video
video_downloader_instance.set_save_path("C:/Users/you/Downloads")

# Add URL to download
video_downloader_instance.append_link(url)

# Download all videos appended
video_downloader_instance.download_all()
```

```python
# Optional - Set Audio to True, Default is False if unspecified.
video_downloader_instance.set_audio(audio=True)

# Optional - Open a file of video/audio URL(s)
video_downloader_instance.open_file("FILE")

# Optional - Enter a YouTube channel name and download their latest videos
video_downloader_instance.get_channel_videos("YT-Channel Name")
```
</details>

<details>
  <summary><b>Installation Instructions:</b></summary>

Install Python Package

```bash
python -m pip install media-downloader
```
</details>

## Geniusbot Application

Use with a GUI through Geniusbot

Visit our [GitHub](https://github.com/Knuckles-Team/geniusbot) for more information

<details>
  <summary><b>Installation Instructions with Geniusbot:</b></summary>

Install Python Package

```bash
python -m pip install geniusbot
```

</details>

<details>
  <summary><b>Repository Owners:</b></summary>


<img width="100%" height="180em" src="https://github-readme-stats.vercel.app/api?username=Knucklessg1&show_icons=true&hide_border=true&&count_private=true&include_all_commits=true" />

![GitHub followers](https://img.shields.io/github/followers/Knucklessg1)
![GitHub User's stars](https://img.shields.io/github/stars/Knucklessg1)
</details>
