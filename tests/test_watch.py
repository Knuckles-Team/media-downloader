"""Tests for the watch pipeline: captions, key frames, and the bundle manifest.

Every ffmpeg call and every network call is mocked; nothing here spawns a real
encoder or reaches a real site.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from media_downloader.security import MediaSecurityError
from media_downloader.watch import (
    build_frames,
    collect_captions,
    detect_scene_changes,
    extract_frames,
    parse_vtt,
    probe_duration,
    select_timestamps,
    watch_media,
    write_transcript,
)

ROLLUP_VTT = """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:03.000 align:start position:0%
first line here

00:00:03.000 --> 00:00:05.000 align:start position:0%
first line here
second <c>line</c> here

00:00:05.000 --> 00:00:07.000
second line here
third &amp; final

01:02:03.500 --> 01:02:05.000
much later
"""


# --------------------------------------------------------------------------- #
# Captions
# --------------------------------------------------------------------------- #
def test_parse_vtt_drops_rollup_repeats():
    """Auto-captions repeat the previous tail; the transcript must not."""
    cues = parse_vtt(ROLLUP_VTT)
    assert [c["text"] for c in cues] == [
        "first line here",
        "second line here",
        "third & final",
        "much later",
    ]


def test_parse_vtt_strips_markup_and_reads_hours():
    cues = parse_vtt(ROLLUP_VTT)
    # <c> tags removed, &amp; unescaped, and 01:02:03.500 is an hour in.
    assert "<c>" not in cues[1]["text"]
    assert cues[2]["text"] == "third & final"
    assert cues[3]["start"] == pytest.approx(3723.5)


def test_parse_vtt_ignores_a_header_only_file():
    assert parse_vtt("WEBVTT\n\nKind: captions\n") == []


def test_write_transcript_formats_timestamps(tmp_path):
    destination = tmp_path / "transcript.txt"
    count = write_transcript(parse_vtt(ROLLUP_VTT), destination)
    assert count == 4
    lines = destination.read_text().splitlines()
    assert lines[0] == "[00:00:01] first line here"
    assert lines[3] == "[01:02:03] much later"


def test_write_transcript_handles_no_cues(tmp_path):
    destination = tmp_path / "transcript.txt"
    assert write_transcript([], destination) == 0
    assert destination.read_text() == ""


def test_collect_captions_prefers_the_fullest_track(tmp_path):
    (tmp_path / "clip.en.vtt").write_text(ROLLUP_VTT, encoding="utf-8")
    (tmp_path / "clip.en-orig.vtt").write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nshort\n", encoding="utf-8"
    )
    info: dict = {"subtitles": {"en": [{}]}, "automatic_captions": {}}
    captions = collect_captions(tmp_path, info)
    assert captions["status"] == "present"
    assert captions["vtt_file"] == "clip.en.vtt"
    assert captions["language"] == "en"
    assert captions["source"] == "manual"
    assert captions["line_count"] == 4


def test_collect_captions_reports_missing_when_no_vtt(tmp_path):
    captions = collect_captions(tmp_path, {})
    assert captions["status"] == "missing"
    assert captions["transcript_file"] is None


def test_collect_captions_reports_missing_for_an_empty_track(tmp_path):
    (tmp_path / "clip.en.vtt").write_text("WEBVTT\n", encoding="utf-8")
    assert collect_captions(tmp_path, {})["status"] == "missing"


def test_collect_captions_marks_an_automatic_track(tmp_path):
    (tmp_path / "clip.en.vtt").write_text(ROLLUP_VTT, encoding="utf-8")
    info: dict = {"subtitles": {}, "automatic_captions": {"en": [{}]}}
    assert collect_captions(tmp_path, info)["source"] == "automatic"


# --------------------------------------------------------------------------- #
# Frame selection
# --------------------------------------------------------------------------- #
def _candidates(count):
    return [
        {"timestamp_s": float(i), "scene_score": (i % 10) / 10.0}
        for i in range(count)
    ]


def test_select_timestamps_keeps_the_highest_scoring_in_time_order():
    """The cap must keep the best scenes, not merely the first ones."""
    candidates = _candidates(30)
    chosen, mode = select_timestamps(candidates, 100.0, max_frames=5, min_frames=6)
    assert mode == "scene"
    assert len(chosen) == 5
    stamps = [c["timestamp_s"] for c in chosen]
    assert stamps == sorted(stamps), "frames must be chronological"
    # Nothing left behind may outrank anything kept.
    kept = {c["timestamp_s"] for c in chosen}
    dropped = [c for c in candidates if c["timestamp_s"] not in kept]
    assert min(c["scene_score"] for c in chosen) >= max(
        c["scene_score"] for c in dropped
    )
    # ... and the cap must not simply have taken the earliest detections.
    assert stamps != [c["timestamp_s"] for c in candidates[:5]]


def test_select_timestamps_falls_back_to_even_spacing():
    chosen, mode = select_timestamps(
        _candidates(2), 60.0, max_frames=24, min_frames=6
    )
    assert mode == "interval"
    assert [c["timestamp_s"] for c in chosen] == [
        pytest.approx(v) for v in (8.571, 17.143, 25.714, 34.286, 42.857, 51.429)
    ]
    assert all(c["scene_score"] is None for c in chosen)


def test_select_timestamps_without_a_duration_keeps_what_it_found():
    """No duration means no way to space frames, so the detections stand."""
    chosen, mode = select_timestamps(_candidates(2), None, max_frames=24, min_frames=6)
    assert mode == "scene"
    assert len(chosen) == 2


def test_select_timestamps_returns_nothing_for_an_empty_detection():
    chosen, mode = select_timestamps([], None, max_frames=24, min_frames=6)
    assert (chosen, mode) == ([], "scene")


# --------------------------------------------------------------------------- #
# ffmpeg wrappers
# --------------------------------------------------------------------------- #
FFMPEG_STDERR = """\
[Parsed_metadata_1 @ 0x1] frame:0    pts:30720   pts_time:2
[Parsed_metadata_1 @ 0x1] lavfi.scene_score=0.812345
[Parsed_metadata_1 @ 0x1] frame:1    pts:61440   pts_time:4.5
[Parsed_metadata_1 @ 0x1] lavfi.scene_score=0.400000
"""


@patch("media_downloader.watch._run")
def test_detect_scene_changes_parses_ffmpeg_metadata(mock_run):
    mock_run.return_value = subprocess.CompletedProcess([], 0, "", FFMPEG_STDERR)
    found = detect_scene_changes(Path("/tmp/x.mp4"), 0.3)
    assert found == [
        {"timestamp_s": 2.0, "scene_score": 0.812345},
        {"timestamp_s": 4.5, "scene_score": 0.4},
    ]


@patch("media_downloader.watch._run")
def test_detect_scene_changes_survives_empty_output(mock_run):
    mock_run.return_value = subprocess.CompletedProcess([], 1, "", "")
    assert detect_scene_changes(Path("/tmp/x.mp4"), 0.3) == []


@patch("media_downloader.watch._run")
def test_probe_duration_returns_none_on_unparseable_output(mock_run):
    mock_run.return_value = subprocess.CompletedProcess([], 1, "N/A", "")
    assert probe_duration(Path("/tmp/x.mp4")) is None


@patch("media_downloader.watch._run")
def test_extract_frames_names_files_after_their_timestamp(mock_run, tmp_path):
    frames_dir = tmp_path / "frames"

    def fake(command, timeout):
        Path(command[-1]).write_bytes(b"jpeg")
        return subprocess.CompletedProcess(command, 0, "", "")

    mock_run.side_effect = fake
    items = extract_frames(
        Path("/tmp/x.mp4"),
        [{"timestamp_s": 12.48, "scene_score": 0.9}],
        frames_dir,
    )
    assert items == [
        {
            "file": "frames/frame_0001_t00012.480.jpg",
            "timestamp_s": 12.48,
            "scene_score": 0.9,
        }
    ]
    assert (frames_dir / "frame_0001_t00012.480.jpg").exists()


@patch("media_downloader.watch._run")
def test_extract_frames_skips_a_failed_seek(mock_run, tmp_path):
    mock_run.return_value = subprocess.CompletedProcess([], 1, "", "boom")
    items = extract_frames(
        Path("/tmp/x.mp4"), [{"timestamp_s": 1.0, "scene_score": 0.9}], tmp_path / "f"
    )
    assert items == []


def test_extract_frames_makes_no_directory_without_timestamps(tmp_path):
    frames_dir = tmp_path / "frames"
    assert extract_frames(Path("/tmp/x.mp4"), [], frames_dir) == []
    assert not frames_dir.exists()


@patch("media_downloader.watch.ffmpeg_available", return_value=False)
def test_build_frames_degrades_without_ffmpeg(_mock_available, tmp_path):
    """A missing encoder must warn, not raise: captions are still worth having."""
    warnings: list[str] = []
    frames = build_frames(
        tmp_path / "x.mp4",
        tmp_path,
        max_frames=24,
        min_frames=6,
        scene_threshold=0.3,
        warnings=warnings,
    )
    assert frames["status"] == "unavailable"
    assert frames["count"] == 0
    assert any("ffmpeg" in w for w in warnings)


@patch("media_downloader.watch.extract_frames", return_value=[])
@patch("media_downloader.watch.detect_scene_changes", return_value=[])
@patch("media_downloader.watch.probe_duration", return_value=None)
@patch("media_downloader.watch.ffmpeg_available", return_value=True)
def test_build_frames_reports_when_nothing_was_extracted(
    _available, _duration, _detect, _extract, tmp_path
):
    warnings: list[str] = []
    frames = build_frames(
        tmp_path / "x.mp4",
        tmp_path,
        max_frames=24,
        min_frames=6,
        scene_threshold=0.3,
        warnings=warnings,
    )
    assert frames["status"] == "unavailable"
    assert warnings == ["ffmpeg produced no key frames for this media."]


# --------------------------------------------------------------------------- #
# watch_media
# --------------------------------------------------------------------------- #
class FakeDownloader:
    """Stands in for MediaDownloader: writes a media file, optional captions."""

    instances: list["FakeDownloader"] = []

    def __init__(self, links=None, download_directory=None, **kwargs):
        self.output_root = Path(download_directory).resolve()
        self.download_directory = str(self.output_root)
        self.last_kg_asset = None
        self.captions = ROLLUP_VTT
        self.fail = False
        self.extra_opts: dict | None = None
        FakeDownloader.instances.append(self)

    def download_video(self, link, extra_opts=None):
        self.extra_opts = extra_opts
        if self.fail:
            return None
        bundle = Path(self.download_directory)
        media = bundle / "Author - Title.mp4"
        media.write_bytes(b"video")
        (bundle / "Author - Title.info.json").write_text(
            json.dumps({"id": "abc123", "title": "Title", "uploader": "Author"})
        )
        if self.captions:
            (bundle / "Author - Title.en.vtt").write_text(self.captions)
        return str(media)


@pytest.fixture
def fake_downloader(tmp_path):
    FakeDownloader.instances.clear()
    with patch("media_downloader.watch.validate_media_url", side_effect=lambda u: u):
        with patch(
            "media_downloader.media_downloader.MediaDownloader", FakeDownloader
        ):
            yield


@patch("media_downloader.watch.ffmpeg_available", return_value=False)
@pytest.mark.usefixtures("fake_downloader")
def test_watch_media_writes_a_manifest(_available, tmp_path):
    manifest = watch_media("https://example.com/v", download_directory=str(tmp_path))
    bundle = Path(manifest["bundle_dir"])
    assert bundle.parent == tmp_path.resolve()
    assert bundle.name.startswith("watch-")
    on_disk = json.loads((bundle / "manifest.json").read_text())
    assert on_disk == manifest
    assert manifest["video"]["id"] == "abc123"
    assert manifest["media_file"] == "Author - Title.mp4"
    assert manifest["source_url"] == "https://example.com"


@patch("media_downloader.watch.ffmpeg_available", return_value=False)
@pytest.mark.usefixtures("fake_downloader")
def test_watch_media_requests_captions_and_metadata(
    _available, tmp_path
):
    watch_media("https://example.com/v", download_directory=str(tmp_path))
    opts = FakeDownloader.instances[0].extra_opts
    assert opts is not None
    assert opts["writesubtitles"] is True
    assert opts["writeautomaticsub"] is True
    assert opts["writeinfojson"] is True
    assert opts["subtitlesformat"] == "vtt"
    # A wildcard here asks a site for every translated track and earns a 429.
    assert all("*" not in lang for lang in opts["subtitleslangs"])


@patch("media_downloader.watch.ffmpeg_available", return_value=False)
@pytest.mark.usefixtures("fake_downloader")
def test_watch_media_is_partial_when_frames_are_unavailable(
    _available, tmp_path
):
    manifest = watch_media("https://example.com/v", download_directory=str(tmp_path))
    assert manifest["status"] == "partial"
    assert manifest["captions"]["status"] == "present"
    assert manifest["frames"]["status"] == "unavailable"


@patch("media_downloader.watch.ffmpeg_available", return_value=False)
@pytest.mark.usefixtures("fake_downloader")
def test_watch_media_bridges_to_audio_transcriber_without_captions(
    _available, tmp_path
):
    """No captions must name the fallback rather than silently transcribe."""
    FakeDownloader.instances.clear()

    class NoCaptions(FakeDownloader):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.captions = ""

    with patch("media_downloader.media_downloader.MediaDownloader", NoCaptions):
        manifest = watch_media(
            "https://example.com/v", download_directory=str(tmp_path)
        )

    captions = manifest["captions"]
    assert manifest["status"] == "partial"
    assert captions["status"] == "missing"
    fallback = captions["fallback"]
    assert fallback["skill"] == "audio-transcriber-transcription"
    assert fallback["tool"] == "transcribe_audio"
    # The named file has to exist, or the handoff cannot be acted on.
    assert (Path(manifest["bundle_dir"]) / fallback["arguments"]["audio_file"]).exists()
    assert any("audio-transcriber" in w for w in manifest["warnings"])


@patch("media_downloader.watch.extract_frames")
@patch("media_downloader.watch.detect_scene_changes")
@patch("media_downloader.watch.probe_duration", return_value=60.0)
@patch("media_downloader.watch.ffmpeg_available", return_value=True)
@pytest.mark.usefixtures("fake_downloader")
def test_watch_media_succeeds_with_captions_and_frames(
    _available, _duration, mock_detect, mock_extract, tmp_path
):
    mock_detect.return_value = _candidates(20)
    mock_extract.return_value = [
        {"file": "frames/frame_0001_t00002.000.jpg", "timestamp_s": 2.0,
         "scene_score": 0.9}
    ]
    manifest = watch_media(
        "https://example.com/v", download_directory=str(tmp_path), max_frames=1
    )
    assert manifest["status"] == "success"
    assert manifest["frames"]["mode"] == "scene"
    assert manifest["frames"]["count"] == 1
    assert manifest["warnings"] == []


@pytest.mark.usefixtures("fake_downloader")
def test_watch_media_reports_a_failed_download(tmp_path):
    class Failing(FakeDownloader):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fail = True

    with patch("media_downloader.media_downloader.MediaDownloader", Failing):
        manifest = watch_media(
            "https://example.com/v", download_directory=str(tmp_path)
        )
    assert manifest["status"] == "error"
    assert manifest["media_file"] is None
    assert manifest["captions"]["status"] == "missing"
    assert json.loads(
        (Path(manifest["bundle_dir"]) / "manifest.json").read_text()
    ) == manifest


def test_watch_media_rejects_a_bundle_outside_the_output_root(tmp_path):
    """Path containment is the boundary every written file has to cross."""

    class Escaping(FakeDownloader):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.output_root = Path(tmp_path / "elsewhere").resolve()

    with patch("media_downloader.watch.validate_media_url", side_effect=lambda u: u):
        with patch("media_downloader.media_downloader.MediaDownloader", Escaping):
            with pytest.raises(MediaSecurityError):
                watch_media("https://example.com/v", download_directory=str(tmp_path))


@patch("media_downloader.watch.ffmpeg_available", return_value=False)
@pytest.mark.usefixtures("fake_downloader")
def test_watch_media_reuses_the_bundle_for_the_same_url(
    _available, tmp_path
):
    first = watch_media("https://example.com/v", download_directory=str(tmp_path))
    second = watch_media("https://example.com/v", download_directory=str(tmp_path))
    other = watch_media("https://example.com/w", download_directory=str(tmp_path))
    assert first["bundle_dir"] == second["bundle_dir"]
    assert other["bundle_dir"] != first["bundle_dir"]


def test_watch_media_validates_the_url_before_writing_anything(tmp_path):
    with patch(
        "media_downloader.watch.validate_media_url",
        side_effect=MediaSecurityError("nope"),
    ):
        with pytest.raises(MediaSecurityError):
            watch_media("http://10.0.0.1/x", download_directory=str(tmp_path))
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------- #
# MediaDownloader.watch delegation
# --------------------------------------------------------------------------- #
@patch("media_downloader.watch.watch_media")
def test_downloader_watch_delegates(mock_watch, tmp_path):
    from media_downloader.media_downloader import MediaDownloader

    mock_watch.return_value = {"status": "success"}
    downloader = MediaDownloader(
        links=[], download_directory=str(tmp_path), output_root=str(tmp_path)
    )
    assert downloader.watch("https://example.com/v", max_frames=3) == {
        "status": "success"
    }
    kwargs = mock_watch.call_args.kwargs
    assert kwargs["max_frames"] == 3
    assert kwargs["scene_threshold"] == 0.3


@patch("media_downloader.watch.watch_media", return_value={})
def test_downloader_watch_applies_defaults(mock_watch, tmp_path):
    from media_downloader.media_downloader import MediaDownloader

    downloader = MediaDownloader(
        links=[], download_directory=str(tmp_path), output_root=str(tmp_path)
    )
    downloader.watch("https://example.com/v")
    assert mock_watch.call_args.kwargs["max_frames"] == 24


def test_download_video_merges_extra_opts(tmp_path):
    """extra_opts is the seam the watch pipeline rides on."""
    from media_downloader.media_downloader import MediaDownloader

    downloader = MediaDownloader(
        links=[], download_directory=str(tmp_path), output_root=str(tmp_path)
    )
    captured = {}

    class FakeYdl:
        def __init__(self, opts):
            captured.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, link, download=True):
            return {"id": "x"}

        def prepare_filename(self, info):
            return str(tmp_path / "x.mp4")

    with patch("media_downloader.media_downloader.SafeYoutubeDL", FakeYdl):
        with patch(
            "media_downloader.media_downloader.validate_media_url",
            side_effect=lambda u: u,
        ):
            downloader.ingest_to_kg = False
            downloader.download_video(
                "https://example.com/v", extra_opts={"writesubtitles": True}
            )
    assert captured["writesubtitles"] is True
    assert captured["noplaylist"] is True, "existing options must survive the merge"


def test_download_video_without_extra_opts_is_unchanged(tmp_path):
    from media_downloader.media_downloader import MediaDownloader

    downloader = MediaDownloader(
        links=[], download_directory=str(tmp_path), output_root=str(tmp_path)
    )
    captured = {}

    class FakeYdl:
        def __init__(self, opts):
            captured.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, link, download=True):
            return {"id": "x"}

        def prepare_filename(self, info):
            return str(tmp_path / "x.mp4")

    with patch("media_downloader.media_downloader.SafeYoutubeDL", FakeYdl):
        with patch(
            "media_downloader.media_downloader.validate_media_url",
            side_effect=lambda u: u,
        ):
            downloader.ingest_to_kg = False
            downloader.download_video("https://example.com/v")
    assert "writesubtitles" not in captured
