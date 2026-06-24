"""MCP Server (stdio transport) — exposes knowledge-distiller tools to Open CLAW / Claude Code.

Architecture note
─────────────────
This server handles ONLY the heavy lifting that AI agents cannot do themselves:
  1. Subtitle extraction (yt-dlp, no API key)
  2. Local audio transcription (Qwen3-ASR MLX, Apple Silicon, no API key)

Summarization is intentionally left to the calling agent (Open CLAW / Claude).
The server returns the raw transcript + a ready-to-use system prompt for the
chosen style, so the agent can summarize using its own AI capabilities.

This means: zero external AI API calls from this server.
The agent is the AI — kd is just the transcription pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import subprocess
import tempfile
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from . import config, downloader, subtitle_extractor, transcriber
from .models import ArticleSummary, ProcessingStatus
from .providers import build_provider
from .summarizer import PROMPT_STYLES, generate_summary

logger = logging.getLogger(__name__)

# In-memory job store (keyed by job_id) — bounded to prevent unbounded memory growth
_MAX_JOBS = 100

class _BoundedJobStore(OrderedDict):
    def __setitem__(self, key: str, value: ProcessingStatus) -> None:
        super().__setitem__(key, value)
        while len(self) > _MAX_JOBS:
            self.popitem(last=False)  # evict oldest

_jobs: _BoundedJobStore = _BoundedJobStore()

# URL allowlist — C3: prevent SSRF via yt-dlp's broad extractor support
_ALLOWED_HOSTS = re.compile(
    r"^(www\.|m\.)?(youtube\.com|youtu\.be|yt\.be"
    r"|bilibili\.com|b23\.tv"
    r"|facebook\.com|fb\.watch)$",
    re.IGNORECASE,
)

_LOCAL_MEDIA_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".flac",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
    ".wma",
}

def _validate_url(url: str) -> None:
    """Raise ValueError if url is not an allowed YouTube/Bilibili/Facebook URL."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only http/https URLs are allowed (got: {parsed.scheme!r})")
    if not parsed.netloc or not _ALLOWED_HOSTS.match(parsed.netloc):
        raise ValueError(
            f"Unsupported platform: {parsed.netloc!r}. "
            "Only YouTube, Bilibili, and Facebook are supported."
        )

def _resolve_local_media_path(path_or_uri: str) -> Path:
    """Return a validated local media file path from a path or file:// URI."""
    if not isinstance(path_or_uri, str) or not path_or_uri.strip():
        raise ValueError("path must be a non-empty string")

    parsed = urlparse(path_or_uri)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError("Only local file paths or file:// URIs are allowed")

    if parsed.scheme == "file":
        if parsed.netloc and parsed.netloc not in ("localhost", "127.0.0.1"):
            raise ValueError(f"Remote file hosts are not supported: {parsed.netloc!r}")
        path = Path(unquote(parsed.path))
    else:
        path = Path(path_or_uri).expanduser()

    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Local media file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Local media path is not a file: {path}")
    if path.suffix.lower() not in _LOCAL_MEDIA_EXTENSIONS:
        raise ValueError(
            f"Unsupported local media extension: {path.suffix or '(none)'}. "
            f"Supported: {', '.join(sorted(_LOCAL_MEDIA_EXTENSIONS))}"
        )
    return path

def _extract_local_audio(media_path: Path) -> tuple[Path, Path]:
    """Extract a local media file's audio to WAV. Returns (audio_path, temp_dir)."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found. Install: brew install ffmpeg")

    temp_dir = Path(tempfile.mkdtemp(prefix="kd_local_audio_"))
    audio_path = temp_dir / "audio.wav"
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(media_path),
            "-vn",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-f",
            "wav",
            str(audio_path),
        ],
        capture_output=True,
        timeout=300,
    )
    if result.returncode != 0:
        shutil.rmtree(temp_dir, ignore_errors=True)
        stderr = result.stderr.decode(errors="replace")[:500]
        raise RuntimeError(f"ffmpeg failed extracting audio from local media: {stderr}")
    return audio_path, temp_dir

server = Server("openclaw-knowledge-distiller")


# ─── Tool definitions ──────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    style_list = " | ".join(f"{k} ({v.emoji} {v.label})" for k, v in PROMPT_STYLES.items())
    return [
        Tool(
            name="transcribe_url",
            description=(
                "**RECOMMENDED for Open CLAW agents.** "
                "Transcribe a YouTube, Bilibili, or Facebook video — returns the raw transcript "
                "and a ready-to-use summarization prompt. The agent (you) then performs the "
                "summarization using your own AI capabilities. No external AI API key needed.\n\n"
                "Steps: (1) extract subtitles if available (fastest), "
                "(2) otherwise download audio and transcribe locally with Qwen3-ASR MLX.\n\n"
                "After receiving the result, use the `suggested_prompt` as your system instruction "
                "and summarize the `transcript` yourself."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube, Bilibili, or Facebook URL"},
                    "language": {
                        "type": "string",
                        "description": (
                            "Language code: 'zh' (Mandarin), 'yue' (粵語), 'en', "
                            "'ja', 'ko', etc. Auto-detect if omitted."
                        ),
                    },
                    "style": {
                        "type": "string",
                        "enum": list(PROMPT_STYLES.keys()),
                        "description": (
                            "Summary style that determines the `suggested_prompt` returned. "
                            f"Options: {style_list}. Default: standard."
                        ),
                    },
                    "asr_prompt": {
                        "type": "string",
                        "description": (
                            "Context hint for Qwen3-ASR "
                            "(e.g. '這是粵語口語對話，請保留懶音'). Optional."
                        ),
                    },
                    "model_size": {
                        "type": "string",
                        "enum": ["1.7b", "0.6b"],
                        "description": (
                            "Qwen3-ASR model size. '1.7b' = higher accuracy "
                            "(default), '0.6b' = faster."
                        ),
                    },
                    "no_subtitles": {
                        "type": "boolean",
                        "description": (
                            "Skip subtitle extraction, always use Qwen3-ASR. Default false."
                        ),
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="transcribe_file",
            description=(
                "**For local media files.** Transcribe a local video or audio file from this "
                "machine and return the raw transcript plus a ready-to-use summarization prompt. "
                "Accepts absolute/relative paths or file:// URIs. The agent (you) then performs "
                "summarization using your own AI capabilities. No external AI API key needed.\n\n"
                "The server extracts audio with ffmpeg, then transcribes locally with "
                "Qwen3-ASR MLX or the configured transcription backend."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Local video/audio file path or file:// URI, "
                            "e.g. /Users/me/video.mp4"
                        ),
                    },
                    "language": {
                        "type": "string",
                        "description": (
                            "Language code: 'zh' (Mandarin), 'yue' (粵語), 'en', "
                            "'ja', 'ko', etc. Auto-detect if omitted."
                        ),
                    },
                    "style": {
                        "type": "string",
                        "enum": list(PROMPT_STYLES.keys()),
                        "description": (
                            "Summary style that determines the `suggested_prompt` returned. "
                            f"Options: {style_list}. Default: standard."
                        ),
                    },
                    "asr_prompt": {
                        "type": "string",
                        "description": (
                            "Context hint for Qwen3-ASR "
                            "(e.g. '這是粵語口語對話，請保留懶音'). Optional."
                        ),
                    },
                    "model_size": {
                        "type": "string",
                        "enum": ["1.7b", "0.6b"],
                        "description": (
                            "Qwen3-ASR model size. '1.7b' = higher accuracy "
                            "(default), '0.6b' = faster."
                        ),
                    },
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="process_url",
            description=(
                "Submit a YouTube, Bilibili, or Facebook URL for full processing "
                "including AI summarization. "
                "Use this when an external AI API key is configured and you want kd to handle "
                "everything end-to-end. Returns a job_id to poll.\n\n"
                "For Open CLAW agents, prefer `transcribe_url` instead — it returns the transcript "
                "so you can summarize using your own AI."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube, Bilibili, or Facebook URL"},
                    "language": {
                        "type": "string",
                        "description": "Language code: 'zh', 'yue', 'en', 'ja', 'ko', etc.",
                    },
                    "style": {
                        "type": "string",
                        "enum": list(PROMPT_STYLES.keys()),
                        "description": f"Summary style. Options: {style_list}. Default: standard.",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Custom AI summarization prompt (overrides style).",
                    },
                    "asr_prompt": {
                        "type": "string",
                        "description": "Context hint for Qwen3-ASR. Optional.",
                    },
                    "model_size": {
                        "type": "string",
                        "enum": ["1.7b", "0.6b"],
                        "description": "Qwen3-ASR model size. '1.7b' (default) or '0.6b' (faster).",
                    },
                    "provider": {
                        "type": "string",
                        "description": "AI provider for summary: google|openai|anthropic.",
                    },
                    "ai_model": {"type": "string", "description": "AI model name for summary."},
                    "no_subtitles": {
                        "type": "boolean",
                        "description": "Skip subtitle extraction. Default false.",
                    },
                    "no_summary": {
                        "type": "boolean",
                        "description": "Skip AI summarization — transcript only. Default false.",
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="get_status",
            description="Check the processing status and progress of a process_url job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job ID returned by process_url"},
                },
                "required": ["job_id"],
            },
        ),
        Tool(
            name="get_result",
            description="Retrieve the result of a completed process_url job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job ID"},
                    "format": {
                        "type": "string",
                        "enum": ["full", "summary", "transcript"],
                        "description": "Output format. Default: full.",
                    },
                },
                "required": ["job_id"],
            },
        ),
        Tool(
            name="list_styles",
            description=(
                "List all available summary style presets with their names, descriptions, "
                "and system prompts. Use the system prompt as your summarization instruction "
                "after receiving a transcript from transcribe_url."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "style": {
                        "type": "string",
                        "description": "Optional: get details for a specific style only.",
                    },
                },
            },
        ),
        Tool(
            name="list_jobs",
            description="List all process_url jobs and their statuses.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="configure",
            description=(
                "Update knowledge-distiller configuration (for process_url mode). "
                "API keys cannot be set via MCP — use the CLI: kd config set api-key <key>, "
                "or set environment variables: "
                "KD_API_KEY / GOOGLE_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": "AI provider: google|openai|anthropic",
                    },
                    "model": {"type": "string", "description": "AI model name"},
                    "default_prompt": {
                        "type": "string",
                        "description": "Default summarization prompt",
                    },
                    "language": {"type": "string", "description": "Default language code"},
                },
            },
        ),
    ]


# ─── Tool handlers ─────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    match name:
        case "transcribe_url":
            return await _handle_transcribe_url(arguments)
        case "transcribe_file":
            return await _handle_transcribe_file(arguments)
        case "process_url":
            return await _handle_process_url(arguments)
        case "get_status":
            return _handle_get_status(arguments)
        case "get_result":
            return _handle_get_result(arguments)
        case "list_styles":
            return _handle_list_styles(arguments)
        case "list_jobs":
            return _handle_list_jobs()
        case "configure":
            return _handle_configure(arguments)
        case _:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ─── transcribe_url: recommended for Open CLAW agents ─────────────────────────

async def _handle_transcribe_url(args: dict[str, Any]) -> list[TextContent]:
    """
    Transcribe a video and return the transcript + suggested summarization prompt.
    The calling agent (Open CLAW) handles summarization using its own AI.
    No external AI API key required.
    """
    url = args["url"]
    language = args.get("language") or config.get("language")
    asr_prompt = args.get("asr_prompt") or ""
    model_size = args.get("model_size") or "1.7b"
    no_subtitles = args.get("no_subtitles", False)
    style_key = args.get("style") or "standard"
    style = PROMPT_STYLES.get(style_key, PROMPT_STYLES["standard"])

    audio_dir = None  # track temp dir for cleanup in finally

    try:
        # C3: Validate URL before passing to yt-dlp
        _validate_url(url)

        # Step 1: metadata
        meta = downloader.fetch_metadata(url)

        transcript: str | None = None
        source = "asr"

        # Step 2: subtitles (fast path)
        if not no_subtitles and meta.has_subtitles:
            transcript = await asyncio.to_thread(
                subtitle_extractor.extract_subtitles,
                url,
                str(language) if language else None,
            )
            if transcript:
                source = "subtitles"

        # Step 3: local ASR (Qwen3-ASR MLX) — no API key needed
        if transcript is None:
            audio_path = await asyncio.to_thread(downloader.download_audio, url)
            audio_dir = audio_path.parent  # track for cleanup
            backend = str(config.get("transcriber", "qwen3-asr"))
            transcript = await asyncio.to_thread(
                transcriber.transcribe,
                audio_path,
                str(language) if language else None,
                backend,
                str(model_size),
                str(asr_prompt),
                None,
            )
            source = "qwen3-asr"

        data = {
            "status": "ready",
            "title": meta.title,
            "url": url,
            "language": language or "auto-detected",
            "transcript_source": source,   # "subtitles" or "qwen3-asr"
            "transcript": transcript or "",
            "style": style_key,
            "style_label": f"{style.emoji} {style.label}",
            # Hand this prompt to your AI to generate the summary:
            "suggested_prompt": style.system_prompt,
            "instructions": (
                "Use `suggested_prompt` as your system instruction and `transcript` as the user "
                "message to generate a structured summary. Output JSON with keys: "
                "one_sentence, key_points (list), full_transcript."
            ),
        }
        return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]

    except Exception as e:
        logger.exception("transcribe_url failed for url=%s", url)
        return [TextContent(type="text", text=json.dumps({
            "status": "error",
            "error": f"Transcription failed: {type(e).__name__}: {e}",
        }))]
    finally:
        # H1: Clean up temp audio directory
        if audio_dir is not None:
            shutil.rmtree(audio_dir, ignore_errors=True)


# ─── transcribe_file: local media files ───────────────────────────────────────

async def _handle_transcribe_file(args: dict[str, Any]) -> list[TextContent]:
    """
    Transcribe a local video/audio file and return transcript + summarization prompt.
    The calling agent handles summarization using its own AI.
    """
    path_arg = args["path"]
    language = args.get("language") or config.get("language")
    asr_prompt = args.get("asr_prompt") or ""
    model_size = args.get("model_size") or "1.7b"
    style_key = args.get("style") or "standard"
    style = PROMPT_STYLES.get(style_key, PROMPT_STYLES["standard"])

    audio_dir = None

    try:
        media_path = _resolve_local_media_path(path_arg)
        audio_path, audio_dir = await asyncio.to_thread(_extract_local_audio, media_path)
        backend = str(config.get("transcriber", "qwen3-asr"))
        transcript = await asyncio.to_thread(
            transcriber.transcribe,
            audio_path,
            str(language) if language else None,
            backend,
            str(model_size),
            str(asr_prompt),
            None,
        )

        data = {
            "status": "ready",
            "title": media_path.stem,
            "path": str(media_path),
            "language": language or "auto-detected",
            "transcript_source": backend,
            "transcript": transcript or "",
            "style": style_key,
            "style_label": f"{style.emoji} {style.label}",
            "suggested_prompt": style.system_prompt,
            "instructions": (
                "Use `suggested_prompt` as your system instruction and `transcript` as the user "
                "message to generate a structured summary. Output JSON with keys: "
                "one_sentence, key_points (list), full_transcript."
            ),
        }
        return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]

    except Exception as e:
        logger.exception("transcribe_file failed for path=%s", path_arg)
        return [TextContent(type="text", text=json.dumps({
            "status": "error",
            "error": f"Transcription failed: {type(e).__name__}: {e}",
        }))]
    finally:
        if audio_dir is not None:
            shutil.rmtree(audio_dir, ignore_errors=True)


# ─── process_url: async job queue (external AI summarization) ──────────────────

async def _handle_process_url(args: dict[str, Any]) -> list[TextContent]:
    url = args["url"]
    try:
        _validate_url(url)  # C3: validate before queuing
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"status": "error", "error": str(e)}))]

    job_id = str(uuid.uuid4())[:12]  # M5: 12 chars for better entropy
    status = ProcessingStatus(job_id=job_id, status="queued", url=url)
    _jobs[job_id] = status

    # H3: add done callback so unexpected exceptions are logged (not silently dropped)
    def _on_done(task: asyncio.Task) -> None:
        if not task.cancelled() and (exc := task.exception()):
            logger.exception("Background job %s raised unexpected error", job_id, exc_info=exc)

    task = asyncio.create_task(_run_job(job_id, args))
    task.add_done_callback(_on_done)

    return [TextContent(type="text", text=json.dumps({"job_id": job_id, "status": "queued"}))]


async def _run_job(job_id: str, args: dict[str, Any]) -> None:
    job = _jobs[job_id]
    url = args["url"]
    language = args.get("language") or config.get("language")
    summary_prompt = args.get("prompt") or config.get("default_prompt") or None
    asr_prompt = args.get("asr_prompt") or ""
    model_size = args.get("model_size") or "1.7b"
    no_subtitles = args.get("no_subtitles", False)
    no_summary = args.get("no_summary", False)
    style = args.get("style") or None

    provider_name = args.get("provider") or config.get("provider", "google")
    model_name = args.get("ai_model") or config.get("model")
    api_key = config.get_api_key(str(provider_name))

    if not no_summary and not api_key:
        no_summary = True
        job.phase_message = (
            "No API key — transcript-only mode (use transcribe_url for agent summarization)"
        )

    audio_dir = None  # track for cleanup

    try:
        job.status = "downloading"
        job.phase_message = "Fetching metadata..."
        job.progress = 0.05
        meta = downloader.fetch_metadata(url)

        transcript: str | None = None

        if not no_subtitles and meta.has_subtitles:
            job.status = "extracting_subtitles"
            job.phase_message = "Extracting subtitles..."
            job.progress = 0.2
            # H4: was blocking, now properly off the event loop
            transcript = await asyncio.to_thread(
                subtitle_extractor.extract_subtitles, url, str(language) if language else None
            )

        if transcript is None:
            job.status = "downloading"
            job.phase_message = "Downloading audio..."
            job.progress = 0.15
            audio_path = await asyncio.to_thread(downloader.download_audio, url)
            audio_dir = audio_path.parent  # H1: track for cleanup

            job.status = "transcribing"
            job.phase_message = "Transcribing with Qwen3-ASR MLX..."
            job.progress = 0.4
            backend = str(config.get("transcriber", "qwen3-asr"))
            transcript = await asyncio.to_thread(
                transcriber.transcribe,
                audio_path,
                str(language) if language else None,
                backend,
                str(model_size),
                str(asr_prompt),
                None,
            )

        summary = None
        if not no_summary and api_key:
            job.status = "summarizing"
            job.phase_message = "Generating summary..."
            job.progress = 0.8
            provider = build_provider(
                str(provider_name), api_key, str(model_name) if model_name else None
            )
            summary = await generate_summary(
                transcript,
                provider,
                custom_prompt=str(summary_prompt) if summary_prompt else None,
                style=str(style) if style else None,
                source_url=url,
                video_title=meta.title,
                language=str(language) if language else None,
            )

        if summary is None:
            summary = ArticleSummary(
                one_sentence=(
                    "(Transcript only — summarize using your own AI with the style prompt "
                    "from list_styles)"
                ),
                key_points=[],
                full_transcript=transcript,
                source_url=url,
                video_title=meta.title,
                language=str(language) if language else None,
            )

        job.status = "completed"
        job.progress = 1.0
        job.phase_message = "Done"
        job.result = summary

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        job.status = "failed"
        job.error = f"{type(e).__name__}: {e}"  # H5: type prefix, no raw data leak
        job.progress = 0.0

    finally:
        # H1: clean up temp audio directory
        if audio_dir is not None:
            shutil.rmtree(audio_dir, ignore_errors=True)


# ─── Remaining handlers ────────────────────────────────────────────────────────

def _handle_get_status(args: dict[str, Any]) -> list[TextContent]:
    job_id = args["job_id"]
    if job_id not in _jobs:
        return [TextContent(type="text", text=json.dumps({"error": f"Job {job_id!r} not found"}))]
    job = _jobs[job_id]
    data: dict[str, Any] = {
        "job_id": job.job_id,
        "status": job.status,
        "progress": round(job.progress, 2),
        "phase": job.phase_message,
    }
    if job.error:
        data["error"] = job.error
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False))]


def _handle_get_result(args: dict[str, Any]) -> list[TextContent]:
    job_id = args["job_id"]
    fmt = args.get("format", "full")
    if job_id not in _jobs:
        return [TextContent(type="text", text=json.dumps({"error": f"Job {job_id!r} not found"}))]
    job = _jobs[job_id]
    if job.status != "completed":
        return [
            TextContent(type="text", text=json.dumps({"status": job.status, "error": job.error}))
        ]
    summary = job.result
    if summary is None:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "Job completed but result is missing"}),
            )
        ]
    match fmt:
        case "summary":
            data: Any = {"one_sentence": summary.one_sentence, "key_points": summary.key_points}
        case "transcript":
            data = {"full_transcript": summary.full_transcript}
        case _:
            data = summary.model_dump(exclude_none=True)
    return [
        TextContent(
            type="text",
            text=json.dumps(data, ensure_ascii=False, indent=2, default=str),
        )
    ]


def _handle_list_styles(args: dict[str, Any]) -> list[TextContent]:
    specific = args.get("style")
    if specific and specific in PROMPT_STYLES:
        s = PROMPT_STYLES[specific]
        data = {
            "key": specific,
            "label": s.label,
            "emoji": s.emoji,
            "description": s.description,
            "system_prompt": s.system_prompt,
        }
    else:
        data = {  # type: ignore[assignment]
            "styles": [
                {
                    "key": k,
                    "label": s.label,
                    "emoji": s.emoji,
                    "description": s.description,
                    "system_prompt": s.system_prompt,
                }
                for k, s in PROMPT_STYLES.items()
            ],
            "usage": (
                "Call transcribe_url(url, style=<key>) to get the transcript + suggested_prompt. "
                "Then use suggested_prompt as system instruction to summarize with your own AI."
            ),
        }
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]


def _handle_list_jobs() -> list[TextContent]:
    jobs_list = [
        {"job_id": j.job_id, "url": j.url, "status": j.status, "progress": round(j.progress, 2)}
        for j in _jobs.values()
    ]
    return [TextContent(type="text", text=json.dumps(jobs_list, ensure_ascii=False, indent=2))]


_ALLOWED_CONFIG_KEYS = {"provider", "model", "default_prompt", "language", "transcriber"}

def _handle_configure(args: dict[str, Any]) -> list[TextContent]:
    # C2: API keys must not be sent over MCP stdio (risk of logging by calling agent)
    if "api_key" in args:
        return [TextContent(type="text", text=json.dumps({
            "ok": False,
            "error": (
                "API keys cannot be set via MCP (risk of logging by the agent). "
                "Use the CLI: kd config set api-key <key>  "
                "or set environment variables: "
                "KD_API_KEY / GOOGLE_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY"
            ),
        }))]

    rejected = []
    for key, value in args.items():
        if key in _ALLOWED_CONFIG_KEYS:
            config.set_value(key, str(value))
        else:
            rejected.append(key)
    if rejected:
        return [TextContent(type="text", text=json.dumps({
            "ok": False,
            "error": (
                f"Unknown config keys rejected: {rejected}. "
                f"Allowed: {sorted(_ALLOWED_CONFIG_KEYS)}"
            ),
        }))]
    return [TextContent(type="text", text='{"ok": true, "message": "Configuration updated"}')]


# ─── Entry point ───────────────────────────────────────────────────────────────

async def run_server() -> None:
    """Start the MCP server on stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(run_server())
