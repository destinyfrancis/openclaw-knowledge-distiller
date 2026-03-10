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
import uuid
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from . import config, downloader, subtitle_extractor, transcriber
from .models import ProcessingStatus, ArticleSummary
from .providers import build_provider
from .summarizer import generate_summary, PROMPT_STYLES

# In-memory job store (keyed by job_id)
_jobs: dict[str, ProcessingStatus] = {}

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
                "Transcribe a YouTube or Bilibili video — returns the raw transcript and a "
                "ready-to-use summarization prompt. The agent (you) then performs the summarization "
                "using your own AI capabilities. No external AI API key needed.\n\n"
                "Steps: (1) extract subtitles if available (fastest), "
                "(2) otherwise download audio and transcribe locally with Qwen3-ASR MLX.\n\n"
                "After receiving the result, use the `suggested_prompt` as your system instruction "
                "and summarize the `transcript` yourself."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube or Bilibili URL"},
                    "language": {
                        "type": "string",
                        "description": "Language code: 'zh' (Mandarin), 'yue' (粵語), 'en', 'ja', 'ko', etc. Auto-detect if omitted.",
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
                        "description": "Context hint for Qwen3-ASR (e.g. '這是粵語口語對話，請保留懶音'). Optional.",
                    },
                    "model_size": {
                        "type": "string",
                        "enum": ["1.7b", "0.6b"],
                        "description": "Qwen3-ASR model size. '1.7b' = higher accuracy (default), '0.6b' = faster.",
                    },
                    "no_subtitles": {
                        "type": "boolean",
                        "description": "Skip subtitle extraction, always use Qwen3-ASR. Default false.",
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="process_url",
            description=(
                "Submit a YouTube or Bilibili URL for full processing including AI summarization. "
                "Use this when an external AI API key is configured and you want kd to handle "
                "everything end-to-end. Returns a job_id to poll.\n\n"
                "For Open CLAW agents, prefer `transcribe_url` instead — it returns the transcript "
                "so you can summarize using your own AI."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube or Bilibili URL"},
                    "language": {
                        "type": "string",
                        "description": "Language code: 'zh', 'yue', 'en', 'ja', 'ko', etc.",
                    },
                    "style": {
                        "type": "string",
                        "enum": list(PROMPT_STYLES.keys()),
                        "description": f"Summary style. Options: {style_list}. Default: standard.",
                    },
                    "prompt": {"type": "string", "description": "Custom AI summarization prompt (overrides style)."},
                    "asr_prompt": {"type": "string", "description": "Context hint for Qwen3-ASR. Optional."},
                    "model_size": {
                        "type": "string",
                        "enum": ["1.7b", "0.6b"],
                        "description": "Qwen3-ASR model size. '1.7b' (default) or '0.6b' (faster).",
                    },
                    "provider": {"type": "string", "description": "AI provider for summary: google|openai|anthropic."},
                    "ai_model": {"type": "string", "description": "AI model name for summary."},
                    "no_subtitles": {"type": "boolean", "description": "Skip subtitle extraction. Default false."},
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
            description="Update knowledge-distiller configuration (for process_url mode).",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "description": "AI provider: google|openai|anthropic"},
                    "model": {"type": "string", "description": "AI model name"},
                    "api_key": {"type": "string", "description": "API key for the current provider"},
                    "default_prompt": {"type": "string", "description": "Default summarization prompt"},
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

    try:
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
        return [TextContent(type="text", text=json.dumps({"status": "error", "error": str(e)}))]


# ─── process_url: async job queue (external AI summarization) ──────────────────

async def _handle_process_url(args: dict[str, Any]) -> list[TextContent]:
    job_id = str(uuid.uuid4())[:8]
    status = ProcessingStatus(job_id=job_id, status="queued", url=args["url"])
    _jobs[job_id] = status
    asyncio.create_task(_run_job(job_id, args))
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
        job.phase_message = "No API key — transcript-only mode (use transcribe_url for agent summarization)"

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
            transcript = subtitle_extractor.extract_subtitles(url, str(language) if language else None)

        if transcript is None:
            job.status = "downloading"
            job.phase_message = "Downloading audio..."
            job.progress = 0.15
            audio_path = await asyncio.to_thread(downloader.download_audio, url)

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
            provider = build_provider(str(provider_name), api_key, str(model_name) if model_name else None)
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
                one_sentence="(Transcript only — summarize using your own AI with the style prompt from list_styles)",
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
        job.status = "failed"
        job.error = str(e)
        job.progress = 0.0


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
        return [TextContent(type="text", text=json.dumps({"status": job.status, "error": job.error}))]
    summary = job.result
    assert summary is not None
    match fmt:
        case "summary":
            data: Any = {"one_sentence": summary.one_sentence, "key_points": summary.key_points}
        case "transcript":
            data = {"full_transcript": summary.full_transcript}
        case _:
            data = summary.model_dump(exclude_none=True)
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2, default=str))]


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


def _handle_configure(args: dict[str, Any]) -> list[TextContent]:
    for key, value in args.items():
        if key == "api_key":
            provider = str(config.get("provider", "google"))
            config.save_api_key(provider, str(value))
        else:
            config.set_value(key, str(value))
    return [TextContent(type="text", text='{"ok": true, "message": "Configuration updated"}')]


# ─── Entry point ───────────────────────────────────────────────────────────────

async def run_server() -> None:
    """Start the MCP server on stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(run_server())
