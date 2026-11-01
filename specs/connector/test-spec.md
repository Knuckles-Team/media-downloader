# CONN-MEDIA-DOWNLOADER — Test specification

Governing spec: [spec.md](spec.md).

| Test ID | Requirement | Proving test | Expected observation |
|---|---|---|---|
| T-001 | `CONN-MEDIA-DOWNLOADER-R001` | covered by the child rows | `test_get_channel_videos_returns_links` in `tests/test_coverage_booster.py` must show two returned links for `limit=2`, equal to `self.links`. |
| T-002 | `CONN-MEDIA-DOWNLOADER-R001.1` | `tests/test_coverage_booster.py::test_get_channel_videos_reads_embedded_video_ids` | `test_get_channel_videos_reads_embedded_video_ids` in `tests/test_coverage_booster.py` must show two unique watch links for `limit=2`. |

## Negative and boundary cases

Each proving test above includes the refusal or error case that its row names. A vendor outage or an unauthorised call must return the SDK typed error.

## Quality and release proof

Run `uv run pytest tests` and `pre-commit run --all-files` from the repository root. A planned test is added by the code change that lands the row.
