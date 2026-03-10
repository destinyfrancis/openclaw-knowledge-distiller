"""Multi-layer summarization: one-sentence + key points + cleaned transcript."""

from __future__ import annotations

import json
import re

from .models import ArticleSummary
from .providers import AIProvider

CHUNK_SIZE = 6000  # chars per chunk for long text
CHUNK_THRESHOLD = 8000  # chars above which we split

DEFAULT_SYSTEM_PROMPT = """\
你是一位專業的內容分析師。給你一段影片轉錄文字，請產生結構化摘要。

輸出必須為 JSON 格式，包含以下欄位：
{
  "one_sentence": "一句話精華（100字以內，概括核心訊息）",
  "key_points": ["要點 1", "要點 2", ...],  // 3-7 個最重要的 takeaways
  "full_transcript": "修正文法、加標點、分段落的完整整理版本"
}

請用與轉錄文字相同的語言輸出。只輸出 JSON，不要有其他文字。"""

MERGE_SYSTEM_PROMPT = """\
你是一位編輯助理。給你多段摘要 JSON，請合併成一份完整摘要。

輸出格式：
{
  "one_sentence": "整體一句話精華",
  "key_points": ["合併後要點..."],
  "full_transcript": "合併後完整轉錄"
}

只輸出 JSON，不要有其他文字。"""


def _split_into_chunks(text: str, max_size: int = CHUNK_SIZE) -> list[str]:
    """Split text at paragraph/sentence boundaries."""
    if len(text) <= max_size:
        return [text]

    chunks: list[str] = []
    remaining = text

    while len(remaining) > max_size:
        # Try paragraph boundary first
        idx = remaining.rfind("\n\n", 0, max_size)
        if idx == -1:
            # Try newline
            idx = remaining.rfind("\n", 0, max_size)
        if idx == -1:
            # Try CJK/English sentence endings
            for pat in ("。", "！", "？", ".", "!", "?"):
                idx = remaining.rfind(pat, 0, max_size)
                if idx != -1:
                    idx += 1  # include the punctuation
                    break
        if idx == -1 or idx == 0:
            idx = max_size

        chunks.append(remaining[:idx].strip())
        remaining = remaining[idx:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


def _extract_json(text: str) -> dict:
    """Extract JSON object from LLM response, handling markdown code fences."""
    text = text.strip()
    # Remove markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    # Find first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


async def generate_summary(
    transcript: str,
    provider: AIProvider,
    custom_prompt: str | None = None,
    source_url: str = "",
    video_title: str | None = None,
    language: str | None = None,
) -> ArticleSummary:
    """Generate structured summary from transcript text."""
    system = custom_prompt if custom_prompt else DEFAULT_SYSTEM_PROMPT

    if len(transcript) <= CHUNK_THRESHOLD:
        raw = await provider.complete(system, transcript)
        data = _extract_json(raw)
    else:
        # Long text: chunk → summarize each → merge
        chunks = _split_into_chunks(transcript)
        chunk_summaries: list[str] = []

        for i, chunk in enumerate(chunks, 1):
            context_note = f"（以下是第 {i}/{len(chunks)} 段，請保持語氣一致）\n\n"
            raw = await provider.complete(system, context_note + chunk)
            chunk_summaries.append(raw)

        # Merge all chunk summaries
        merge_input = "\n\n---\n\n".join(
            f"第 {i}/{len(chunks)} 段摘要：\n{s}"
            for i, s in enumerate(chunk_summaries, 1)
        )
        raw = await provider.complete(MERGE_SYSTEM_PROMPT, merge_input)
        data = _extract_json(raw)

    return ArticleSummary(
        one_sentence=data.get("one_sentence", ""),
        key_points=data.get("key_points", []),
        full_transcript=data.get("full_transcript", transcript),
        source_url=source_url,
        video_title=video_title,
        language=language,
    )
