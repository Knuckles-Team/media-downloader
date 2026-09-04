#!/usr/bin/env python3


import argparse
import hashlib
import html
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path
from urllib.parse import urlsplit

import yt_dlp

from media_downloader.security import (
    MediaSecurityError,
    contained_output_path,
    public_source_url,
    resolve_output_directory,
    safe_metadata_get,
    validate_media_url,
)

__version__ = "4.2.0"

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


class YtDlpLogger:
    def __init__(self, logger):
        self.logger = logger

    def debug(self, msg):
        self.logger.debug("yt-dlp diagnostic event")

    def warning(self, msg):
        self.logger.warning("yt-dlp warning event")

    def error(self, msg):
        self.logger.error("yt-dlp error event")


class SafeYoutubeDL(yt_dlp.YoutubeDL):
    """Revalidate every URL crossing yt-dlp's central request boundary."""

    def urlopen(self, req):
        request_url = req if isinstance(req, str) else getattr(req, "url", None)
        if not request_url:
            raise MediaSecurityError("Downloader request omitted its URL")
        validate_media_url(request_url)
        response = super().urlopen(req)
        final_url = getattr(response, "url", None)
        if final_url:
            validate_media_url(final_url)
        return response


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


class MediaDownloader:
    def __init__(
        self,
        links: list | None = None,
        download_directory: str | None = None,
        audio: bool = False,
        ingest_to_kg: bool = True,
        output_root: str | None = None,
    ):
        self.links = links if links is not None else []
        self.output_root, output_directory = resolve_output_directory(
            download_directory, output_root=output_root
        )
        self.download_directory = str(output_directory)
        self.audio = audio
        # Native KG ingestion is on by default; it auto-no-ops when no epistemic-graph
        # engine is reachable, so it costs nothing without KG infrastructure.
        self.ingest_to_kg = ingest_to_kg
        self.last_kg_asset: dict | None = None
        self.logger = logging.getLogger("MediaDownloader")
        self.progress_callback = None

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def open_file(self, file):
        youtube_urls = open(file)
        for url in youtube_urls:
            self.links.append(url)
        self.links = list(dict.fromkeys(self.links))

    def download_video(self, link, extra_opts=None):
        link = validate_media_url(link.strip())
        self.logger.debug("Downloading media from host %s", urlsplit(link).hostname)
        outtmpl = f"{self.download_directory}/%(uploader)s - %(title)s.%(ext)s"
        host = (urlsplit(link).hostname or "").lower()
        if host == "rumble.com" or host.endswith(".rumble.com"):
            self.logger.debug("Processing Rumble media URL")
            rumble_url = safe_metadata_get(link, timeout=10)
            for rumble_embedded_url in rumble_url.text.split(","):
                if "embedUrl" in rumble_embedded_url:
                    rumble_embedded_url = re.sub(
                        '"', "", re.sub('"embedUrl":', "", rumble_embedded_url)
                    )
                    link = validate_media_url(rumble_embedded_url.strip())
                    outtmpl = f"{self.download_directory}/%(title)s.%(ext)s"
                    self.logger.debug("Validated the embedded Rumble media URL")

        ydl_opts = {
            "format": "bestaudio/best" if self.audio else "best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self.progress_hook],
            "logger": YtDlpLogger(self.logger),
            "restrictfilenames": True,
            "windowsfilenames": True,
            "noplaylist": True,
        }
        if self.audio:
            ydl_opts["postprocessors"] = [
                {  # type: ignore
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }
            ]
        if extra_opts:
            ydl_opts.update(extra_opts)

        try:
            with SafeYoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                path = ydl.prepare_filename(info)
                path = str(contained_output_path(path, self.output_root))
                self._maybe_ingest(path, info, link)
                return path
        except Exception as e:
            self.logger.error("Media download failed (%s)", type(e).__name__)
            try:
                outtmpl = f"{self.download_directory}/%(id)s.%(ext)s"
                ydl_opts["outtmpl"] = outtmpl
                with SafeYoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=True)
                    path = ydl.prepare_filename(info)
                    path = str(contained_output_path(path, self.output_root))
                    self._maybe_ingest(path, info, link)
                    return path
            except Exception as e:
                self.logger.error("Media download retry failed (%s)", type(e).__name__)
                return None

    def _maybe_ingest(self, path, info, link):
        """Natively store a freshly downloaded file into the knowledge graph.

        Default-on and best-effort: no-ops when ``ingest_to_kg`` is off or no live
        epistemic-graph engine is reachable. Records the result on
        ``self.last_kg_asset`` (``{asset_id, digest, size_bytes, media_type}``).
        """
        if not self.ingest_to_kg or not path:
            return
        from media_downloader.kg_media import ingest_media_file

        self.last_kg_asset = ingest_media_file(
            path, info=info, source_url=public_source_url(link)
        )

    def _append_links(self, vids, limit):
        for x, vid in enumerate(vids):
            if limit < 0 or x < limit:
                self.links.append(vid)

    @staticmethod
    def _canonical_channel_video_links(page_content):
        data = str(page_content).split(" ")
        item = 'href="/watch?'
        return [line.replace('href="', "youtube.com") for line in data if item in line]

    @staticmethod
    def _alternate_channel_video_links(page_content):
        data = str(page_content).split(" ")
        item = "https://i.ytimg.com/vi/"
        vids = []
        for line in data:
            if item not in line:
                continue
            try:
                match = re.search("https://i.ytimg.com/vi/(.+?)/hqdefault.", line)
            except AttributeError:
                continue
            if match:
                vids.append(f"https://www.youtube.com/watch?v={match.group(1)}")
        return vids

    def _channel_video_url_candidates(self, channel, username):
        return (
            (
                f"https://www.youtube.com/user/{username}/videos",
                "a canonical YouTube channel URL",
                self._canonical_channel_video_links,
            ),
            (
                f"https://www.youtube.com/c/{channel}/videos",
                "the alternate canonical YouTube channel URL",
                self._alternate_channel_video_links,
            ),
        )

    def get_channel_videos(self, channel, limit=-1):
        self.logger.debug("Fetching videos for a channel (limit=%s)", limit)
        username = channel
        for _attempt in range(3):
            for url, description, extract_links in self._channel_video_url_candidates(
                channel, username
            ):
                self.logger.debug("Trying %s", description)
                page = safe_metadata_get(url, timeout=10).content
                vids = extract_links(page)
                if vids:
                    self.logger.debug(f"Found {len(vids)} videos")
                    self._append_links(vids, limit)
                    return
        self.logger.error("Could not find the requested channel")

    def progress_hook(self, d):
        if self.progress_callback and d["status"] == "downloading":
            if d.get("total_bytes") and d.get("downloaded_bytes"):
                progress = (d["downloaded_bytes"] / d["total_bytes"]) * 100
                self.progress_callback(progress=progress, total=100)
            elif d.get("downloaded_bytes"):
                self.progress_callback(progress=d["downloaded_bytes"])
        elif d["status"] == "finished":
            if self.progress_callback:
                self.progress_callback(progress=100, total=100)

    def download_all(self):
        self.logger.debug(f"Downloading {len(self.links)} links")
        if len(self.links) > 1_000:
            raise MediaSecurityError("Media link count limit exceeded")
        max_workers = max(
            1, min(int(os.environ.get("MEDIA_DOWNLOADER_MAX_WORKERS", "4")), 4)
        )
        worker_count = min(max_workers, max(1, len(self.links)))
        pool = Pool(processes=worker_count)
        try:
            results = pool.map(self.download_video, self.links)
            self.links = []
            for result in results:
                if result and os.path.exists(result):
                    return result
            return None
        finally:
            pool.close()
            pool.join()

    def watch(
        self,
        link,
        max_frames=DEFAULT_MAX_FRAMES,
        min_frames=DEFAULT_MIN_FRAMES,
        scene_threshold=DEFAULT_SCENE_THRESHOLD,
        subtitle_langs=DEFAULT_SUBTITLE_LANGS,
    ):
        """Download a video with its captions and extract scene-change key frames.

        Returns the bundle manifest: the media, the transcript, the key frames,
        and whatever could not be obtained. ``status`` is ``success`` only when
        both captions and frames are present, so a caller can surface a
        ``partial`` result before reasoning over an incomplete bundle. A degraded
        run never raises.
        """
        link = validate_media_url(link.strip())
        bundle = _bundle_directory(self.download_directory, self.output_root, link)

        # download_video builds its outtmpl from download_directory, so the
        # bundle has to be current for the call and restored afterwards -
        # watching twice on one instance must not nest bundles.
        previous_directory = self.download_directory
        self.download_directory = str(bundle)
        try:
            media_path = self.download_video(
                link,
                extra_opts={
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": list(subtitle_langs),
                    "subtitlesformat": "vtt",
                    "writeinfojson": True,
                },
            )
        finally:
            self.download_directory = previous_directory

        if not media_path or not os.path.exists(media_path):
            return _failed_manifest(link, bundle)

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
            Path(media_path),
            bundle,
            max_frames=max_frames,
            min_frames=min_frames,
            scene_threshold=scene_threshold,
            warnings=warnings,
        )

        manifest = {
            "status": _overall_status(captions, frames),
            "source_url": public_source_url(link),
            "bundle_dir": str(bundle),
            "video": _video_metadata(info),
            "media_file": media_relpath,
            "captions": captions,
            "frames": frames,
            "warnings": warnings,
        }
        if self.last_kg_asset:
            manifest["kg_asset"] = self.last_kg_asset
        return _write_manifest(bundle, manifest)


def media_downloader():
    parser = argparse.ArgumentParser(
        add_help=False, description="Download media from various sources."
    )
    parser.add_argument(
        "-a", "--audio", action="store_true", help="Download audio only"
    )
    parser.add_argument("-c", "--channel", help="Download videos from a channel URL")
    parser.add_argument("-d", "--directory", help="Specify download directory")
    parser.add_argument("-f", "--file", help="Read URLs from a file")
    parser.add_argument(
        "-l", "--links", help="Comma-separated list of URLs to download"
    )
    parser.add_argument(
        "-w",
        "--watch",
        help="URL to watch: download it with captions and extract key frames",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=DEFAULT_MAX_FRAMES,
        help=f"Maximum key frames to extract when watching (default {DEFAULT_MAX_FRAMES})",
    )

    parser.add_argument("--help", action="store_true", help="Show usage")

    args = parser.parse_args()

    if hasattr(args, "help") and args.help:
        parser.print_help()
        sys.exit(0)

    logger = logging.getLogger("MediaDownloader")
    logger.setLevel(logging.DEBUG)

    logger.handlers.clear()
    # Diagnostics go to stderr so stdout carries only command output (the
    # --watch manifest is JSON and has to stay pipeable).
    handler = logging.StreamHandler(sys.stderr)

    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    video_downloader_instance = MediaDownloader(download_directory=args.directory)

    if args.audio:
        video_downloader_instance.audio = True
    if args.channel:
        video_downloader_instance.get_channel_videos(args.channel)
    if args.file:
        video_downloader_instance.open_file(args.file)
    if args.links:
        url_list = args.links.replace(" ", "").split(",")
        video_downloader_instance.links.extend(url_list)

    if args.watch:
        logger.info("Watching the requested media...")
        manifest = video_downloader_instance.watch(args.watch, max_frames=args.frames)
        print(json.dumps(manifest, indent=2))
        sys.exit(0 if manifest.get("status") != "error" else 1)

    logger.info("Kicking off downloads...")
    video_downloader_instance.download_all()


if __name__ == "__main__":
    media_downloader()
