"""MCP Server (stdio transport) — exposes knowledge-distiller tools to Claude Code / Open CLAW."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

from . import config, downloader, subtitle_extractor, transcriber
from .models import ProcessingStatus, ArticleSummary
from .providers import build_provider
from .summarizer import generate_summary

# In-memory job store (keyed by job_id)
_jobs: dict[str, ProcessingStatus] = {}

server = Server("knowledge-distiller")


# ─── Tool definitions ─────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="process_url",
            description=(
                "Submit a YouTube or Bilibili URL for processing. "
                "Steps: (1) extract subtitles if available, (2) download & transcribe with Qwen3-ASR MLX if no subtitles, "
                "(3) generate AI summary (optional, needs API key). "
                "No API key required for transcription-only mode. "
                "Returns a job_id to poll for results."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube or Bilibili URL"},
                    "language": {
                        "type": "string",
                        "description": "Language code: 'zh' (Mandarin), 'yue' (粵語 Cantonese), 'en', 'ja', 'ko', etc. Auto-detect if omitted.",
                    },
                    "prompt": {"type": "string", "description": "Custom AI summarization prompt. Optional."},
                    "asr_prompt": {
                        "type": "string",
                        "description": "Context hint for Qwen3-ASR (e.g. '這是粵語口語對話，請保留懶音'). Optional.",
                    },
                    "model_size": {
                        "type": "string",
                        "enum": ["1.7b", "0.6b"],
                        "description": "Qwen3-ASR model size. '1.7b' = higher accuracy (default), '0.6b' = faster.",
                    },
                    "provider": {"type": "string", "description": "AI provider for summary: google|openai|anthropic. Defaults to config."},
                    "ai_model": {"type": "string", "description": "AI model name for summary. Defaults to config."},
                    "no_subtitles": {"type": "boolean", "description": "Skip subtitle extraction, always use Qwen3-ASR. Default false."},
                    "no_summary": {
                        "type": "boolean",
                        "description": "Skip AI summarization — output transcript only. No API key needed. Default false.",
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="get_status",
            description="Check the processing status and progress of a job.",
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
            description="Retrieve the result of a completed job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job ID"},
                    "format": {
                        "type": "string",
                        "enum": ["full", "summary", "transcript"],
                        "description": "Output format: 'full' (all fields), 'summary' (one_sentence + key_points), 'transcript' (full_transcript only). Default: full.",
                    },
                },
                "required": ["job_id"],
            },
        ),
        Tool(
            name="list_jobs",
            description="List all jobs and their statuses.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="configure",
            description="Update knowledge-distiller configuration.",
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
        case "process_url":
            return await _handle_process_url(arguments)
        case "get_status":
            return _handle_get_status(arguments)
        case "get_result":
            return _handle_get_result(arguments)
        case "list_jobs":
            return _handle_list_jobs()
        case "configure":
            return _handle_configure(arguments)
        case _:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _handle_process_url(args: dict[str, Any]) -> list[TextContent]:
    job_id = str(uuid.uuid4())[:8]
    status = ProcessingStatus(job_id=job_id, status="queued", url=args["url"])
    _jobs[job_id] = status

    # Launch processing in background
    asyncio.create_task(_run_job(job_id, args))

    return [TextContent(type="text", text=f'{{"job_id": "{job_id}", "status": "queued"}}')]


async def _run_job(job_id: str, args: dict[str, Any]) -> None:
    job = _jobs[job_id]
    url = args["url"]
    language = args.get("language") or config.get("language")
    summary_prompt = args.get("prompt") or config.get("default_prompt") or None
    asr_prompt = args.get("asr_prompt") or ""
    model_size = args.get("model_size") or "1.7b"
    no_subtitles = args.get("no_subtitles", False)
    no_summary = args.get("no_summary", False)

    provider_name = args.get("provider") or config.get("provider", "google")
    model_name = args.get("ai_model") or config.get("model")
    api_key = config.get_api_key(str(provider_name))

    if not no_summary and not api_key:
        # Downgrade to transcript-only rather than hard-fail
        no_summary = True
        job.phase_message = "No API key — running in transcript-only mode"

    try:
        # Metadata
        job.status = "downloading"
        job.phase_message = "Fetching metadata..."
        job.progress = 0.05
        meta = downloader.fetch_metadata(url)

        transcript: str | None = None

        # Subtitles
        if not no_subtitles and meta.has_subtitles:
            job.status = "extracting_subtitles"
            job.phase_message = "Extracting subtitles..."
            job.progress = 0.2
            transcript = subtitle_extractor.extract_subtitles(url, str(language) if language else None)

        # ASR fallback
        if transcript is None:
            job.status = "downloading"
            job.phase_message = "Downloading audio..."
            job.progress = 0.15

            audio_path = await asyncio.to_thread(downloader.download_audio, url)

            job.status = "transcribing"
            job.phase_message = "Transcribing audio..."
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

        # Summarize (optional — requires API key)
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
                source_url=url,
                video_title=meta.title,
                language=str(language) if language else None,
            )

        # Build result (transcript-only if no summary)
        if summary is None:
            summary = ArticleSummary(
                one_sentence="(Transcript only — no AI summary)",
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


def _handle_get_status(args: dict[str, Any]) -> list[TextContent]:
    job_id = args["job_id"]
    if job_id not in _jobs:
        return [TextContent(type="text", text=f'{{"error": "Job {job_id!r} not found"}}')]

    job = _jobs[job_id]
    import json
    data = {
        "job_id": job.job_id,
        "status": job.status,
        "progress": round(job.progress, 2),
        "phase": job.phase_message,
    }
    if job.error:
        data["error"] = job.error
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False))]


def _handle_get_result(args: dict[str, Any]) -> list[TextContent]:
    import json

    job_id = args["job_id"]
    fmt = args.get("format", "full")

    if job_id not in _jobs:
        return [TextContent(type="text", text=f'{{"error": "Job {job_id!r} not found"}}')]

    job = _jobs[job_id]
    if job.status != "completed":
        return [TextContent(type="text", text=json.dumps({"status": job.status, "error": job.error}))]

    summary = job.result
    assert summary is not None

    match fmt:
        case "summary":
            data = {"one_sentence": summary.one_sentence, "key_points": summary.key_points}
        case "transcript":
            data = {"full_transcript": summary.full_transcript}  # type: ignore[assignment]
        case _:
            data = summary.model_dump(exclude_none=True)  # type: ignore[assignment]

    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2, default=str))]


def _handle_list_jobs() -> list[TextContent]:
    import json
    jobs_list = [
        {
            "job_id": j.job_id,
            "url": j.url,
            "status": j.status,
            "progress": round(j.progress, 2),
        }
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


# ─── Entry point ──────────────────────────────────────────────────────────────

async def run_server() -> None:
    """Start the MCP server on stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(run_server())
