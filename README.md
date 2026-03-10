# Knowledge Distiller 🎬→📚

**English** · [繁體中文](#繁體中文)

> Turn YouTube/Bilibili videos into structured knowledge articles in seconds — locally, for free.
> 秒速將 YouTube/Bilibili 影片轉化為結構化知識文章 — 本地運行，完全免費。

---

## English

### What is Knowledge Distiller?

Knowledge Distiller (`kd`) is an open-source CLI tool and MCP server that converts YouTube and Bilibili videos into structured knowledge articles — automatically.

**How it works:**
1. If the video has subtitles → extracts them directly (no transcription needed, faster)
2. If no subtitles → downloads audio and transcribes locally with **Qwen3-ASR MLX** on Apple Silicon (no API key, no cloud cost)
3. Optionally generates a multi-layer AI summary: one-sentence essence + key points + cleaned transcript

**Who is it for?**
- Researchers and students who need to digest hours of video content quickly
- AI agent users (Claude Code / Open CLAW 龍蝦) who want to process videos programmatically
- Anyone who wants structured notes from videos without watching them in full

---

### Features

| Feature | Details |
|---------|---------|
| 🎙️ **Local ASR** | Qwen3-ASR MLX runs entirely on-device (Apple Silicon). No API key, no cloud, free forever. |
| 📝 **Smart subtitle detection** | Auto-detects existing subtitles — skips ASR for faster processing |
| 🤖 **AI summarization** | Supports Google Gemini, OpenAI, and Anthropic as summary providers |
| 🎨 **8 summary styles** | Standard, Academic, Action List, News Brief, Investment Analysis, Podcast Digest, ELI5, Bullet Notes |
| 🔌 **MCP Server** | Connect from Claude Code, Open CLAW, or any MCP-compatible AI agent |
| 🌏 **Multilingual** | Cantonese (粵語), Mandarin, English, Japanese, Korean, and 50+ languages |
| ⚡ **Zero API key mode** | `--no-summary`: pure local transcription, no external services needed |

---

### Installation

**Prerequisites:**
```bash
brew install ffmpeg          # audio extraction
pip install qwen-asr         # local Qwen3-ASR (Apple Silicon)
```

**Install from source:**
```bash
git clone https://github.com/destinyfrancis/knowledge-distiller.git
cd knowledge-distiller
pip install -e .
# or with uv:
uv sync
```

---

### Quick Start

```bash
# ── No API key needed (100% local) ────────────────────────────────
kd process "https://youtube.com/watch?v=dQw4w9WgXcQ" --no-summary

# Cantonese video with dialect hint
kd process "https://youtube.com/watch?v=..." \
  --language yue \
  --asr-prompt "這是粵語口語對話，請保留懶音" \
  --no-summary

# ── With AI summary ────────────────────────────────────────────────
kd config set api-key "AIzaSy..."   # Google Gemini (default provider)
kd process "https://youtube.com/watch?v=..."

# Save as Markdown file
kd process "https://youtube.com/watch?v=..." --output notes.md

# ── Choose a summary style ─────────────────────────────────────────
kd process "https://youtube.com/watch?v=..." --style investment
kd process "https://youtube.com/watch?v=..." --style academic
kd process "https://youtube.com/watch?v=..." --style podcast
kd process "https://youtube.com/watch?v=..." --style eli5

# List all available styles
kd styles

# ── Other AI providers ─────────────────────────────────────────────
kd process "..." --provider openai --model gpt-4o-mini
kd process "..." --provider anthropic --model claude-haiku-4-5-20251001
```

---

### Summary Styles

Run `kd styles` to list all styles. Choose with `--style <key>`:

| Key | | Name | Best For |
|-----|-|------|----------|
| `standard` | 📋 | Standard Summary | General videos (default) |
| `academic` | 🎓 | Academic Notes | Lectures, research talks, conference papers |
| `actions` | ✅ | Action List | Tutorials, how-to guides, step-by-step videos |
| `news` | 📰 | News Brief | Interviews, current events, news commentary |
| `investment` | 📈 | Investment Analysis | Finance, stocks, crypto, macro economics |
| `podcast` | 🎙️ | Podcast Digest | Conversations, talk shows, Q&A sessions |
| `eli5` | 🧒 | Explain Like I'm 5 | Tech, science, academic topics for a general audience |
| `bullets` | ⚡ | Bullet Notes | Ultra-concise, fast scanning, quick reference |

---

### CLI Reference

#### `kd process <url>`

Full pipeline: detect subtitles → transcribe (if needed) → summarize.

| Flag | Default | Description |
|------|---------|-------------|
| `--language`, `-l` | auto-detect | Language code: `zh`, `yue` (Cantonese), `en`, `ja`, `ko`… |
| `--style`, `-s` | `standard` | Summary style preset (run `kd styles` to list all) |
| `--provider`, `-p` | `google` | AI provider: `google` \| `openai` \| `anthropic` |
| `--model`, `-m` | provider default | AI model name (e.g. `gemini-2.5-flash`, `gpt-4o-mini`) |
| `--prompt` | — | Custom summarization prompt (overrides `--style`) |
| `--output`, `-o` | stdout | Output file path |
| `--format`, `-f` | `markdown` | Output format: `markdown` \| `json` \| `text` |
| `--no-subtitles` | false | Always use ASR, skip subtitle detection |
| `--no-summary` | false | Transcript only — no AI, no API key needed |
| `--transcriber` | `qwen3-asr` | ASR backend: `qwen3-asr` \| `mlx-whisper` |
| `--model-size` | `1.7b` | Qwen3-ASR size: `1.7b` (accurate) \| `0.6b` (faster) |
| `--asr-prompt` | — | Context hint for ASR (e.g. dialect, domain, speaker style) |

#### `kd styles`

List all built-in summary style presets.

#### `kd subtitles <url>`

Extract subtitles only — no ASR, no AI.

#### `kd config set <key> <value>`

| Key | Example |
|-----|---------|
| `api-key` | `AIzaSy...` |
| `provider` | `google`, `openai`, `anthropic` |
| `model` | `gemini-2.5-flash` |
| `language` | `zh` |
| `transcriber` | `qwen3-asr` |

#### `kd mcp-server`

Start the MCP server on stdio transport for Claude Code / Open CLAW.

---

### MCP Server (Claude Code / Open CLAW)

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

#### Available MCP Tools

| Tool | Description |
|------|-------------|
| `process_url` | Submit a video URL → returns `job_id`. Supports `style`, `language`, `no_summary`, `model_size`… |
| `get_status` | Poll job progress: `status`, `progress` (0–1), `phase` message |
| `get_result` | Get result: `format=full` \| `summary` \| `transcript` |
| `list_jobs` | List all submitted jobs |
| `configure` | Update provider, model, default prompt |

#### Typical Agent Workflow

```
Agent → process_url(url="https://youtube.com/watch?v=...", style="investment", language="zh")
      ← { "job_id": "a1b2c3d4" }

Agent → get_status(job_id="a1b2c3d4")
      ← { "status": "transcribing", "progress": 0.6, "phase": "Transcribing audio..." }

Agent → get_result(job_id="a1b2c3d4", format="summary")
      ← {
           "one_sentence": "核心投資論點...",
           "key_points": ["【投資論點】...", "【風險因素】..."]
         }
```

---

### Configuration

Config file: `~/.config/knowledge-distiller/config.toml`

```toml
provider = "google"
model = "gemini-2.5-flash"
language = "zh"
transcriber = "qwen3-asr"
default_prompt = ""
```

Environment variables (override config file):
```bash
export KD_PROVIDER=google
export KD_API_KEY=AIzaSy...
export KD_MODEL=gemini-2.5-flash
export KD_LANGUAGE=zh
```

---

### System Requirements

- Python 3.11+
- macOS with Apple Silicon (M1/M2/M3/M4) — required for Qwen3-ASR and mlx-whisper local inference
- `ffmpeg`: `brew install ffmpeg`
- `qwen-asr`: `pip install qwen-asr`
- `mlx-whisper`: `pip install mlx-whisper` (alternative ASR backend)

---

## 繁體中文

[Back to English](#english)

### 什麼是 Knowledge Distiller？

Knowledge Distiller（`kd`）係一個開源命令行工具同 MCP 伺服器，可以自動將 YouTube 同 Bilibili 影片轉化為結構化知識文章。

**處理流程：**
1. 若影片有字幕 → 直接提取（無需 ASR 轉錄，速度更快）
2. 若無字幕 → 下載音頻，用 **Qwen3-ASR MLX** 本地轉錄（Apple Silicon，無需 API Key，零費用）
3. 可選：用 AI 生成多層摘要（一句精華 + 要點列表 + 修正轉錄）

**適合誰使用？**
- 需要快速消化大量影片內容的研究者和學生
- 使用 Claude Code / Open CLAW（龍蝦）的 AI agent 用戶
- 想從影片獲取結構化筆記而無需完整觀看的人

---

### 主要功能

| 功能 | 說明 |
|------|------|
| 🎙️ **本地 ASR** | Qwen3-ASR MLX 完全在設備上運行（Apple Silicon），無 API 費用，永久免費 |
| 📝 **智能字幕偵測** | 自動偵測並提取現有字幕，有字幕就跳過 ASR，速度更快 |
| 🤖 **AI 摘要** | 支援 Google Gemini、OpenAI、Anthropic |
| 🎨 **8 種摘要風格** | 標準、學術、行動清單、新聞速報、投資分析、播客速覽、深入淺出、極簡子彈 |
| 🔌 **MCP 伺服器** | 可從 Claude Code、Open CLAW 或任何 MCP 相容 AI agent 連接 |
| 🌏 **多語言** | 粵語、普通話、英語、日語、韓語及 50+ 種語言 |
| ⚡ **零 API Key 模式** | `--no-summary`：純本地轉錄，無需任何外部服務 |

---

### 安裝

```bash
# 安裝依賴
brew install ffmpeg
pip install qwen-asr

# 從 GitHub 安裝
git clone https://github.com/destinyfrancis/knowledge-distiller.git
cd knowledge-distiller
pip install -e .
# 或使用 uv：
uv sync
```

---

### 快速開始

```bash
# ── 無需 API Key（完全本地）──────────────────────────────────────
kd process "https://youtube.com/watch?v=..." --no-summary

# 粵語影片
kd process "https://youtube.com/watch?v=..." \
  --language yue \
  --asr-prompt "這是粵語口語對話，請保留懶音" \
  --no-summary

# ── 使用 AI 摘要（需要 API Key）──────────────────────────────────
kd config set api-key "AIzaSy..."   # 設定 Google Gemini（預設）
kd process "https://youtube.com/watch?v=..."

# 儲存為 Markdown
kd process "https://youtube.com/watch?v=..." --output notes.md

# ── 選擇摘要風格 ───────────────────────────────────────────────────
kd process "https://youtube.com/watch?v=..." --style investment   # 投資分析
kd process "https://youtube.com/watch?v=..." --style academic     # 學術筆記
kd process "https://youtube.com/watch?v=..." --style podcast      # 播客速覽
kd process "https://youtube.com/watch?v=..." --style eli5         # 深入淺出
kd process "https://youtube.com/watch?v=..." --style bullets      # 極簡子彈

# 列出所有可用風格
kd styles
```

---

### 8 種摘要風格

執行 `kd styles` 查看完整列表，使用 `--style <key>` 選擇：

| Key | | 名稱 | 最適合 |
|-----|-|------|--------|
| `standard` | 📋 | 標準摘要 | 一般影片（預設） |
| `academic` | 🎓 | 學術筆記 | 學術演講、研究討論、學術報告 |
| `actions` | ✅ | 行動清單 | 教程、How-to、步驟指引 |
| `news` | 📰 | 新聞速報 | 訪談、時事、新聞評論 |
| `investment` | 📈 | 投資分析 | 財經、股票、加密貨幣、宏觀經濟 |
| `podcast` | 🎙️ | 播客速覽 | 對話、訪問、脫口秀 |
| `eli5` | 🧒 | 深入淺出 | 科技、科學、複雜主題 |
| `bullets` | ⚡ | 極簡子彈 | 極速瀏覽、快速筆記 |

---

### CLI 參考

#### `kd process <url>`

| 旗標 | 預設值 | 說明 |
|------|--------|------|
| `--language`, `-l` | 自動偵測 | 語言代碼：`zh`、`yue`（粵語）、`en`、`ja`、`ko`… |
| `--style`, `-s` | `standard` | 摘要風格（執行 `kd styles` 查看全部） |
| `--provider`, `-p` | `google` | AI 供應商：`google` \| `openai` \| `anthropic` |
| `--model`, `-m` | 供應商預設 | AI 模型名稱（例如 `gemini-2.5-flash`） |
| `--prompt` | — | 自訂摘要 prompt（覆蓋 `--style`） |
| `--output`, `-o` | 標準輸出 | 輸出檔案路徑 |
| `--format`, `-f` | `markdown` | 輸出格式：`markdown` \| `json` \| `text` |
| `--no-subtitles` | false | 跳過字幕偵測，強制使用 ASR |
| `--no-summary` | false | 純轉錄模式，無需 AI，無需 API Key |
| `--transcriber` | `qwen3-asr` | ASR 引擎：`qwen3-asr` \| `mlx-whisper` |
| `--model-size` | `1.7b` | Qwen3-ASR 模型大小：`1.7b`（高精度）\| `0.6b`（更快） |
| `--asr-prompt` | — | ASR 上下文提示（例如方言、領域、語氣） |

---

### MCP 伺服器配置（Claude Code / Open CLAW 龍蝦）

在 `~/.claude.json` 加入：

```json
{
  "mcpServers": {
    "knowledge-distiller": {
      "command": "kd",
      "args": ["mcp-server"],
      "env": {
        "KD_API_KEY": "你的 API Key",
        "KD_PROVIDER": "google"
      }
    }
  }
}
```

#### 典型 Agent 工作流程

```
Agent → process_url(url="https://youtube.com/watch?v=...", style="investment", language="zh")
      ← { "job_id": "a1b2c3d4" }

Agent → get_status(job_id="a1b2c3d4")
      ← { "status": "transcribing", "progress": 0.6 }

Agent → get_result(job_id="a1b2c3d4", format="summary")
      ← {
           "one_sentence": "核心投資論點...",
           "key_points": ["【投資論點】...", "【風險因素】..."],
           "full_transcript": "..."
         }
```

---

### 系統需求

- Python 3.11+
- macOS Apple Silicon（M1/M2/M3/M4）— Qwen3-ASR MLX 本地推理必需
- `ffmpeg`：`brew install ffmpeg`
- `qwen-asr`：`pip install qwen-asr`

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

### Contributors

| Avatar | Name | Role |
|--------|------|------|
| <img src="https://github.com/destinyfrancis.png" width="40" height="40" style="border-radius:50%"> | **[destinyfrancis](https://github.com/destinyfrancis)** | Creator & Maintainer |

---

## License

MIT © 2026 [destinyfrancis](https://github.com/destinyfrancis)

---

*Powered by [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR) · [yt-dlp](https://github.com/yt-dlp/yt-dlp) · [Apple MLX](https://github.com/ml-explore/mlx)*
