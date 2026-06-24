"""Tests for MCP server tool handlers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from knowledge_distiller.mcp_server import (
    _handle_configure,
    _handle_get_result,
    _handle_get_status,
    _handle_list_jobs,
    _handle_transcribe_file,
    _jobs,
    _resolve_local_media_path,
    _validate_url,
)
from knowledge_distiller.models import ArticleSummary, ProcessingStatus


@pytest.fixture(autouse=True)
def clear_jobs():
    _jobs.clear()
    yield
    _jobs.clear()


def _make_job(job_id: str, status: str = "queued", **kwargs) -> ProcessingStatus:
    job = ProcessingStatus(job_id=job_id, status=status, url="https://test.com", **kwargs)
    _jobs[job_id] = job
    return job


# ─── get_status ─────────────────────────────────────────────────────────────

def test_get_status_not_found():
    result = _handle_get_status({"job_id": "nonexistent"})
    assert "not found" in result[0].text.lower() or "error" in result[0].text.lower()


def test_get_status_queued():
    _make_job("abc", status="queued", progress=0.0)
    result = _handle_get_status({"job_id": "abc"})
    import json
    data = json.loads(result[0].text)
    assert data["status"] == "queued"
    assert data["progress"] == 0.0


def test_get_status_failed():
    _make_job("err", status="failed", error="Something went wrong")
    result = _handle_get_status({"job_id": "err"})
    import json
    data = json.loads(result[0].text)
    assert data["status"] == "failed"
    assert "error" in data


# ─── get_result ──────────────────────────────────────────────────────────────

def test_get_result_not_completed():
    _make_job("pending", status="transcribing")
    result = _handle_get_result({"job_id": "pending", "format": "full"})
    import json
    data = json.loads(result[0].text)
    assert data["status"] == "transcribing"


def test_get_result_full():
    job = _make_job("done", status="completed")
    job.result = ArticleSummary(
        one_sentence="精華摘要",
        key_points=["要點一", "要點二"],
        full_transcript="完整轉錄",
        source_url="https://youtube.com/test",
    )

    result = _handle_get_result({"job_id": "done", "format": "full"})
    import json
    data = json.loads(result[0].text)
    assert data["one_sentence"] == "精華摘要"
    assert "key_points" in data
    assert "full_transcript" in data


def test_get_result_summary_only():
    job = _make_job("done2", status="completed")
    job.result = ArticleSummary(
        one_sentence="精華",
        key_points=["要點"],
        full_transcript="Long transcript...",
        source_url="https://test.com",
    )

    result = _handle_get_result({"job_id": "done2", "format": "summary"})
    import json
    data = json.loads(result[0].text)
    assert "one_sentence" in data
    assert "full_transcript" not in data


# ─── list_jobs ───────────────────────────────────────────────────────────────

def test_list_jobs_empty():
    result = _handle_list_jobs()
    import json
    data = json.loads(result[0].text)
    assert data == []


def test_list_jobs_with_entries():
    _make_job("j1", status="completed")
    _make_job("j2", status="failed")
    result = _handle_list_jobs()
    import json
    data = json.loads(result[0].text)
    assert len(data) == 2
    ids = {j["job_id"] for j in data}
    assert ids == {"j1", "j2"}


# ─── _validate_url ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://yt.be/dQw4w9WgXcQ",
    "https://www.bilibili.com/video/BV1xx411c7XE",
    "https://b23.tv/abc123",
    "https://www.facebook.com/videos/123456789",
    "https://www.facebook.com/watch?v=123456789",
    "https://m.facebook.com/watch?v=123456789",
    "https://fb.watch/abc123def/",
])
def test_validate_url_allowed(url):
    _validate_url(url)  # Should not raise


@pytest.mark.parametrize("url", [
    "https://twitter.com/user/status/123",
    "https://tiktok.com/@user/video/123",
    "https://evil.com/hack",
    "ftp://youtube.com/video",
    "file:///etc/passwd",
])
def test_validate_url_rejected(url):
    with pytest.raises(ValueError):
        _validate_url(url)


# ─── transcribe_file ─────────────────────────────────────────────────────────

def test_resolve_local_media_path_accepts_path(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake")

    assert _resolve_local_media_path(str(media)) == media.resolve()


def test_resolve_local_media_path_accepts_file_uri(tmp_path):
    media = tmp_path / "clip with space.mp4"
    media.write_bytes(b"fake")

    assert _resolve_local_media_path(media.as_uri()) == media.resolve()


def test_resolve_local_media_path_rejects_unsupported_extension(tmp_path):
    media = tmp_path / "notes.txt"
    media.write_text("not media")

    with pytest.raises(ValueError, match="Unsupported local media extension"):
        _resolve_local_media_path(str(media))


@pytest.mark.asyncio
@patch("knowledge_distiller.mcp_server._extract_local_audio")
@patch("knowledge_distiller.mcp_server.transcriber.transcribe")
@patch("knowledge_distiller.mcp_server.config")
async def test_handle_transcribe_file(mock_config, mock_transcribe, mock_extract_audio, tmp_path):
    media = tmp_path / "lecture.mp4"
    media.write_bytes(b"fake video")
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake audio")

    mock_config.get.side_effect = lambda key, default=None: {
        "language": None,
        "transcriber": "qwen3-asr",
    }.get(key, default)
    mock_extract_audio.return_value = (audio, tmp_path)
    mock_transcribe.return_value = "本地影片轉錄"

    result = await _handle_transcribe_file(
        {"path": str(media), "style": "bullets", "language": "zh"}
    )
    data = json.loads(result[0].text)

    assert data["status"] == "ready"
    assert data["title"] == "lecture"
    assert data["path"] == str(media.resolve())
    assert data["transcript"] == "本地影片轉錄"
    assert data["transcript_source"] == "qwen3-asr"
    assert data["style"] == "bullets"


# ─── configure ───────────────────────────────────────────────────────────────

@patch("knowledge_distiller.mcp_server.config")
def test_configure_sets_values(mock_config):
    mock_config.get.return_value = "google"
    mock_config.save_api_key = MagicMock()
    mock_config.set_value = MagicMock()

    result = _handle_configure({"provider": "openai", "model": "gpt-4o"})
    import json
    data = json.loads(result[0].text)
    assert data["ok"] is True

    mock_config.set_value.assert_any_call("provider", "openai")
    mock_config.set_value.assert_any_call("model", "gpt-4o")
