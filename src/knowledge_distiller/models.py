"""Pydantic data models for knowledge-distiller."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl, field_validator


class VideoMetadata(BaseModel):
    url: str
    platform: Literal["youtube", "bilibili", "unknown"]
    title: str | None = None
    duration: float | None = None  # seconds
    has_subtitles: bool = False
    subtitle_languages: list[str] = []
    thumbnail_url: str | None = None
    uploader: str | None = None
    view_count: int | None = None


class ArticleSummary(BaseModel):
    one_sentence: str
    key_points: list[str]
    full_transcript: str
    source_url: str
    video_title: str | None = None
    language: str | None = None
    generated_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: object) -> None:
        if self.generated_at is None:
            self.generated_at = datetime.now()

    def to_markdown(self) -> str:
        lines = []
        if self.video_title:
            lines.append(f"# {self.video_title}\n")
        lines.append(f"> {self.one_sentence}\n")
        lines.append("## 要點\n")
        for point in self.key_points:
            lines.append(f"- {point}")
        lines.append("\n## 完整轉錄\n")
        lines.append(self.full_transcript)
        lines.append(f"\n---\n來源：{self.source_url}")
        lines.append(f"生成時間：{self.generated_at.strftime('%Y-%m-%d %H:%M')}")
        return "\n".join(lines)


class ProcessingStatus(BaseModel):
    job_id: str
    status: Literal["queued", "downloading", "extracting_subtitles", "transcribing", "summarizing", "completed", "failed"]
    progress: float = 0.0  # 0.0–1.0
    phase_message: str = ""
    error: str | None = None
    result: ArticleSummary | None = None
    url: str = ""
    created_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: object) -> None:
        if self.created_at is None:
            self.created_at = datetime.now()
