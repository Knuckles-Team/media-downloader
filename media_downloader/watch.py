#!/usr/bin/env python3
"""Turn a media URL into a bundle an agent can read: captions + key frames.

``watch_media`` downloads a video once, keeps its captions, extracts
scene-change key frames whose filenames carry their timestamp (so a frame can be
lined up against what was being said), and writes a ``manifest.json`` stating
exactly what was and was not obtained.

A degraded run never raises. Missing ffmpeg or missing captions yields
``status: "partial"`` plus a warning, so a caller can report the gap before
reasoning over an incomplete bundle.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from media_downloader.security import (
    contained_output_path,
    public_source_url,
    validate_media_url,
)

logger = logging.getLogger("MediaDownloader")

DEFAULT_MAX_FRAMES = 24
DEFAULT_MIN_FRAMES = 6
DEFAULT_SCENE_THRESHOLD = 0.3
# Deliberately NOT a wildcard such as "en.*": YouTube publishes an auto-translated
# track per target language (en-ar, en-zh, en-de ...), and a wildcard requests all
# ~32 of them, which earns an HTTP 429 partway through. "en-orig" picks up the
# original-audio track on multi-language uploads.
DEFAULT_SUBTITLE_LANGS = ("en", "en-orig")
FRAME_WIDTH = 1280
MANIFEST_NAME = "manifest.json"
TRANSCRIPT_NAME = "transcript.txt"
FRAMES_DIRNAME = "frames"

_DETECT_TIMEOUT = 900
_PROBE_TIMEOUT = 60
_FRAME_TIMEOUT = 120
_ROLLUP_WINDOW = 4

_CUE_RE = re.compile(
    r"^(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3})"
)
_TAG_RE = re.compile(r"<[^>]+>")
_PTS_RE = re.compile(r"pts_time:(\d+(?:\.\d+)?)")
_SCORE_RE = re.compile(r"lavfi\.scene_score=(\d+(?:\.\d+)?)")


# --------------------------------------------------------------------------- #
# Captions
# --------------------------------------------------------------------------- #
def _timestamp_to_seconds(stamp: str) -> float:
    hours, minutes, seconds = stamp.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def _clean_caption_line(line: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub("", line))).strip()


def parse_vtt(text: str) -> list[dict]:
    """Parse WebVTT into de-duplicated ``{start, text}`` cues.

    Auto-generated captions roll up: each cue repeats the tail of the previous
    one so the caption box scrolls. Emitting them verbatim triples the
    transcript, so a line already seen in the last few cues is dropped.
    """
    cues: list[dict] = []
    recent: list[str] = []
    state: dict = {"start": None, "buffer": []}

    def flush() -> None:
        start = state["start"]
        buffer = state["buffer"]
        state["start"], state["buffer"] = None, []
        if start is None:
            return
        for raw in buffer:
            line = _clean_caption_line(raw)
            if not line or line in recent:
                continue
            cues.append({"start": start, "text": line})
            recent.append(line)
            del recent[:-_ROLLUP_WINDOW]

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        match = _CUE_RE.match(stripped)
        if match:
            flush()
            state["start"] = _timestamp_to_seconds(match.group(1))
        elif not stripped:
            flush()
        elif state["start"] is not None:
            state["buffer"].append(raw_line)
    flush()
    return cues


def write_transcript(cues: list[dict], destination: Path) -> int:
    """Write ``[HH:MM:SS] text`` lines; return how many were written."""
    lines = [f"[{_format_timestamp(c['start'])}] {c['text']}" for c in cues]
    body = "\n".join(lines)
    destination.write_text(f"{body}\n" if lines else "", encoding="utf-8")
    return len(lines)


def _caption_language(vtt: Path) -> str | None:
    parts = vtt.name.split(".")
    return parts[-2] if len(parts) >= 3 else None


def _caption_source(info: dict, language: str) -> str:
    if language in (info.get("subtitles") or {}):
        return "manual"
    if language in (info.get("automatic_captions") or {}):
        return "automatic"
    return "unknown"


def _empty_captions() -> dict:
    return {
        "status": "missing",
        "language": None,
        "source": None,
        "vtt_file": None,
        "transcript_file": None,
        "line_count": 0,
    }


def collect_captions(bundle: Path, info: dict) -> dict:
    """Pick the fullest caption track in ``bundle`` and render a transcript."""
    vtt_files = sorted(bundle.glob("*.vtt"))
    if not vtt_files:
        return _empty_captions()
    # Several language variants can land at once; the largest carries the most
    # cues, which is the one worth transcribing.
    vtt = max(vtt_files, key=lambda p: (p.stat().st_size, p.name))
    cues = parse_vtt(vtt.read_text(encoding="utf-8", errors="replace"))
    if not cues:
        return _empty_captions()
    language = _caption_language(vtt)
    line_count = write_transcript(cues, bundle / TRANSCRIPT_NAME)
    return {
        "status": "present",
        "language": language,
        "source": _caption_source(info, language or ""),
        "vtt_file": vtt.name,
        "transcript_file": TRANSCRIPT_NAME,
        "line_count": line_count,
    }


# --------------------------------------------------------------------------- #
# Key frames
# --------------------------------------------------------------------------- #
def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, capture_output=True, text=True, timeout=timeout, check=False
    )


def ffmpeg_available() -> bool:
    """Both binaries are needed: ffprobe for duration, ffmpeg for frames."""
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def probe_duration(media: Path) -> float | None:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(media),
        ],
        _PROBE_TIMEOUT,
    )
    try:
        return float(result.stdout.strip())
    except (AttributeError, TypeError, ValueError):
        return None


def detect_scene_changes(media: Path, threshold: float) -> list[dict]:
    """Return ``{timestamp_s, scene_score}`` candidates in chronological order."""
    result = _run(
        [
            "ffmpeg",
            "-nostdin",
            "-i",
            str(media),
            "-vf",
            f"select='gt(scene,{threshold})',metadata=print",
            "-an",
            "-f",
            "null",
            "-",
        ],
        _DETECT_TIMEOUT,
    )
    candidates: list[dict] = []
    pending: float | None = None
    for line in (result.stderr or "").splitlines():
        pts = _PTS_RE.search(line)
        if pts:
            pending = float(pts.group(1))
            continue
        score = _SCORE_RE.search(line)
        if score and pending is not None:
            candidates.append(
                {"timestamp_s": pending, "scene_score": float(score.group(1))}
            )
            pending = None
    return candidates


def select_timestamps(
    candidates: list[dict],
    duration: float | None,
    *,
    max_frames: int,
    min_frames: int,
) -> tuple[list[dict], str]:
    """Cap scene candidates to the highest-scoring ``max_frames``, chronologically.

    Keeping the top scores rather than the first ``max_frames`` matters: a long
    tutorial's most informative screens are spread throughout, and truncating the
    detection order would return nothing but the intro. Videos with too few
    detected changes (a static talking head, a short clip) fall back to evenly
    spaced timestamps so a bundle always carries some visual evidence.
    """
    if len(candidates) >= min_frames:
        ranked = sorted(candidates, key=lambda c: c["scene_score"], reverse=True)
        chosen = sorted(ranked[:max_frames], key=lambda c: c["timestamp_s"])
        return chosen, "scene"
    if not duration or duration <= 0:
        return list(candidates), "scene"
    count = max(1, min(min_frames, max_frames))
    step = duration / (count + 1)
    spaced = [
        {"timestamp_s": round(step * (index + 1), 3), "scene_score": None}
        for index in range(count)
    ]
    return spaced, "interval"


def extract_frames(media: Path, timestamps: list[dict], frames_dir: Path) -> list[dict]:
    """Extract one JPEG per timestamp, naming each file after its position."""
    if not timestamps:
        return []
    frames_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[dict] = []
    for index, candidate in enumerate(timestamps, start=1):
        seconds = float(candidate["timestamp_s"])
        name = f"frame_{index:04d}_t{seconds:09.3f}.jpg"
        target = frames_dir / name
        result = _run(
            [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-ss",
                f"{seconds:.3f}",
                "-i",
                str(media),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-vf",
                f"scale='min({FRAME_WIDTH},iw)':-2",
                str(target),
            ],
            _FRAME_TIMEOUT,
        )
        if result.returncode != 0 or not target.exists():
            logger.debug("Key frame skipped at %.3fs", seconds)
            continue
        extracted.append(
            {
                "file": f"{FRAMES_DIRNAME}/{name}",
                "timestamp_s": seconds,
                "scene_score": candidate.get("scene_score"),
            }
        )
    return extracted


def _unavailable_frames(mode: str | None, threshold: float) -> dict:
    return {
        "status": "unavailable",
        "mode": mode,
        "count": 0,
        "scene_threshold": threshold,
        "dir": None,
        "items": [],
    }


def build_frames(
    media: Path,
    bundle: Path,
    *,
    max_frames: int,
    min_frames: int,
    scene_threshold: float,
    warnings: list[str],
) -> dict:
    if not ffmpeg_available():
        warnings.append(
            "ffmpeg/ffprobe were not found on PATH, so no key frames were "
            "extracted - only the captions half of this video is available."
        )
        return _unavailable_frames(None, scene_threshold)

    duration = probe_duration(media)
    candidates = detect_scene_changes(media, scene_threshold)
    chosen, mode = select_timestamps(
        candidates, duration, max_frames=max_frames, min_frames=min_frames
    )
    items = extract_frames(media, chosen, bundle / FRAMES_DIRNAME)
    if not items:
        warnings.append("ffmpeg produced no key frames for this media.")
        return _unavailable_frames(mode, scene_threshold)
    if mode == "interval":
        warnings.append(
            "Too few scene changes were detected, so frames are evenly spaced "
            "rather than scene-aligned."
        )
    return {
        "status": "present",
        "mode": mode,
        "count": len(items),
        "scene_threshold": scene_threshold,
        "dir": FRAMES_DIRNAME,
        "items": items,
    }


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #
_INFO_KEYS = (
    "id",
    "title",
    "uploader",
    "channel",
    "duration",
    "webpage_url",
    "ext",
    "resolution",
    "fps",
    "upload_date",
)


def _read_info(bundle: Path) -> dict:
    for path in sorted(bundle.glob("*.info.json")):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.debug("Unreadable info sidecar in bundle")
    return {}


def _video_metadata(info: dict) -> dict:
    return {key: info.get(key) for key in _INFO_KEYS}


def _bundle_directory(download_directory: str, output_root: Path, url: str) -> Path:
    """A stable per-URL bundle directory, reused on a repeat run.

    Named from a URL digest rather than the video id because the id is only
    known after the download; the media file inside keeps its human-readable
    ``uploader - title`` name, so the bundle stays browsable.
    """
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    bundle = contained_output_path(
        str(Path(download_directory) / f"watch-{digest}"), output_root
    )
    bundle.mkdir(parents=True, exist_ok=True)
    return bundle


def _relative(path: str | None, bundle: Path) -> str | None:
    if not path:
        return None
    return os.path.relpath(path, bundle).replace(os.sep, "/")


def _add_caption_fallback(captions: dict, media_relpath: str | None) -> None:
    """Point a caption-less bundle at the audio-transcriber package.

    Deliberately a handoff rather than an in-process transcription: the caller
    is told the captions are absent and decides whether to spend an ASR pass,
    and anything produced that way is marked as inferred rather than quoted.
    """
    captions["fallback"] = {
        "skill": "audio-transcriber-transcription",
        "tool": "transcribe_audio",
        "arguments": {
            "audio_file": media_relpath,
            "export_formats": ["txt", "vtt"],
        },
        "reason": "no manual or automatic captions were published for this media",
    }


def _overall_status(captions: dict, frames: dict) -> str:
    complete = captions["status"] == "present" and frames["status"] == "present"
    return "success" if complete else "partial"


def _write_manifest(bundle: Path, manifest: dict) -> dict:
    (bundle / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=False), encoding="utf-8"
    )
    return manifest


def _failed_manifest(url: str, bundle: Path | None) -> dict:
    manifest = {
        "status": "error",
        "source_url": public_source_url(url),
        "message": "Download failed; no media, captions or frames were produced.",
        "bundle_dir": str(bundle) if bundle else None,
        "video": {},
        "media_file": None,
        "captions": _empty_captions(),
        "frames": _unavailable_frames(None, DEFAULT_SCENE_THRESHOLD),
        "warnings": ["The media could not be downloaded."],
    }
    if bundle is not None:
        return _write_manifest(bundle, manifest)
    return manifest


def watch_media(
    url: str,
    *,
    download_directory: str | None = None,
    output_root: str | None = None,
    max_frames: int = DEFAULT_MAX_FRAMES,
    min_frames: int = DEFAULT_MIN_FRAMES,
    scene_threshold: float = DEFAULT_SCENE_THRESHOLD,
    subtitle_langs: tuple[str, ...] = DEFAULT_SUBTITLE_LANGS,
    ingest_to_kg: bool = True,
) -> dict:
    """Download a video with its captions and extract scene-change key frames.

    Returns the manifest describing the bundle. ``status`` is ``success`` only
    when both captions and frames were obtained; a caller should surface a
    ``partial`` result before reasoning over the bundle.
    """
    from media_downloader.media_downloader import MediaDownloader

    url = validate_media_url(url.strip())
    downloader = MediaDownloader(
        links=[url],
        download_directory=download_directory,
        ingest_to_kg=ingest_to_kg,
        output_root=output_root,
    )
    bundle = _bundle_directory(
        downloader.download_directory, downloader.output_root, url
    )
    downloader.download_directory = str(bundle)

    media_path = downloader.download_video(
        url,
        extra_opts={
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": list(subtitle_langs),
            "subtitlesformat": "vtt",
            "writeinfojson": True,
        },
    )
    if not media_path or not os.path.exists(media_path):
        return _failed_manifest(url, bundle)

    media = Path(media_path)
    warnings: list[str] = []
    info = _read_info(bundle)
    captions = collect_captions(bundle, info)
    media_relpath = _relative(media_path, bundle)
    if captions["status"] == "missing":
        _add_caption_fallback(captions, media_relpath)
        warnings.append(
            "No captions were available for this media; the transcript is "
            "missing. Transcribe it with the audio-transcriber skill before "
            "relying on anything that was said."
        )

    frames = build_frames(
        media,
        bundle,
        max_frames=max_frames,
        min_frames=min_frames,
        scene_threshold=scene_threshold,
        warnings=warnings,
    )

    manifest = {
        "status": _overall_status(captions, frames),
        "source_url": public_source_url(url),
        "bundle_dir": str(bundle),
        "video": _video_metadata(info),
        "media_file": media_relpath,
        "captions": captions,
        "frames": frames,
        "warnings": warnings,
    }
    if downloader.last_kg_asset:
        manifest["kg_asset"] = downloader.last_kg_asset
    return _write_manifest(bundle, manifest)
