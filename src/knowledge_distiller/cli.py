"""CLI entry point for knowledge-distiller (kd)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from . import config, downloader, subtitle_extractor, transcriber
from .models import ArticleSummary
from .providers import build_provider
from .summarizer import generate_summary

app = typer.Typer(
    name="kd",
    help="Knowledge Distiller — turn YouTube/Bilibili videos into structured knowledge articles.",
    no_args_is_help=True,
)
console = Console()


# ─── process ────────────────────────────────────────────────────────────────

@app.command()
def process(
    url: Annotated[str, typer.Argument(help="YouTube or Bilibili URL")],
    language: Annotated[Optional[str], typer.Option("--language", "-l", help="Language code: zh, yue (粵語), en, ja, ko...")] = None,
    provider: Annotated[Optional[str], typer.Option("--provider", "-p", help="AI provider: google|openai|anthropic (for summary)")] = None,
    model: Annotated[Optional[str], typer.Option("--model", "-m", help="AI model name")] = None,
    prompt: Annotated[Optional[str], typer.Option("--prompt", help="Custom summary prompt")] = None,
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output file path")] = None,
    output_format: Annotated[str, typer.Option("--format", "-f", help="Output format: markdown|json|text")] = "markdown",
    no_subtitles: Annotated[bool, typer.Option("--no-subtitles", help="Skip subtitle extraction, always use ASR")] = False,
    no_summary: Annotated[bool, typer.Option("--no-summary", help="Skip AI summarization (transcription only, no API key needed)")] = False,
    transcriber_backend: Annotated[str, typer.Option("--transcriber", help="ASR backend: qwen3-asr (default) | mlx-whisper")] = "qwen3-asr",
    model_size: Annotated[str, typer.Option("--model-size", help="Qwen3-ASR model size: 1.7b (default) | 0.6b")] = "1.7b",
    custom_prompt: Annotated[Optional[str], typer.Option("--asr-prompt", help="Custom context for Qwen3-ASR (e.g. '這是粵語口語對話')")] = None,
) -> None:
    """
    Process a video URL: download/subtitle → transcribe → summarize.

    \b
    No API keys needed for transcription:
      kd process "https://youtube.com/watch?v=xxx" --no-summary

    Cantonese (粵語):
      kd process "https://youtube.com/watch?v=xxx" --language yue --asr-prompt "這是粵語口語對話"

    With AI summary (requires API key):
      kd process "https://youtube.com/watch?v=xxx" --language zh
    """
    asyncio.run(_process(url, language, provider, model, prompt, output, output_format,
                         no_subtitles, no_summary, transcriber_backend, model_size, custom_prompt or ""))


async def _process(
    url: str,
    language: str | None,
    provider_name: str | None,
    model_name: str | None,
    summary_prompt: str | None,
    output: Path | None,
    output_format: str,
    no_subtitles: bool,
    no_summary: bool,
    transcriber_backend: str,
    model_size: str,
    asr_custom_prompt: str,
) -> None:
    cfg = config.load()
    provider_name = provider_name or cfg.get("provider", "google")
    model_name = model_name or cfg.get("model")
    language = language or cfg.get("language")
    summary_prompt = summary_prompt or cfg.get("default_prompt") or None
    transcriber_backend = transcriber_backend or cfg.get("transcriber", "qwen3-asr")

    # Provider / API key only needed when summarizing
    provider = None
    if not no_summary:
        api_key = config.get_api_key(provider_name)
        if not api_key:
            console.print(f"[yellow]No API key for '{provider_name}' — running in transcript-only mode.[/yellow]")
            console.print(f"  To enable summarization: kd config set api-key <key>")
            no_summary = True
        else:
            provider = build_provider(provider_name, api_key, model_name)

    transcript: str | None = None
    title: str | None = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        # Step 1: Metadata
        task = progress.add_task("Fetching metadata...", total=None)
        try:
            meta = downloader.fetch_metadata(url)
            title = meta.title
            progress.update(task, description=f"[green]✓[/green] {meta.title or url[:60]}", completed=1, total=1)
        except Exception as e:
            progress.stop()
            console.print(f"[red]Error fetching metadata:[/red] {e}")
            raise typer.Exit(1)

        # Step 2: Subtitles or ASR
        if not no_subtitles and meta.has_subtitles:
            task2 = progress.add_task("Extracting subtitles...", total=None)
            try:
                transcript = subtitle_extractor.extract_subtitles(url, language)
                if transcript:
                    progress.update(task2, description="[green]✓[/green] Subtitles extracted (skipping ASR)", completed=1, total=1)
                else:
                    progress.update(task2, description="[yellow]![/yellow] No usable subtitles, falling back to ASR", completed=1, total=1)
            except Exception:
                transcript = None

        if transcript is None:
            task3 = progress.add_task("Downloading audio...", total=1.0)

            def dl_progress(p: float) -> None:
                progress.update(task3, completed=p, description=f"Downloading audio... {p*100:.0f}%")

            try:
                audio_path = downloader.download_audio(url, progress_callback=dl_progress)
                progress.update(task3, description="[green]✓[/green] Audio downloaded", completed=1.0)
            except Exception as e:
                progress.stop()
                console.print(f"[red]Error downloading audio:[/red] {e}")
                raise typer.Exit(1)

            task4 = progress.add_task("Transcribing...", total=None)

            def asr_progress(p: float, msg: str) -> None:
                progress.update(task4, description=f"Transcribing... {msg}")

            try:
                transcript = transcriber.transcribe(
                    audio_path,
                    language=language,
                    backend=transcriber_backend,
                    model_size=model_size,
                    custom_prompt=asr_custom_prompt,
                    progress_callback=asr_progress,
                )
                progress.update(task4, description="[green]✓[/green] Transcription complete", completed=1, total=1)
            except Exception as e:
                progress.stop()
                console.print(f"[red]Error transcribing:[/red] {e}")
                raise typer.Exit(1)

        # Step 3: Summarize (optional — requires AI API key)
        summary = None
        if not no_summary and provider is not None:
            task5 = progress.add_task("Generating summary...", total=None)
            try:
                summary = await generate_summary(
                    transcript,
                    provider,
                    custom_prompt=summary_prompt,
                    source_url=url,
                    video_title=title,
                    language=language,
                )
                progress.update(task5, description="[green]✓[/green] Summary generated", completed=1, total=1)
            except Exception as e:
                progress.stop()
                console.print(f"[yellow]Warning: Summary failed ({e}) — outputting transcript only.[/yellow]")
                # Fall through to output transcript

    # Output
    _render_output(summary, transcript or "", url, title, output_format, output)


def _render_output(
    summary: ArticleSummary | None,
    transcript: str,
    url: str,
    title: str | None,
    fmt: str,
    output: Path | None,
) -> None:
    if summary is not None:
        if fmt == "json":
            import json
            text = summary.model_dump_json(indent=2, exclude_none=True)
        elif fmt == "text":
            lines = [f"# {summary.video_title or summary.source_url}", f"\n{summary.one_sentence}\n"]
            lines += [f"• {p}" for p in summary.key_points]
            lines += ["\n--- Full Transcript ---\n", summary.full_transcript]
            text = "\n".join(lines)
        else:  # markdown
            text = summary.to_markdown()
    else:
        # Transcript-only mode (no API key / --no-summary)
        header = f"# {title or url}\n\n" if (title or url) else ""
        text = header + transcript

    if output:
        output.write_text(text, encoding="utf-8")
        console.print(f"\n[green]Saved to:[/green] {output}")
    else:
        console.print()
        if fmt == "markdown" and summary is not None:
            console.print(Markdown(text))
        else:
            console.print(text)


# ─── subtitles ───────────────────────────────────────────────────────────────

@app.command()
def subtitles(
    url: Annotated[str, typer.Argument(help="Video URL")],
    language: Annotated[Optional[str], typer.Option("--language", "-l")] = None,
    output: Annotated[Optional[Path], typer.Option("--output", "-o")] = None,
) -> None:
    """Extract subtitles only (no ASR, no summarization)."""
    with console.status("Extracting subtitles..."):
        text = subtitle_extractor.extract_subtitles(url, language)

    if not text:
        console.print("[red]No subtitles available for this video.[/red]")
        raise typer.Exit(1)

    if output:
        output.write_text(text, encoding="utf-8")
        console.print(f"[green]Saved to:[/green] {output}")
    else:
        console.print(text)


# ─── transcribe ──────────────────────────────────────────────────────────────

@app.command()
def transcribe_cmd(
    url: Annotated[str, typer.Argument(help="Video URL")],
    language: Annotated[Optional[str], typer.Option("--language", "-l")] = None,
    output: Annotated[Optional[Path], typer.Option("--output", "-o")] = None,
    backend: Annotated[str, typer.Option("--backend")] = "mlx-whisper",
) -> None:
    """Download audio and transcribe only (no summarization)."""
    typer.echo("transcribe command not yet implemented — use 'process' instead")
    raise typer.Exit(1)


transcribe_cmd.name = "transcribe"  # type: ignore[attr-defined]


# ─── config ──────────────────────────────────────────────────────────────────

config_app = typer.Typer(name="config", help="Manage configuration.", no_args_is_help=True)
app.add_typer(config_app)


@config_app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help="Config key")],
    value: Annotated[str, typer.Argument(help="Config value")],
) -> None:
    """Set a configuration value."""
    if key == "api-key":
        provider = config.get("provider", "google")
        config.save_api_key(str(provider), value)
        console.print(f"[green]API key saved for provider '{provider}'[/green]")
    else:
        config.set_value(key, value)
        console.print(f"[green]Set {key} = {value}[/green]")


@config_app.command("get")
def config_get(key: Annotated[str, typer.Argument()] = "") -> None:
    """Show current configuration."""
    cfg = config.load()
    if key:
        console.print(cfg.get(key, "[dim]not set[/dim]"))
    else:
        table = Table(title="knowledge-distiller config")
        table.add_column("Key", style="cyan")
        table.add_column("Value")
        for k, v in cfg.items():
            if k == "api_key":
                v = "***" if v else "[dim]not set[/dim]"
            table.add_row(k, str(v) if v is not None else "[dim]not set[/dim]")
        console.print(table)


# ─── mcp-server ──────────────────────────────────────────────────────────────

@app.command("mcp-server")
def mcp_server_cmd() -> None:
    """Start MCP server on stdio transport (for Claude Code / Open CLAW)."""
    from .mcp_server import run_server
    asyncio.run(run_server())


if __name__ == "__main__":
    app()
