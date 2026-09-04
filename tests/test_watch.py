"""Tests for the watch pipeline: captions, key frames, and the bundle manifest.

Every ffmpeg call and every network call is mocked; nothing here spawns a real
encoder or reaches a real site.
"""

import json
import subprocess

import yaml
from pathlib import Path
from unittest.mock import patch

import pytest

from media_downloader.security import MediaSecurityError
from media_downloader.media_downloader import (
    MediaDownloader,
    build_skill,
    find_watch_skills,
    skill_sources,
    build_frames,
    collect_captions,
    detect_scene_changes,
    extract_frames,
    parse_vtt,
    probe_duration,
    select_timestamps,
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


@patch("media_downloader.media_downloader._run")
def test_detect_scene_changes_parses_ffmpeg_metadata(mock_run):
    mock_run.return_value = subprocess.CompletedProcess([], 0, "", FFMPEG_STDERR)
    found = detect_scene_changes(Path("/tmp/x.mp4"), 0.3)
    assert found == [
        {"timestamp_s": 2.0, "scene_score": 0.812345},
        {"timestamp_s": 4.5, "scene_score": 0.4},
    ]


@patch("media_downloader.media_downloader._run")
def test_detect_scene_changes_survives_empty_output(mock_run):
    mock_run.return_value = subprocess.CompletedProcess([], 1, "", "")
    assert detect_scene_changes(Path("/tmp/x.mp4"), 0.3) == []


@patch("media_downloader.media_downloader._run")
def test_probe_duration_returns_none_on_unparseable_output(mock_run):
    mock_run.return_value = subprocess.CompletedProcess([], 1, "N/A", "")
    assert probe_duration(Path("/tmp/x.mp4")) is None


@patch("media_downloader.media_downloader._run")
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


@patch("media_downloader.media_downloader._run")
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


@patch("media_downloader.media_downloader.ffmpeg_available", return_value=False)
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


@patch("media_downloader.media_downloader.extract_frames", return_value=[])
@patch("media_downloader.media_downloader.detect_scene_changes", return_value=[])
@patch("media_downloader.media_downloader.probe_duration", return_value=None)
@patch("media_downloader.media_downloader.ffmpeg_available", return_value=True)
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
# --------------------------------------------------------------------------- #
# MediaDownloader.watch
# --------------------------------------------------------------------------- #
@pytest.fixture
def downloader(tmp_path):
    """A real MediaDownloader rooted at tmp_path, with URL validation stubbed."""
    with patch(
        "media_downloader.media_downloader.validate_media_url", side_effect=lambda u: u
    ):
        yield MediaDownloader(
            links=[],
            download_directory=str(tmp_path),
            output_root=str(tmp_path),
            ingest_to_kg=False,
        )


def _stub_download(downloader, *, captions=ROLLUP_VTT, fail=False):
    """Replace download_video with one writing into whatever bundle is current."""
    state: dict = {"extra_opts": None, "directory": None}

    def _download(link, extra_opts=None):
        state["extra_opts"] = extra_opts
        state["directory"] = downloader.download_directory
        if fail:
            return None
        bundle = Path(downloader.download_directory)
        media = bundle / "Author - Title.mp4"
        media.write_bytes(b"video")
        (bundle / "Author - Title.info.json").write_text(
            json.dumps({"id": "abc123", "title": "Title", "uploader": "Author"})
        )
        if captions:
            (bundle / "Author - Title.en.vtt").write_text(captions)
        return str(media)

    downloader.download_video = _download
    return state


@patch("media_downloader.media_downloader.ffmpeg_available", return_value=False)
def test_watch_writes_a_manifest(_available, downloader, tmp_path):
    _stub_download(downloader)
    manifest = downloader.watch("https://example.com/v")

    bundle = Path(manifest["bundle_dir"])
    assert bundle.parent == tmp_path.resolve()
    assert bundle.name.startswith("watch-")
    assert json.loads((bundle / "manifest.json").read_text()) == manifest
    assert manifest["video"]["id"] == "abc123"
    assert manifest["media_file"] == "Author - Title.mp4"
    assert manifest["source_url"] == "https://example.com"


@patch("media_downloader.media_downloader.ffmpeg_available", return_value=False)
def test_watch_downloads_into_the_bundle_then_restores(_available, downloader, tmp_path):
    """Watching twice must not nest one bundle inside the last one."""
    state = _stub_download(downloader)
    first = downloader.watch("https://example.com/v")

    assert state["directory"] == first["bundle_dir"], "download ran inside the bundle"
    assert downloader.download_directory == str(tmp_path.resolve()), "restored after"

    second = downloader.watch("https://example.com/v")
    assert second["bundle_dir"] == first["bundle_dir"]
    assert Path(second["bundle_dir"]).parent == tmp_path.resolve()


@patch("media_downloader.media_downloader.ffmpeg_available", return_value=False)
def test_watch_requests_captions_and_metadata(_available, downloader):
    state = _stub_download(downloader)
    downloader.watch("https://example.com/v")

    opts = state["extra_opts"]
    assert opts is not None
    assert opts["writesubtitles"] is True
    assert opts["writeautomaticsub"] is True
    assert opts["writeinfojson"] is True
    assert opts["subtitlesformat"] == "vtt"
    # A wildcard here asks a site for every translated track and earns a 429.
    assert all("*" not in lang for lang in opts["subtitleslangs"])


@patch("media_downloader.media_downloader.ffmpeg_available", return_value=False)
def test_watch_is_partial_when_frames_are_unavailable(_available, downloader):
    _stub_download(downloader)
    manifest = downloader.watch("https://example.com/v")
    assert manifest["status"] == "partial"
    assert manifest["captions"]["status"] == "present"
    assert manifest["frames"]["status"] == "unavailable"


@patch("media_downloader.media_downloader.ffmpeg_available", return_value=False)
def test_watch_bridges_to_audio_transcriber_without_captions(_available, downloader):
    """No captions must name the fallback rather than silently transcribe."""
    _stub_download(downloader, captions="")
    manifest = downloader.watch("https://example.com/v")

    captions = manifest["captions"]
    assert manifest["status"] == "partial"
    assert captions["status"] == "missing"
    fallback = captions["fallback"]
    assert fallback["skill"] == "audio-transcriber-transcription"
    assert fallback["tool"] == "transcribe_audio"
    # The named file has to exist, or the handoff cannot be acted on.
    assert (Path(manifest["bundle_dir"]) / fallback["arguments"]["audio_file"]).exists()
    assert any("audio-transcriber" in w for w in manifest["warnings"])


@patch("media_downloader.media_downloader.extract_frames")
@patch("media_downloader.media_downloader.detect_scene_changes")
@patch("media_downloader.media_downloader.probe_duration", return_value=60.0)
@patch("media_downloader.media_downloader.ffmpeg_available", return_value=True)
def test_watch_succeeds_with_captions_and_frames(
    _available, _duration, mock_detect, mock_extract, downloader
):
    _stub_download(downloader)
    mock_detect.return_value = _candidates(20)
    mock_extract.return_value = [
        {
            "file": "frames/frame_0001_t00002.000.jpg",
            "timestamp_s": 2.0,
            "scene_score": 0.9,
        }
    ]
    manifest = downloader.watch("https://example.com/v", max_frames=1)

    assert manifest["status"] == "success"
    assert manifest["frames"]["mode"] == "scene"
    assert manifest["frames"]["count"] == 1
    assert manifest["warnings"] == []


@patch("media_downloader.media_downloader.ffmpeg_available", return_value=False)
def test_watch_carries_the_kg_asset_when_one_was_ingested(_available, downloader):
    _stub_download(downloader)
    downloader.last_kg_asset = {"asset_id": "a1", "digest": "d1"}
    manifest = downloader.watch("https://example.com/v")
    assert manifest["kg_asset"] == {"asset_id": "a1", "digest": "d1"}


def test_watch_reports_a_failed_download(downloader):
    _stub_download(downloader, fail=True)
    manifest = downloader.watch("https://example.com/v")

    assert manifest["status"] == "error"
    assert manifest["media_file"] is None
    assert manifest["captions"]["status"] == "missing"
    assert (
        json.loads((Path(manifest["bundle_dir"]) / "manifest.json").read_text())
        == manifest
    )


@patch("media_downloader.media_downloader.ffmpeg_available", return_value=False)
def test_watch_gives_a_different_bundle_to_a_different_url(_available, downloader):
    _stub_download(downloader)
    first = downloader.watch("https://example.com/v")
    other = downloader.watch("https://example.com/w")
    assert other["bundle_dir"] != first["bundle_dir"]


def test_watch_rejects_a_bundle_outside_the_output_root(downloader, tmp_path):
    """Path containment is the boundary every written file has to cross."""
    downloader.output_root = (tmp_path / "elsewhere").resolve()
    with pytest.raises(MediaSecurityError):
        downloader.watch("https://example.com/v")


def test_watch_validates_the_url_before_writing_anything(tmp_path):
    instance = MediaDownloader(
        links=[],
        download_directory=str(tmp_path),
        output_root=str(tmp_path),
        ingest_to_kg=False,
    )
    with patch(
        "media_downloader.media_downloader.validate_media_url",
        side_effect=MediaSecurityError("nope"),
    ):
        with pytest.raises(MediaSecurityError):
            instance.watch("http://10.0.0.1/x")
    assert list(tmp_path.iterdir()) == []


# download_video extra_opts seam
# --------------------------------------------------------------------------- #
def test_download_video_merges_extra_opts(tmp_path):
    """extra_opts is the seam the watch pipeline rides on."""
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


# --------------------------------------------------------------------------- #
# Salvaging a partial download
# --------------------------------------------------------------------------- #
def _stub_captions_only(downloader, captions=ROLLUP_VTT):
    """Captions and metadata land, the media download refuses. Real sites do this."""

    def _download(link, extra_opts=None):
        bundle = Path(downloader.download_directory)
        (bundle / "Author - Title.info.json").write_text(
            json.dumps({"id": "abc123", "title": "Title", "uploader": "Author"})
        )
        if captions:
            (bundle / "Author - Title.en.vtt").write_text(captions)
        return None

    downloader.download_video = _download


def test_watch_keeps_captions_when_only_the_media_fails(downloader):
    """A 403 on the video must not throw away captions that already landed."""
    _stub_captions_only(downloader)
    manifest = downloader.watch("https://example.com/v")

    assert manifest["status"] == "partial", "captions arrived; this is not a failure"
    assert manifest["captions"]["status"] == "present"
    assert manifest["captions"]["line_count"] == 4
    assert manifest["video"]["id"] == "abc123", "metadata sidecar still read"
    assert manifest["media_file"] is None
    assert manifest["frames"]["status"] == "unavailable"
    assert any("media itself could not be downloaded" in w for w in manifest["warnings"])
    # With no media file there is nothing for the transcriber to work on.
    assert "fallback" not in manifest["captions"]


def test_watch_is_an_error_only_when_nothing_arrived(downloader):
    _stub_captions_only(downloader, captions="")
    manifest = downloader.watch("https://example.com/v")

    assert manifest["status"] == "error"
    assert manifest["captions"]["status"] == "missing"
    assert any("no way to produce one" in w for w in manifest["warnings"])


# --------------------------------------------------------------------------- #
# Caption language selection
# --------------------------------------------------------------------------- #
def test_collect_captions_prefers_the_requested_language_over_size(tmp_path):
    """English by default, even when another track is bigger."""
    (tmp_path / "clip.en.vtt").write_text(ROLLUP_VTT, encoding="utf-8")
    (tmp_path / "clip.de.vtt").write_text(
        ROLLUP_VTT + "\n01:00:00.000 --> 01:00:02.000\nmehr text\n", encoding="utf-8"
    )
    assert (tmp_path / "clip.de.vtt").stat().st_size > (
        tmp_path / "clip.en.vtt"
    ).stat().st_size

    assert collect_captions(tmp_path, {})["language"] == "en"
    assert collect_captions(tmp_path, {}, ("de", "en"))["language"] == "de"


def test_collect_captions_falls_back_to_an_unrequested_language(tmp_path):
    (tmp_path / "clip.fr.vtt").write_text(ROLLUP_VTT, encoding="utf-8")
    captions = collect_captions(tmp_path, {})
    assert captions["status"] == "present"
    assert captions["language"] == "fr"


# --------------------------------------------------------------------------- #
# Skill authoring
# --------------------------------------------------------------------------- #
def _manifest(video_id="v1", title="First", lines=10, frames="present", count=4):
    return {
        "status": "success",
        "video": {
            "id": video_id,
            "title": title,
            "uploader": "Someone",
            "upload_date": "20260101",
            "webpage_url": f"https://example.com/{video_id}",
        },
        "captions": {"status": "present", "source": "manual", "line_count": lines},
        "frames": {"status": frames, "count": count},
    }


def _frontmatter(skill_dir):
    text = (Path(skill_dir) / "SKILL.md").read_text()
    return yaml.safe_load(text.split("---")[1])


def test_build_skill_creates_a_valid_skill(tmp_path):
    result = build_skill(
        tmp_path,
        name="My Test Skill",
        description="Does a thing. Do NOT use for other things.",
        body="# My Test Skill\n\nWhat it teaches.\n",
        manifest=_manifest(),
    )
    assert result["status"] == "created"
    assert result["skill"] == "my-test-skill", "name is slugified into the directory"

    frontmatter = _frontmatter(result["path"])
    assert frontmatter["name"] == "my-test-skill", "must equal the directory name"
    assert frontmatter["skill_type"] == "skill"
    assert frontmatter["metadata"]["version"] == "0.1.0"
    assert [s["video_id"] for s in frontmatter["metadata"]["sources"]] == ["v1"]

    text = (Path(result["path"]) / "SKILL.md").read_text()
    assert "## Sources" in text
    assert "https://example.com/v1" in text
    assert (Path(result["path"]) / "WORKFLOW.md").is_file()


def test_build_skill_records_what_evidence_was_actually_obtained(tmp_path):
    """A caption-only skill has to stay auditable as caption-only."""
    result = build_skill(
        tmp_path,
        name="thin",
        description="d",
        body="# Thin\n",
        manifest=_manifest(frames="unavailable", count=0),
    )
    text = (Path(result["path"]) / "SKILL.md").read_text()
    assert "no key frames" in text
    assert "10 transcript lines (manual)" in text


def test_build_skill_appends_a_second_video(tmp_path):
    build_skill(
        tmp_path, name="s", description="d", body="# S\n\nfirst\n", manifest=_manifest()
    )
    result = build_skill(
        tmp_path,
        name="s",
        body="## Update\n\nsecond\n",
        manifest=_manifest("v2", "Second"),
        mode="append",
    )
    assert result["status"] == "appended"
    assert result["version"] == "0.2.0", "a new video is a minor bump"
    assert result["source_count"] == 2

    text = (Path(result["path"]) / "SKILL.md").read_text()
    assert "first" in text and "second" in text, "earlier content is kept"
    assert text.count("## Sources") == 1, "the sources section is regenerated, not doubled"
    assert "https://example.com/v2" in text


def test_build_skill_refuses_to_append_the_same_video_twice(tmp_path):
    build_skill(
        tmp_path, name="s", description="d", body="# S\n", manifest=_manifest()
    )
    result = build_skill(
        tmp_path, name="s", body="## Again\n", manifest=_manifest(), mode="append"
    )
    assert result["status"] == "skipped"
    assert "already a source" in result["reason"]
    assert "Again" not in (Path(result["path"]) / "SKILL.md").read_text()


def test_build_skill_replace_rewrites_the_body_and_keeps_sources(tmp_path):
    build_skill(
        tmp_path, name="s", description="d", body="# S\n\nold\n", manifest=_manifest()
    )
    build_skill(
        tmp_path,
        name="s",
        body="## More\n",
        manifest=_manifest("v2", "Second"),
        mode="append",
    )
    result = build_skill(
        tmp_path,
        name="s",
        body="# S\n\nrewritten\n",
        manifest=_manifest("v2", "Second"),
        mode="replace",
    )
    assert result["status"] == "replaced"
    assert result["source_count"] == 2, "replace does not drop provenance"

    text = (Path(result["path"]) / "SKILL.md").read_text()
    assert "rewritten" in text
    assert "old" not in text and "## More" not in text
    assert "https://example.com/v1" in text and "https://example.com/v2" in text


def test_build_skill_rejects_bad_input(tmp_path):
    with pytest.raises(ValueError, match="mode"):
        build_skill(tmp_path, name="s", body="b", manifest=_manifest(), mode="merge")
    with pytest.raises(ValueError, match="description"):
        build_skill(tmp_path, name="s", body="b", manifest=_manifest())
    with pytest.raises(ValueError, match="no skill"):
        build_skill(
            tmp_path, name="absent", body="b", manifest=_manifest(), mode="append"
        )
    with pytest.raises(ValueError, match="letter or digit"):
        build_skill(tmp_path, name="!!!", description="d", body="b", manifest=_manifest())

    build_skill(tmp_path, name="s", description="d", body="b", manifest=_manifest())
    with pytest.raises(ValueError, match="already exists"):
        build_skill(tmp_path, name="s", description="d", body="b", manifest=_manifest())


def test_find_watch_skills_reports_what_each_skill_already_covers(tmp_path):
    assert find_watch_skills(tmp_path) == []
    assert find_watch_skills(tmp_path / "absent") == []

    build_skill(tmp_path, name="a", description="d", body="# A\n", manifest=_manifest())
    build_skill(
        tmp_path, name="b", description="d", body="# B\n", manifest=_manifest("v9")
    )
    # A hand-written skill with no video provenance is not a watch skill.
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "SKILL.md").write_text("---\nname: plain\ndescription: d\n---\n# Plain\n")

    found = find_watch_skills(tmp_path)
    assert {s["name"] for s in found} == {"a", "b"}
    assert next(s for s in found if s["name"] == "b")["video_ids"] == ["v9"]


def test_skill_sources_tolerates_junk(tmp_path):
    assert skill_sources(tmp_path / "nothing") == []
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "SKILL.md").write_text("no frontmatter here")
    assert skill_sources(broken) == []
