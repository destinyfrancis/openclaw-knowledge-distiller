"""Tests for MCP server tool handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_distiller.mcp_server import (
    _handle_configure,
    _handle_get_result,
    _handle_get_status,
    _handle_list_jobs,
    _jobs,
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
