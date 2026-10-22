# CONN-MEDIA-DOWNLOADER — Requirements

Governing spec: [spec.md](spec.md).

| ID | Requirement | Acceptance |
|---|---|---|
| `CONN-MEDIA-DOWNLOADER-R001` | **Channel video links returned.** `MediaDownloader.get_channel_videos` in `media_downloader/media_downloader.py` must return the found video links, limited by `limit`. It must also queue them on `self.links`. It must return an empty list when no channel is found. | `test_get_channel_videos_returns_links` in `tests/test_coverage_booster.py` must show two returned links for `limit=2`, equal to `self.links`. |
| `CONN-MEDIA-DOWNLOADER-R001.1` | **Embedded video IDs read.** `_canonical_channel_video_links` in `media_downloader/media_downloader.py` must read the `videoId` values from the page's embedded initial data when the page has no `href="/watch?` anchors. It must keep page order and drop duplicates. | `test_get_channel_videos_reads_embedded_video_ids` in `tests/test_coverage_booster.py` must show two unique watch links for `limit=2`. |
