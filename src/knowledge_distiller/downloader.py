"""yt-dlp wrapper for downloading audio from YouTube, Bilibili, and Facebook."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from .models import VideoMetadata


def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if any(x in host for x in ("youtube.com", "youtu.be", "yt.be")):
        return "youtube"
    if "bilibili.com" in host or "b23.tv" in host:
        return "bilibili"
    if "facebook.com" in host or "fb.watch" in host:
        return "facebook"
    return "unknown"


def _ydl_opts_base(quiet: bool = True) -> dict:
    return {
        "quiet": quiet,
        "no_warnings": quiet,
        "extract_flat": False,
    }


def fetch_metadata(url: str) -> VideoMetadata:
    """Fetch video metadata without downloading."""
    try:
        import yt_dlp
    except ImportError as e:
        raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp") from e

    platform = detect_platform(url)
    opts = {**_ydl_opts_base(), "skip_download": True}

    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as e:
            raise ValueError(f"Cannot fetch metadata: {e}") from e

    subtitle_langs: list[str] = []
    has_subtitles = False

    raw_subs = info.get("subtitles", {})
    raw_auto = info.get("automatic_captions", {})

    if raw_subs:
        has_subtitles = True
        subtitle_langs = list(raw_subs.keys())
    elif raw_auto:
        has_subtitles = True
        subtitle_langs = [f"{lang} (auto)" for lang in raw_auto.keys()]

    return VideoMetadata(
        url=url,
        platform=platform,  # type: ignore[arg-type]
        title=info.get("title"),
        duration=info.get("duration"),
        has_subtitles=has_subtitles,
        subtitle_languages=subtitle_langs,
        thumbnail_url=info.get("thumbnail"),
        uploader=info.get("uploader"),
        view_count=info.get("view_count"),
    )


def download_audio(
    url: str,
    output_dir: Path | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> Path:
    """Download best audio track, return path to downloaded file."""
    try:
        import yt_dlp
    except ImportError as e:
        raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp") from e

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="kd_audio_"))
    output_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(output_dir / "%(id)s.%(ext)s")
    downloaded_path: list[Path] = []

    class ProgressHook:
        def __call__(self, d: dict) -> None:
            if d["status"] == "finished":
                downloaded_path.append(Path(d["filename"]))
            elif d["status"] == "downloading" and progress_callback:
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    progress_callback(downloaded / total)

    opts = {
        **_ydl_opts_base(),
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "progress_hooks": [ProgressHook()],
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            raise ValueError(f"Download failed: {e}") from e

    # yt-dlp changes extension after postprocessing
    if downloaded_path:
        # The hook fires before postprocessing; look for mp3
        base = downloaded_path[0].with_suffix(".mp3")
        if base.exists():
            return base
        if downloaded_path[0].exists():
            return downloaded_path[0]

    # Fallback: find newest file in output_dir
    files = sorted(output_dir.iterdir(), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No audio file found after download in {output_dir}")
    return files[-1]
