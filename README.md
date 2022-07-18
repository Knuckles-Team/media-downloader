# Video Downloader  
*Version: 0.0.1*

Download videos from the internet!

### Usage:
| Short Flag | Long Flag | Description              |
| --- | ------|--------------------------|
| -h | --help | See Usage                |
| -f | --file | Subtitle File            |
| -m | --mode | + / -                    |
| -t | --time | Time in seconds to shift |

### Example:
```bash
video-downloader --file videos.txt --download-directory "C:\Users\Downloads"
```


#### Build Instructions
Build Python Package

```bash
sudo chmod +x ./*.py
sudo pip install .
python3 setup.py bdist_wheel --universal
# Test Pypi
twine upload --repository-url https://test.pypi.org/legacy/ dist/*
# Prod Pypi
twine upload dist/*
```
