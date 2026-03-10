"""Extract subtitles from YouTube/Bilibili/Facebook videos, preferring manual over auto-generated."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path


def _strip_timestamps(text: str) -> str:
    """Remove SRT/VTT/JSON timestamps and return plain text."""
    # Remove VTT header
    text = re.sub(r"WEBVTT.*?\n\n", "", text, flags=re.DOTALL)
    # Remove SRT sequence numbers and timestamps
    text = re.sub(r"^\d+\s*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}.*\n", "", text)
    # Remove VTT timestamps
    text = re.sub(r"\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}\.\d{3}.*\n", "", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove positioning/alignment info (e.g., {\\an8})
    text = re.sub(r"\{\\[^}]+\}", "", text)
    # Collapse blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _pick_language(available: list[str], preferred: str | None) -> str | None:
    """Choose best subtitle language from available options."""
    if not available:
        return None

    # Strip " (auto)" markers for comparison
    clean = {lang.replace(" (auto)", ""): lang for lang in available}

    if preferred and preferred in clean:
        return clean[preferred]
    if preferred:
        # Try prefix match (e.g. "zh" matches "zh-Hans")
        for key, val in clean.items():
            if key.startswith(preferred):
                return val

    # Prefer non-auto subtitles
    manual = [lang for lang in available if "(auto)" not in lang]
    if manual:
        return manual[0]

    return available[0]


def extract_subtitles(url: str, language: str | None = None) -> str | None:
    """
    Extract subtitles for a video URL.
    Returns plain text or None if no subtitles available.
    Priority: manual > auto-generated.
    """
    try:
        import yt_dlp
    except ImportError as e:
        raise RuntimeError("yt-dlp not installed") from e

    with tempfile.TemporaryDirectory(prefix="kd_subs_") as _tmp:
        tmp_dir = Path(_tmp)

        # First: probe available subtitles
        probe_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception:
                return None

        raw_manual = info.get("subtitles", {})
        raw_auto = info.get("automatic_captions", {})

        # Gather all available languages with source tag
        available_manual = list(raw_manual.keys())
        available_auto = [f"{lang} (auto)" for lang in raw_auto.keys()]
        all_available = available_manual + available_auto

        if not all_available:
            return None

        chosen = _pick_language(all_available, language)
        if not chosen:
            return None

        is_auto = "(auto)" in chosen
        lang_code = chosen.replace(" (auto)", "")

        # Download chosen subtitle
        sub_opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writesubtitles": not is_auto,
            "writeautomaticsub": is_auto,
            "subtitleslangs": [lang_code],
            "subtitlesformat": "vtt",
            "outtmpl": str(tmp_dir / "subtitle.%(ext)s"),
        }

        with yt_dlp.YoutubeDL(sub_opts) as ydl:
            try:
                ydl.download([url])
            except Exception:
                return None

        # Find downloaded subtitle file and read before temp dir is deleted
        sub_files = list(tmp_dir.rglob("*.vtt")) + list(tmp_dir.rglob("*.srt"))
        if not sub_files:
            return None

        raw = sub_files[0].read_text(encoding="utf-8", errors="replace")

    return _strip_timestamps(raw) or None
