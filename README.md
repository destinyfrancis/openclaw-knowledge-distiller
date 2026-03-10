# Knowledge Distiller

Turn YouTube/Bilibili videos into structured knowledge articles in seconds.

**Features**
- Auto-extracts subtitles (skips ASR when available)
- Falls back to local ASR via `mlx-whisper` (Apple Silicon, no API cost)
- AI summarization: one-sentence essence + key points + cleaned transcript
- Supports Google Gemini, OpenAI, Anthropic
- **MCP Server** — connect from Claude Code / Open CLAW AI agents

---

## Installation

```bash
pip install knowledge-distiller          # basic
pip install "knowledge-distiller[whisper]"  # + mlx-whisper for local ASR
```

Or install from source with [uv](https://github.com/astral-sh/uv):

```bash
cd knowledge-distiller
uv sync
uv sync --extra whisper
```

---

## Quick Start

```bash
# Set your API key (one-time)
kd config set api-key "AIzaSy..."       # Google Gemini (default)

# Process a YouTube video
kd process "https://youtube.com/watch?v=dQw4w9WgXcQ"

# Save as Markdown
kd process "https://youtube.com/watch?v=..." --output article.md

# Chinese video
kd process "https://bilibili.com/video/BV..." --language zh

# Custom prompt
kd process "..." --prompt "提取所有投資建議和風險提醒"

# Use OpenAI instead
kd process "..." --provider openai --model gpt-4o-mini
```

---

## CLI Reference

### `kd process <url>`

Download → transcribe → summarize.

| Flag | Description |
|------|-------------|
| `--language`, `-l` | ISO-639-1 code (zh, en, ja…) |
| `--provider`, `-p` | `google` \| `openai` \| `anthropic` |
| `--model`, `-m` | AI model name |
| `--prompt` | Custom summarization prompt |
| `--output`, `-o` | Output file path |
| `--format`, `-f` | `markdown` (default) \| `json` \| `text` |
| `--no-subtitles` | Always use ASR, skip subtitle extraction |
| `--transcriber` | `mlx-whisper` (default) \| `qwen3-asr` |

### `kd subtitles <url>`

Extract subtitles only (no ASR, no summarization).

### `kd config set <key> <value>`

| Key | Example Value |
|-----|---------------|
| `provider` | `google`, `openai`, `anthropic` |
| `api-key` | `AIzaSy...` |
| `model` | `gemini-2.5-flash` |
| `language` | `zh` |
| `transcriber` | `mlx-whisper` |

### `kd mcp-server`

Start the MCP server on stdio transport.

---

## MCP Server (Claude Code / Open CLAW)

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "knowledge-distiller": {
      "command": "kd",
      "args": ["mcp-server"],
      "env": {
        "KD_API_KEY": "your-api-key-here",
        "KD_PROVIDER": "google"
      }
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `process_url` | Submit a URL for processing → returns `job_id` |
| `get_status` | Poll job status and progress |
| `get_result` | Get completed job result (full/summary/transcript) |
| `list_jobs` | List all jobs |
| `configure` | Update configuration |

### Typical Agent Workflow

```
Agent → process_url(url="https://youtube.com/watch?v=...")
      ← { "job_id": "a1b2c3d4" }

Agent → get_status(job_id="a1b2c3d4")
      ← { "status": "transcribing", "progress": 0.6 }

Agent → get_result(job_id="a1b2c3d4", format="summary")
      ← {
           "one_sentence": "...",
           "key_points": ["...", "..."]
         }
```

---

## Configuration File

`~/.config/knowledge-distiller/config.toml`

```toml
provider = "google"
model = "gemini-2.5-flash"
language = "zh"
transcriber = "mlx-whisper"
default_prompt = ""
```

Environment variables override config file:
- `KD_PROVIDER`, `KD_API_KEY`, `KD_MODEL`, `KD_LANGUAGE`, `KD_TRANSCRIBER`

---

## System Requirements

- Python 3.11+
- Apple Silicon recommended (for mlx-whisper local ASR)
- `yt-dlp` (auto-installed)
- ffmpeg (for audio extraction): `brew install ffmpeg`

---

## License

MIT
