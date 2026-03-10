# Open CLAW Knowledge Distiller — Development Notes

## Project Overview

Open CLAW Knowledge Distiller (`kd`) is an open-source Python CLI + MCP Server that converts **YouTube, Bilibili, and Facebook videos** into structured knowledge articles — locally, for free.

**Repository**: https://github.com/destinyfrancis/openclaw-knowledge-distiller
**PyPI**: `openclaw-knowledge-distiller`
**Last Updated**: 2026-03-10 (v0.1.0 + Facebook support)

---

## Supported Platforms

- ✅ **YouTube** (youtube.com, youtu.be, yt.be)
- ✅ **Bilibili** (bilibili.com, b23.tv)
- ✅ **Facebook** (facebook.com, m.facebook.com, fb.watch) — *NEW in latest commit*

---

## Key Architecture Decisions

### 1. Agent-First Design

**Philosophy**: `kd` handles transcription only. AI agents (Open CLAW / Codex) handle summarization.

```
Agent → transcribe_url(url, style="investment")
     ← { transcript: "...", suggested_prompt: "<full system prompt>", ... }
     → Agent summarizes using its OWN AI (no external API key needed from kd)
```

**Benefits**:
- Zero external AI API calls from `kd` server
- Agent can use its full capabilities for summarization
- Simpler, more reliable, lower cost

### 2. URL Validation (Security)

**Prevention**: SSRF attacks via yt-dlp's broad extractor support.

**Implementation** (`mcp_server.py`):
```python
_ALLOWED_HOSTS = re.compile(
    r"^(www\.|m\.)?(youtube\.com|youtu\.be|yt\.be"
    r"|bilibili\.com|b23\.tv"
    r"|facebook\.com|fb\.watch)$",
    re.IGNORECASE,
)

def _validate_url(url: str) -> None:
    """Raise ValueError if url is not an allowed YouTube/Bilibili/Facebook URL."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only http/https URLs allowed (got: {parsed.scheme!r})")
    if not parsed.netloc or not _ALLOWED_HOSTS.match(parsed.netloc):
        raise ValueError(
            f"Unsupported platform: {parsed.netloc!r}. "
            "Only YouTube, Bilibili, and Facebook are supported."
        )
```

### 3. Transcription Pipeline

```
URL → fetch_metadata() → has_subtitles?
  ├─ YES → extract_subtitles() → transcript (fast, no ASR)
  └─ NO  → download_audio() → transcriber.transcribe() (local Qwen3-ASR MLX)
```

**Note on Facebook**: Facebook videos typically have no subtitles (yt-dlp doesn't surface them), so they fall through to audio download + Qwen3-ASR transcription.

---

## File Structure

```
src/knowledge_distiller/
├── mcp_server.py           # MCP Server (stdio) with URL validation
├── downloader.py           # yt-dlp wrapper (youtube, bilibili, facebook)
├── subtitle_extractor.py   # Subtitle extraction
├── transcriber.py          # ASR (qwen3-asr, mlx-whisper)
├── summarizer.py           # Summary generation + PROMPT_STYLES registry
├── providers.py            # AI providers (Google, OpenAI, Anthropic)
├── models.py               # Pydantic data models
├── config.py               # Config management (~/.config/knowledge-distiller/config.toml)
└── cli.py                  # CLI entry (typer)

tests/
└── test_mcp_server.py      # Unit tests (37 tests passing, includes Facebook URL validation)
```

---

## Recent Changes (Facebook Support — v0.1.0+)

### Code Changes (Commit: db5cacc)

**`mcp_server.py`**:
- Extended `_ALLOWED_HOSTS` regex: Added `facebook.com`, `m.facebook.com`, `fb.watch`
- Updated error message in `_validate_url()` to mention Facebook
- Updated tool descriptions (`transcribe_url`, `process_url`) to mention Facebook
- Updated `inputSchema` url descriptions

**`downloader.py`**:
- Updated module docstring
- Added Facebook detection in `detect_platform()` function
- Handles `facebook.com` and `fb.watch` domains

**`subtitle_extractor.py`**:
- Updated docstring to mention Facebook

**`tests/test_mcp_server.py`**:
- Added 14 parametrized URL validation tests
- Tests cover allowed URLs (YouTube, Bilibili, Facebook variants)
- Tests cover rejected URLs (Twitter, TikTok, evil.com, ftp://, file://)

### Documentation Changes (Commit: d30a1e5)

**`README.md`**:
- Tagline updated to mention Facebook support
- English intro updated
- Traditional Chinese (繁體中文) intro updated
- Simplified Chinese (简体中文) intro updated
- yt-dlp acknowledgement updated to mention Facebook

**`AGENTS.md`**:
- Project description updated to mention Facebook
- yt-dlp dependency description updated

---

## Development Workflow

### Setup

```bash
cd knowledge-distiller
uv sync
uv pip install -e .
```

### Running Tests

```bash
# All tests (37 passing)
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_mcp_server.py -v

# Coverage
python -m pytest tests/ --cov=src/
```

### Linting

```bash
ruff check src/ tests/
ruff format src/ tests/
```

### Running MCP Server

```bash
kd mcp-server
```

### CLI Usage

```bash
# Local transcription only (no API key needed)
kd process "https://www.facebook.com/videos/123456789" --language en --no-summary

# With AI summary (requires API key)
kd config set api-key "AIza..."
kd process "https://www.facebook.com/watch?v=123" --style investment
```

---

## Testing

### Test Coverage

**37 tests passing** (as of 2026-03-10):
- Job status tests (get_status, get_result, list_jobs)
- Configuration tests
- URL validation tests (14 new parametrized tests for Facebook)

### URL Validation Tests

```python
# Allowed URLs (should pass)
- https://www.youtube.com/watch?v=...
- https://youtu.be/...
- https://www.bilibili.com/video/...
- https://b23.tv/...
- https://www.facebook.com/videos/...
- https://www.facebook.com/watch?v=...
- https://m.facebook.com/watch?v=...
- https://fb.watch/...

# Rejected URLs (should raise ValueError)
- https://twitter.com/...
- https://tiktok.com/...
- ftp://youtube.com/...
- file:///etc/passwd
```

---

## Dependency Notes

| Dependency | Purpose | Version |
|------------|---------|---------|
| `yt-dlp` | Audio/subtitle extraction (YouTube, Bilibili, Facebook) | Latest |
| `qwen-asr` | Local Qwen3-ASR MLX transcription | Latest |
| `mcp` | MCP stdio server | Latest |
| `typer` | CLI framework | Latest |
| `httpx` | Async HTTP client | Latest |
| `pydantic` | Data validation | Latest |
| `keyring` | Secure API key storage | Latest |

---

## Future Enhancements

Potential areas for expansion:
- Additional video platforms (Instagram Reels, Twitter/X Videos, etc.)
- Speaker diarization for Facebook videos
- Real-time streaming support
- Batch processing improvements

---

## Contributing

When contributing:
1. Keep URL validation strict (security-first)
2. Update tests for any new platform support
3. Update README.md documentation (all 3 language sections)
4. Run `pytest` and `ruff` before committing
5. Follow commit message format: `feat: ...`, `fix: ...`, `docs: ...`, etc.

---

## Notes for AI Agents

- **Security**: Always validate URLs against `_ALLOWED_HOSTS` before processing
- **Testing**: Run full test suite after changes: `python -m pytest tests/ -v`
- **Documentation**: Update README.md, AGENTS.md, and this file when adding features
- **Backwards Compatibility**: Maintain API compatibility for existing `transcribe_url` and `process_url` calls

---

*Last updated: 2026-03-10*
