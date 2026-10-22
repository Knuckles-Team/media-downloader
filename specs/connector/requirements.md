# CONN-MEDIA-DOWNLOADER — Requirements

Governing spec: [spec.md](spec.md).

| ID | Requirement | Acceptance |
|---|---|---|
| `CONN-MEDIA-DOWNLOADER-R001` | **Channel video links returned.** `MediaDownloader.get_channel_videos` in `media_downloader/media_downloader.py` must return the found video links, limited by `limit`. It must also queue them on `self.links`. It must return an empty list when no channel is found. | `test_get_channel_videos_returns_links` in `tests/test_coverage_booster.py` must show two returned links for `limit=2`, equal to `self.links`. |
