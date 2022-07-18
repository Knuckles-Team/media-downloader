# Video Downloader  
*Version: 0.0.1*

Download videos from the internet!

### Usage:
| Short Flag | Long Flag   | Description                                  |
|------------|-------------|----------------------------------------------|
| -h         | --help      | See usage                                    |
| -c         | --channel   | YouTube Channel/User - Downloads all videos  |
| -f         | --file      | File with video links                        |
| -l         | --links     | Comma separated links                        |
| -d         | --directory | Location to save videos                      |


### Example:
```bash
video-downloader --file "C:\Users\videos.txt" --directory "C:\Users\Downloads" --channel "WhiteHouse" --links "URL1,URL2,URL3"
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
