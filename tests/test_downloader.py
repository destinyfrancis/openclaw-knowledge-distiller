"""Tests for downloader module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from knowledge_distiller.downloader import detect_platform, fetch_metadata
from knowledge_distiller.models import VideoMetadata


def test_detect_platform_youtube():
    assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"
    assert detect_platform("https://youtu.be/dQw4w9WgXcQ") == "youtube"


def test_detect_platform_bilibili():
    assert detect_platform("https://www.bilibili.com/video/BV1xx411c7mD") == "bilibili"


def test_detect_platform_unknown():
    assert detect_platform("https://vimeo.com/123456") == "unknown"


def _make_mock_ydl(info: dict) -> MagicMock:
    """Helper: build a mock YoutubeDL context manager."""
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = info
    return mock_ydl


def test_fetch_metadata_youtube(monkeypatch):
    mock_info = {
        "title": "Test Video",
        "duration": 300.0,
        "subtitles": {"zh": [{"ext": "vtt"}]},
        "automatic_captions": {},
        "thumbnail": "https://example.com/thumb.jpg",
        "uploader": "Test Channel",
        "view_count": 1000,
    }
    mock_yt_dlp = MagicMock()
    mock_yt_dlp.YoutubeDL.return_value = _make_mock_ydl(mock_info)
    monkeypatch.setitem(__import__("sys").modules, "yt_dlp", mock_yt_dlp)

    meta = fetch_metadata("https://youtube.com/watch?v=test")

    assert meta.title == "Test Video"
    assert meta.duration == 300.0
    assert meta.has_subtitles is True
    assert "zh" in meta.subtitle_languages
    assert meta.platform == "youtube"


def test_fetch_metadata_no_subtitles(monkeypatch):
    mock_info = {
        "title": "No Subs Video",
        "duration": 120.0,
        "subtitles": {},
        "automatic_captions": {},
        "thumbnail": None,
        "uploader": None,
        "view_count": None,
    }
    mock_yt_dlp = MagicMock()
    mock_yt_dlp.YoutubeDL.return_value = _make_mock_ydl(mock_info)
    monkeypatch.setitem(__import__("sys").modules, "yt_dlp", mock_yt_dlp)

    meta = fetch_metadata("https://youtube.com/watch?v=nosubs")

    assert meta.has_subtitles is False
    assert meta.subtitle_languages == []
