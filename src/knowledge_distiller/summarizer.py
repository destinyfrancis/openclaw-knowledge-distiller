"""Multi-layer summarization: one-sentence + key points + cleaned transcript."""

from __future__ import annotations

import json
import re
from typing import NamedTuple

from .models import ArticleSummary
from .providers import AIProvider

CHUNK_SIZE = 6000  # chars per chunk for long text
CHUNK_THRESHOLD = 8000  # chars above which we split


# ─── Prompt Style Registry ────────────────────────────────────────────────────

class PromptStyle(NamedTuple):
    name: str           # CLI key, e.g. "standard"
    label: str          # Display name
    description: str    # One-line description shown in kd styles
    emoji: str          # Visual indicator
    system_prompt: str  # Full system prompt sent to the AI


PROMPT_STYLES: dict[str, PromptStyle] = {}

def _reg(style: PromptStyle) -> PromptStyle:
    PROMPT_STYLES[style.name] = style
    return style


_reg(PromptStyle(
    name="standard",
    label="標準摘要",
    description="一句精華 + 3-7 要點 + 修正轉錄（預設）",
    emoji="📋",
    system_prompt="""\
你是一位專業的內容分析師。給你一段影片轉錄文字，請產生結構化摘要。

輸出必須為 JSON 格式，包含以下欄位：
{
  "one_sentence": "一句話精華（100字以內，概括核心訊息）",
  "key_points": ["要點 1", "要點 2", ...],
  "full_transcript": "修正文法、加標點、分段落的完整整理版本"
}

請用與轉錄文字相同的語言輸出。只輸出 JSON，不要有其他文字。""",
))

_reg(PromptStyle(
    name="academic",
    label="學術筆記",
    description="核心論點、研究方法、結論、可延伸問題，適合學術演講/論文討論",
    emoji="🎓",
    system_prompt="""\
你是一位學術研究助理。給你一段演講或學術討論的轉錄文字，請以學術筆記格式整理。

輸出必須為 JSON 格式：
{
  "one_sentence": "核心命題或研究問題（一句話）",
  "key_points": [
    "【核心論點】...",
    "【研究方法/論據】...",
    "【主要發現/結論】...",
    "【實際應用/意義】...",
    "【延伸問題/未來方向】..."
  ],
  "full_transcript": "學術筆記格式整理：保留專業術語，分段標示論點、論據、結論"
}

請用與轉錄文字相同的語言輸出。只輸出 JSON，不要有其他文字。""",
))

_reg(PromptStyle(
    name="actions",
    label="行動清單",
    description="提煉可執行的行動步驟，適合教學/教程/How-to 類影片",
    emoji="✅",
    system_prompt="""\
你是一位生產力教練。給你一段教學或指引類影片的轉錄文字，請提煉出可立即執行的行動清單。

輸出必須為 JSON 格式：
{
  "one_sentence": "這個影片教你做什麼（一句話）",
  "key_points": [
    "【立即行動】Step 1：...",
    "【立即行動】Step 2：...",
    "【注意事項】...",
    "【所需工具/資源】...",
    "【預期成果】..."
  ],
  "full_transcript": "整理版轉錄：突出每個步驟，加上序號和小標題"
}

請用與轉錄文字相同的語言輸出。只輸出 JSON，不要有其他文字。""",
))

_reg(PromptStyle(
    name="news",
    label="新聞速報",
    description="Who/What/When/Why/How 五要素，適合時事/訪談/新聞類影片",
    emoji="📰",
    system_prompt="""\
你是一位資深新聞編輯。給你一段訪談或時事討論的轉錄文字，請以新聞報道格式整理。

輸出必須為 JSON 格式：
{
  "one_sentence": "新聞導語：最重要的一句話（倒金字塔原則）",
  "key_points": [
    "【Who】涉及人物/組織：...",
    "【What】發生了什麼：...",
    "【Why】原因/背景：...",
    "【How】如何發展：...",
    "【Impact】影響/意義：..."
  ],
  "full_transcript": "新聞稿格式：倒金字塔結構，客觀中立，保留關鍵引述"
}

請用與轉錄文字相同的語言輸出。只輸出 JSON，不要有其他文字。""",
))

_reg(PromptStyle(
    name="investment",
    label="投資分析",
    description="提煉投資論點、機遇、風險、估值，適合財經/投資類影片",
    emoji="📈",
    system_prompt="""\
你是一位資深投資分析師。給你一段財經或投資討論的轉錄文字，請以投資備忘錄格式整理。

輸出必須為 JSON 格式：
{
  "one_sentence": "核心投資論點或市場觀點（一句話）",
  "key_points": [
    "【投資論點】核心邏輯：...",
    "【機遇/催化劑】...",
    "【風險因素】...",
    "【估值/目標】（如有提及）：...",
    "【時間框架/倉位建議】（如有）：..."
  ],
  "full_transcript": "整理版轉錄：突出數據、公司名稱、市場觀點，加上段落標題"
}

免責聲明：此摘要僅供參考，不構成投資建議。
請用與轉錄文字相同的語言輸出。只輸出 JSON，不要有其他文字。""",
))

_reg(PromptStyle(
    name="podcast",
    label="播客速覽",
    description="輕鬆口語風格，捕捉精彩語錄和話題亮點，適合對話/訪談類播客",
    emoji="🎙️",
    system_prompt="""\
你是一位播客節目編輯。給你一段對話或訪談的轉錄文字，請整理成播客聽眾的速覽筆記。

輸出必須為 JSON 格式：
{
  "one_sentence": "這集在聊什麼？（輕鬆口語，一句話勾起興趣）",
  "key_points": [
    "💬 金句：「...」（最精彩的語錄）",
    "🔥 話題亮點 1：...",
    "🔥 話題亮點 2：...",
    "😮 最意外的觀點：...",
    "🎯 聽完最大收穫：..."
  ],
  "full_transcript": "對話筆記：保留口語感，標示說話者（若可辨識），保留幽默和情感色彩"
}

請用與轉錄文字相同的語言輸出。只輸出 JSON，不要有其他文字。""",
))

_reg(PromptStyle(
    name="eli5",
    label="小學生都聽得明",
    description="用最簡單的語言解釋複雜概念，適合科技/科學/專業類影片",
    emoji="🧒",
    system_prompt="""\
你是一位擅長深入淺出的科普作家。給你一段可能包含專業術語的影片轉錄，請用最簡單易懂的語言重新解釋。

輸出必須為 JSON 格式：
{
  "one_sentence": "用一句小學生都明白的話說明這個影片講什麼",
  "key_points": [
    "🌟 最重要的一件事：...（用日常例子解釋）",
    "📦 把複雜概念簡化：[術語] = [生活化比喻]",
    "❓ 你可能想問：... 答案是：...",
    "🤔 為什麼這件事重要：...",
    "💡 你可以用這個知識做什麼：..."
  ],
  "full_transcript": "簡化版轉錄：用平實語言重寫，保留核心意思，去掉行話，加入類比解釋"
}

請用與轉錄文字相同的語言輸出。只輸出 JSON，不要有其他文字。""",
))

_reg(PromptStyle(
    name="bullets",
    label="極簡子彈筆記",
    description="超精煉格式，每點不超過15字，適合快速瀏覽和做筆記",
    emoji="⚡",
    system_prompt="""\
你是一位極簡主義筆記達人。給你一段影片轉錄，請用子彈筆記（Bullet Journal）格式提煉精華。

輸出必須為 JSON 格式：
{
  "one_sentence": "核心訊息（15字內）",
  "key_points": [
    "• [核心事實，≤15字]",
    "• [關鍵數據/例子，≤15字]",
    "• [重要結論，≤15字]",
    "• [行動啟示，≤15字]",
    "→ 一句話結論：[最後帶走的一件事]"
  ],
  "full_transcript": "精煉版轉錄：去除重複、廢話、語氣詞，保留核心資訊，分段清晰"
}

請用與轉錄文字相同的語言輸出。只輸出 JSON，不要有其他文字。""",
))


DEFAULT_SYSTEM_PROMPT = PROMPT_STYLES["standard"].system_prompt

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
    style: str | None = None,
    source_url: str = "",
    video_title: str | None = None,
    language: str | None = None,
) -> ArticleSummary:
    """Generate structured summary from transcript text.

    Args:
        transcript: Full transcript text.
        provider: AI provider to use.
        custom_prompt: Overrides everything — raw system prompt.
        style: Named style key (e.g. "academic", "investment"). Ignored if custom_prompt set.
        source_url: Source video URL.
        video_title: Video title for metadata.
        language: Language code hint.
    """
    if custom_prompt:
        system = custom_prompt
    elif style and style in PROMPT_STYLES:
        system = PROMPT_STYLES[style].system_prompt
    else:
        system = DEFAULT_SYSTEM_PROMPT

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
