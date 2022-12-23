#!/usr/bin/env python
# coding: utf-8

from setuptools import setup
from media_downloader.version import __version__, __author__
from pathlib import Path
import re


readme = Path('README.md').read_text()
version = __version__
readme = re.sub(r"Version: [0-9]*\.[0-9]*\.[0-9][0-9]*", f"Version: {version}", readme)
print(f"README: {readme}")
with open("README.md", "w") as readme_file:
    readme_file.write(readme)
description = 'Download audio/videos from the internet!'

setup(
    name='media-downloader',
    version=f"{version}",
    description=description,
    long_description=f'{readme}',
    long_description_content_type='text/markdown',
    url='https://github.com/Knuckles-Team/media-downloader',
    author=__author__,
    author_email='knucklessg1@gmail.com',
    license='Unlicense',
    packages=['media_downloader'],
    include_package_data=True,
    install_requires=['youtube-dl>=2021.12.17', 'requests>=2.28.1'],
    py_modules=['media_downloader'],
    package_data={'media_downloader': ['media_downloader']},
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: Public Domain',
        'Environment :: Console',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
    entry_points={'console_scripts': ['media-downloader = media_downloader.media_downloader:main']},
)
