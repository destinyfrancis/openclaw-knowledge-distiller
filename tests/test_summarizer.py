"""Tests for summarizer module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from knowledge_distiller.summarizer import (
    _extract_json,
    _split_into_chunks,
    generate_summary,
    CHUNK_THRESHOLD,
)
from knowledge_distiller.models import ArticleSummary


# ─── _split_into_chunks ─────────────────────────────────────────────────────

def test_split_short_text_no_split():
    text = "Hello world"
    chunks = _split_into_chunks(text, max_size=100)
    assert chunks == ["Hello world"]


def test_split_at_paragraph_boundary():
    para1 = "A" * 4000
    para2 = "B" * 4000
    text = para1 + "\n\n" + para2
    chunks = _split_into_chunks(text, max_size=6000)
    assert len(chunks) == 2
    assert chunks[0] == para1
    assert chunks[1] == para2


def test_split_at_sentence_boundary():
    text = "一句話。" * 2000  # well over 6000 chars
    chunks = _split_into_chunks(text, max_size=6000)
    for chunk in chunks:
        assert len(chunk) <= 6000 + 10  # small overshoot allowed


def test_split_no_boundary_hard_cut():
    text = "A" * 10000
    chunks = _split_into_chunks(text, max_size=6000)
    assert all(len(c) <= 6000 for c in chunks)


# ─── _extract_json ───────────────────────────────────────────────────────────

def test_extract_json_clean():
    raw = '{"one_sentence": "Test", "key_points": ["a", "b"], "full_transcript": "..."}'
    data = _extract_json(raw)
    assert data["one_sentence"] == "Test"
    assert len(data["key_points"]) == 2


def test_extract_json_with_markdown_fence():
    raw = '```json\n{"one_sentence": "Test"}\n```'
    data = _extract_json(raw)
    assert data["one_sentence"] == "Test"


def test_extract_json_with_surrounding_text():
    raw = 'Here is the result:\n{"one_sentence": "Result", "key_points": []}\nEnd.'
    data = _extract_json(raw)
    assert data["one_sentence"] == "Result"


# ─── generate_summary ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_summary_short_text():
    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock(
        return_value='{"one_sentence": "精華", "key_points": ["要點A", "要點B"], "full_transcript": "整理後文字"}'
    )

    summary = await generate_summary(
        "Short transcript",
        mock_provider,
        source_url="https://youtube.com/test",
        video_title="Test Video",
    )

    assert isinstance(summary, ArticleSummary)
    assert summary.one_sentence == "精華"
    assert len(summary.key_points) == 2
    assert summary.source_url == "https://youtube.com/test"
    assert summary.video_title == "Test Video"
    mock_provider.complete.assert_called_once()


@pytest.mark.asyncio
async def test_generate_summary_long_text_chunks():
    long_text = "一句話。" * 3000  # ~12000 chars > CHUNK_THRESHOLD

    chunk_resp = '{"one_sentence": "段落精華", "key_points": ["點1"], "full_transcript": "段落內容"}'
    merge_resp = '{"one_sentence": "全部精華", "key_points": ["點1", "點2"], "full_transcript": "完整內容"}'

    call_count = 0

    async def mock_complete(system: str, user: str) -> str:
        nonlocal call_count
        call_count += 1
        if "合併" in system or "merge" in system.lower() or "第 1/" not in user:
            return merge_resp
        return chunk_resp

    mock_provider = MagicMock()
    mock_provider.complete = mock_complete

    summary = await generate_summary(long_text, mock_provider, source_url="https://test.com")

    # Should have called complete multiple times (chunks + merge)
    assert call_count > 1
    assert summary.one_sentence == "全部精華"
