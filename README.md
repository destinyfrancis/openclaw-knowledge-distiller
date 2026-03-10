# Knowledge Distiller 🎬→📚

> Turn YouTube/Bilibili videos into structured knowledge articles in seconds.
> 秒速將 YouTube/Bilibili 影片轉化為結構化知識文章。
> 秒速将 YouTube/Bilibili 视频转化为结构化知识文章。

[English](#english) · [繁體中文](#繁體中文) · [简体中文](#简体中文)

---

## English

### What is Knowledge Distiller?

Knowledge Distiller (`kd`) is an open-source CLI tool and MCP server that converts YouTube and Bilibili videos into structured knowledge articles — automatically.

**How it works:**
1. If the video has subtitles → extracts them directly (no transcription needed)
2. If no subtitles → downloads audio and transcribes locally with **Qwen3-ASR MLX** (Apple Silicon, no API key needed)
3. Optionally generates a multi-layer AI summary: one-sentence essence + key points + cleaned transcript

**Who is it for?**
- Researchers and students who need to digest video content quickly
- AI agent users (Claude Code / Open CLAW 龍蝦) who want to process videos programmatically
- Anyone who wants structured notes from videos without watching them in full

---

### Features

| Feature | Details |
|---------|---------|
| 🎙️ **Local ASR** | Qwen3-ASR MLX runs on-device (Apple Silicon). No API key, no cloud, free forever. |
| 📝 **Smart subtitles** | Auto-detects and extracts existing subtitles — skips ASR for faster results |
| 🤖 **AI summarization** | Supports Google Gemini, OpenAI, Anthropic — pick your provider |
| 🎨 **8 summary styles** | Standard, Academic, Action List, News Brief, Investment Analysis, Podcast Digest, ELI5, Bullet Notes |
| 🔌 **MCP Server** | Connect from Claude Code, Open CLAW, or any MCP-compatible AI agent |
| 🌏 **Multilingual** | Cantonese, Mandarin, English, Japanese, Korean, and 50+ languages |
| ⚡ **Zero API key mode** | `--no-summary` flag: pure transcription, no external services |

---

### Installation

**Prerequisites:**
```bash
brew install ffmpeg          # for audio extraction
pip install qwen-asr         # for local ASR (Apple Silicon)
```

**Install from PyPI (when available):**
```bash
pip install knowledge-distiller
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
# ── No API key needed ──────────────────────────────────────────────
# Transcript only (100% local, free)
kd process "https://youtube.com/watch?v=dQw4w9WgXcQ" --no-summary

# Cantonese video, local ASR
kd process "https://youtube.com/watch?v=..." \
  --language yue \
  --asr-prompt "這是粵語口語對話，請保留懶音" \
  --no-summary

# ── With AI summary (API key required) ────────────────────────────
kd config set api-key "AIzaSy..."        # Google Gemini (default)
kd process "https://youtube.com/watch?v=..."

# Save as Markdown
kd process "https://youtube.com/watch?v=..." --output article.md

# ── Summary styles ─────────────────────────────────────────────────
kd process "https://youtube.com/watch?v=..." --style investment
kd process "https://youtube.com/watch?v=..." --style podcast
kd process "https://youtube.com/watch?v=..." --style eli5
kd process "https://youtube.com/watch?v=..." --style bullets

# List all styles
kd styles

# ── Other providers ────────────────────────────────────────────────
kd process "..." --provider openai --model gpt-4o-mini
kd process "..." --provider anthropic --model claude-haiku-4-5-20251001
```

---

### Summary Styles

Run `kd styles` to list all styles, or choose with `--style <key>`:

| Key | Emoji | Name | Best For |
|-----|-------|------|----------|
| `standard` | 📋 | Standard Summary | General videos (default) |
| `academic` | 🎓 | Academic Notes | Lectures, research talks, papers |
| `actions` | ✅ | Action List | Tutorials, how-to, step-by-step guides |
| `news` | 📰 | News Brief | Interviews, news, current events |
| `investment` | 📈 | Investment Analysis | Finance, stocks, crypto, economics |
| `podcast` | 🎙️ | Podcast Digest | Conversations, talk shows, interviews |
| `eli5` | 🧒 | Explain Like I'm 5 | Tech, science, complex topics |
| `bullets` | ⚡ | Bullet Notes | Ultra-concise, fast scanning |

---

### CLI Reference

#### `kd process <url>`

Full pipeline: download → transcribe → summarize.

| Flag | Default | Description |
|------|---------|-------------|
| `--language`, `-l` | auto | Language code: `zh`, `yue` (Cantonese), `en`, `ja`, `ko`… |
| `--style`, `-s` | `standard` | Summary style preset (see `kd styles`) |
| `--provider`, `-p` | `google` | AI provider: `google` \| `openai` \| `anthropic` |
| `--model`, `-m` | provider default | AI model name (e.g. `gemini-2.5-flash`) |
| `--prompt` | — | Custom summarization prompt (overrides `--style`) |
| `--output`, `-o` | stdout | Output file path |
| `--format`, `-f` | `markdown` | Output format: `markdown` \| `json` \| `text` |
| `--no-subtitles` | false | Always use ASR, skip subtitle detection |
| `--no-summary` | false | Transcript only, no AI needed |
| `--transcriber` | `qwen3-asr` | ASR backend: `qwen3-asr` \| `mlx-whisper` |
| `--model-size` | `1.7b` | Qwen3-ASR size: `1.7b` (accurate) \| `0.6b` (fast) |
| `--asr-prompt` | — | Context hint for Qwen3-ASR (e.g. dialect, domain) |

#### `kd styles`

List all available summary style presets.

#### `kd subtitles <url>`

Extract subtitles only (no ASR, no summarization).

#### `kd config set <key> <value>`

| Key | Example |
|-----|---------|
| `api-key` | `AIzaSy...` |
| `provider` | `google`, `openai`, `anthropic` |
| `model` | `gemini-2.5-flash` |
| `language` | `zh` |
| `transcriber` | `qwen3-asr` |

#### `kd mcp-server`

Start MCP server on stdio transport (for Claude Code / Open CLAW).

---

### MCP Server Setup (Claude Code / Open CLAW)

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

#### MCP Tools

| Tool | Input | Output | Description |
|------|-------|--------|-------------|
| `process_url` | `url`, `language?`, `style?`, `prompt?`, `no_summary?`, `model_size?`… | `job_id` | Submit video for processing |
| `get_status` | `job_id` | `status`, `progress`, `phase` | Poll progress |
| `get_result` | `job_id`, `format?` | Summary / transcript | Get completed result |
| `list_jobs` | — | Job list | List all jobs |
| `configure` | `provider?`, `model?`… | Confirmation | Update config |

#### Typical Agent Workflow

```
Agent → process_url(url="https://youtube.com/watch?v=...", style="investment")
      ← { "job_id": "a1b2c3d4" }

Agent → get_status(job_id="a1b2c3d4")
      ← { "status": "transcribing", "progress": 0.6, "phase": "Transcribing audio..." }

Agent → get_result(job_id="a1b2c3d4", format="summary")
      ← {
           "one_sentence": "...",
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

Environment variables override config:
```bash
export KD_PROVIDER=google
export KD_API_KEY=AIzaSy...
export KD_MODEL=gemini-2.5-flash
export KD_LANGUAGE=zh
```

---

### System Requirements

- Python 3.11+
- macOS with Apple Silicon (M1/M2/M3/M4) — required for Qwen3-ASR MLX local inference
- `ffmpeg`: `brew install ffmpeg`
- `qwen-asr`: `pip install qwen-asr` (for local Qwen3-ASR transcription)
- `mlx-whisper`: `pip install mlx-whisper` (alternative ASR backend)

---

## 繁體中文

### 什麼是 Knowledge Distiller？

Knowledge Distiller（`kd`）係一個開源命令行工具同 MCP 伺服器，可以自動將 YouTube 同 Bilibili 影片轉化為結構化知識文章。

**處理流程：**
1. 若影片有字幕 → 直接提取（無需轉錄，速度更快）
2. 若無字幕 → 下載音頻，用 **Qwen3-ASR MLX** 在本地轉錄（Apple Silicon，無需 API Key）
3. 可選：用 AI 生成多層摘要（一句精華 + 要點列表 + 修正轉錄）

**適合誰使用？**
- 需要快速消化大量影片內容的研究者和學生
- 使用 Claude Code / Open CLAW（龍蝦）的 AI agent 用戶
- 任何想從影片獲取結構化筆記的人

---

### 主要功能

| 功能 | 說明 |
|------|------|
| 🎙️ **本地 ASR** | Qwen3-ASR MLX 在設備上運行（Apple Silicon），無 API 費用，完全免費 |
| 📝 **智能字幕偵測** | 自動偵測並提取現有字幕，有字幕就跳過 ASR |
| 🤖 **AI 摘要** | 支援 Google Gemini、OpenAI、Anthropic |
| 🎨 **8 種摘要風格** | 標準、學術、行動清單、新聞速報、投資分析、播客速覽、深入淺出、極簡子彈 |
| 🔌 **MCP 伺服器** | 可從 Claude Code、Open CLAW 或任何 MCP 相容 AI agent 連接 |
| 🌏 **多語言** | 粵語、普通話、英語、日語、韓語及 50+ 種語言 |
| ⚡ **零 API Key 模式** | `--no-summary` 旗標：純轉錄，無需任何外部服務 |

---

### 安裝

```bash
# 先安裝依賴
brew install ffmpeg
pip install qwen-asr

# 從 GitHub 安裝
git clone https://github.com/destinyfrancis/knowledge-distiller.git
cd knowledge-distiller
pip install -e .
```

---

### 快速開始

```bash
# 純轉錄（無需 API Key，完全本地）
kd process "https://youtube.com/watch?v=..." --no-summary

# 粵語影片
kd process "https://youtube.com/watch?v=..." \
  --language yue \
  --asr-prompt "這是粵語口語對話，請保留懶音" \
  --no-summary

# 設定 API Key（一次性）
kd config set api-key "AIzaSy..."

# 標準摘要
kd process "https://youtube.com/watch?v=..."

# 選擇摘要風格
kd process "https://youtube.com/watch?v=..." --style investment   # 投資分析
kd process "https://youtube.com/watch?v=..." --style academic     # 學術筆記
kd process "https://youtube.com/watch?v=..." --style podcast      # 播客速覽
kd process "https://youtube.com/watch?v=..." --style eli5         # 深入淺出

# 列出所有風格
kd styles

# 儲存為 Markdown
kd process "https://youtube.com/watch?v=..." --output article.md
```

---

### 8 種摘要風格

| Key | 名稱 | 最適合 |
|-----|------|--------|
| `standard` | 📋 標準摘要 | 一般影片（預設） |
| `academic` | 🎓 學術筆記 | 學術演講、研究討論 |
| `actions` | ✅ 行動清單 | 教程、How-to、步驟指引 |
| `news` | 📰 新聞速報 | 訪談、時事、新聞 |
| `investment` | 📈 投資分析 | 財經、股票、加密貨幣 |
| `podcast` | 🎙️ 播客速覽 | 對話、訪問、脫口秀 |
| `eli5` | 🧒 深入淺出 | 科技、科學、複雜主題 |
| `bullets` | ⚡ 極簡子彈 | 極速瀏覽、做筆記 |

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

Agent → get_result(job_id="a1b2c3d4")
      ← {
           "one_sentence": "核心投資論點...",
           "key_points": ["【投資論點】...", "【風險因素】..."],
           "full_transcript": "..."
         }
```

---

## 简体中文

### 什么是 Knowledge Distiller？

Knowledge Distiller（`kd`）是一个开源命令行工具和 MCP 服务器，可以自动将 YouTube 和 Bilibili 视频转化为结构化知识文章。

**处理流程：**
1. 若视频有字幕 → 直接提取（无需转录，速度更快）
2. 若无字幕 → 下载音频，用 **Qwen3-ASR MLX** 在本地转录（Apple Silicon，无需 API Key）
3. 可选：用 AI 生成多层摘要（一句精华 + 要点列表 + 修正转录）

---

### 主要功能

| 功能 | 说明 |
|------|------|
| 🎙️ **本地 ASR** | Qwen3-ASR MLX 在设备上运行（Apple Silicon），无 API 费用，完全免费 |
| 📝 **智能字幕检测** | 自动检测并提取现有字幕，有字幕就跳过 ASR |
| 🤖 **AI 摘要** | 支持 Google Gemini、OpenAI、Anthropic |
| 🎨 **8 种摘要风格** | 标准、学术、行动清单、新闻速报、投资分析、播客速览、深入浅出、极简子弹 |
| 🔌 **MCP 服务器** | 可从 Claude Code、Open CLAW 或任何 MCP 兼容 AI agent 连接 |
| 🌏 **多语言** | 粤语、普通话、英语、日语、韩语及 50+ 种语言 |
| ⚡ **零 API Key 模式** | `--no-summary` 标志：纯转录，无需任何外部服务 |

---

### 安装

```bash
brew install ffmpeg
pip install qwen-asr

git clone https://github.com/destinyfrancis/knowledge-distiller.git
cd knowledge-distiller
pip install -e .
```

---

### 快速开始

```bash
# 纯转录（无需 API Key）
kd process "https://youtube.com/watch?v=..." --no-summary

# 普通话视频
kd process "https://bilibili.com/video/BV..." --language zh --no-summary

# 设置 API Key
kd config set api-key "AIzaSy..."

# 标准摘要
kd process "https://youtube.com/watch?v=..."

# 选择摘要风格
kd process "https://youtube.com/watch?v=..." --style investment   # 投资分析
kd process "https://youtube.com/watch?v=..." --style academic     # 学术笔记
kd process "https://youtube.com/watch?v=..." --style bullets      # 极简子弹

# 列出所有风格
kd styles
```

---

### 8 种摘要风格

| Key | 名称 | 最适合 |
|-----|------|--------|
| `standard` | 📋 标准摘要 | 一般视频（默认） |
| `academic` | 🎓 学术笔记 | 学术演讲、研究讨论 |
| `actions` | ✅ 行动清单 | 教程、How-to、步骤指引 |
| `news` | 📰 新闻速报 | 采访、时事、新闻 |
| `investment` | 📈 投资分析 | 财经、股票、加密货币 |
| `podcast` | 🎙️ 播客速览 | 对话、访谈、脱口秀 |
| `eli5` | 🧒 深入浅出 | 科技、科学、复杂主题 |
| `bullets` | ⚡ 极简子弹 | 极速浏览、做笔记 |

---

### MCP 服务器配置（Claude Code / Open CLAW）

在 `~/.claude.json` 添加：

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

---

## License

MIT © 2026 Francis Tam

---

*Powered by [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR) · [yt-dlp](https://github.com/yt-dlp/yt-dlp) · [Apple MLX](https://github.com/ml-explore/mlx)*
