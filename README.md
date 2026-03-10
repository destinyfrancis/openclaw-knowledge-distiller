# Open CLAW Knowledge Distiller 🦞📚
### 龙虾知识蒸馏器 · 龍蝦知識蒸餾器

**English** · [繁體中文](#繁體中文) · [简体中文](#简体中文)

> Turn YouTube, Bilibili, and Facebook videos into structured knowledge articles in seconds — locally, for free.
> 秒速将 YouTube、Bilibili、Facebook 视频转化为结构化知识文章 — 本地运行，完全免费。

---

## English

### What is Open CLAW Knowledge Distiller?

Open CLAW Knowledge Distiller（**龍蝦知識蒸餾器**，`kd`）is an open-source CLI tool and MCP server built for the [Open CLAW](https://github.com/destinyfrancis) AI agent ecosystem. It converts YouTube, Bilibili, and Facebook videos into structured knowledge articles — automatically, locally, and for free.

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
brew install ffmpeg    # audio extraction
```

**Install:**
```bash
pip install openclaw-knowledge-distiller
# or with uv:
uv add openclaw-knowledge-distiller
```

> Qwen3-ASR model (~1-2 GB) downloads automatically from Hugging Face on first use.

**Install from source (for development):**
```bash
git clone https://github.com/destinyfrancis/openclaw-knowledge-distiller.git
cd openclaw-knowledge-distiller
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

### 什麼是龍蝦知識蒸餾器？

**Open CLAW Knowledge Distiller**（龍蝦知識蒸餾器，`kd`）係一個專為 Open CLAW（龍蝦）AI agent 生態系統而設計的開源命令行工具同 MCP 伺服器，可以自動將 YouTube、Bilibili 同 Facebook 影片轉化為結構化知識文章。

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
brew install ffmpeg   # 音頻提取工具

pip install openclaw-knowledge-distiller
# 或使用 uv：
uv add openclaw-knowledge-distiller
```

> Qwen3-ASR 模型（約 1-2 GB）首次使用時自動從 Hugging Face 下載，無需手動操作。

**從原始碼安裝（開發用）：**
```bash
git clone https://github.com/destinyfrancis/openclaw-knowledge-distiller.git
cd openclaw-knowledge-distiller
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

---

## 简体中文

[回到英文](#english) · [回到繁體中文](#繁體中文)

### 什么是龙虾知识蒸馏器？

**Open CLAW Knowledge Distiller**（龙虾知识蒸馏器，`kd`）是一款专为 Open CLAW AI 智能体生态系统设计的开源命令行工具和 MCP 服务器。它能自动将 YouTube、Bilibili 和 Facebook 视频转化为结构化知识文章，完全本地运行，无需任何云端费用。

**工作流程：**
1. 若视频有字幕 → 直接提取（最快，无需转录）
2. 若无字幕 → 下载音频，用 **Qwen3-ASR MLX** 在本地转录（Apple 芯片，无需 API 密钥）
3. 将转录文本和风格提示词返回给 Open CLAW，由智能体自行完成摘要生成

**核心设计理念：** `kd` 只负责下载和转录这两件重活，摘要生成交给龙虾自己的 AI 来完成——无需额外的 AI API 密钥。

---

### 主要功能

| 功能 | 说明 |
|------|------|
| 🎙️ **本地 ASR** | Qwen3-ASR MLX 完全在设备上运行（Apple 芯片），无 API 费用，永久免费 |
| 📝 **智能字幕检测** | 自动检测并提取现有字幕，有字幕直接跳过 ASR，速度更快 |
| 🤖 **智能体摘要** | 返回转录文本和提示词，由 Open CLAW 自身 AI 完成摘要，无需额外 API 密钥 |
| 🎨 **8 种摘要风格** | 标准、学术、行动清单、新闻速报、投资分析、播客速览、深入浅出、极简子弹 |
| 🔌 **MCP 服务器** | 可从 Claude Code、Open CLAW 或任何兼容 MCP 的 AI 智能体连接 |
| 🌏 **多语言支持** | 粤语、普通话、英语、日语、韩语及 50+ 种语言 |
| ⚡ **零 API 密钥模式** | `--no-summary`：纯本地转录，无需任何外部服务 |

---

### 安装

```bash
brew install ffmpeg   # 音频提取工具

pip install openclaw-knowledge-distiller
# 或使用 uv（推荐）：
uv add openclaw-knowledge-distiller
```

> Qwen3-ASR 模型（约 1-2 GB）首次使用时自动从 Hugging Face 下载，无需手动操作。

---

### 快速上手

```bash
# ── 零 API 密钥，纯本地转录 ─────────────────────────────────────
# 直接转录，输出文本
kd process "https://www.bilibili.com/video/BV..." --no-summary

# 指定普通话
kd process "https://www.bilibili.com/video/BV..." \
  --language zh \
  --no-summary

# 指定粤语（广东话）
kd process "https://youtube.com/watch?v=..." \
  --language yue \
  --asr-prompt "这是粤语口语对话，请保留原有发音特色" \
  --no-summary

# ── 配置 AI 摘要（可选，需要 API 密钥）───────────────────────────
kd config set api-key "AIzaSy..."       # 设置 Google Gemini（默认）
kd process "https://youtube.com/watch?v=..."

# 保存为 Markdown 文件
kd process "https://youtube.com/watch?v=..." --output 笔记.md

# ── 选择摘要风格 ───────────────────────────────────────────────────
kd process "https://youtube.com/watch?v=..." --style investment   # 投资分析
kd process "https://youtube.com/watch?v=..." --style academic     # 学术笔记
kd process "https://youtube.com/watch?v=..." --style actions      # 行动清单
kd process "https://youtube.com/watch?v=..." --style podcast      # 播客速览
kd process "https://youtube.com/watch?v=..." --style eli5         # 深入浅出
kd process "https://youtube.com/watch?v=..." --style bullets      # 极简子弹

# 查看所有可用风格
kd styles
```

---

### 8 种摘要风格

使用 `kd styles` 查看完整列表，通过 `--style <key>` 选择：

| Key | | 名称 | 最适合 |
|-----|-|------|--------|
| `standard` | 📋 | 标准摘要 | 一般视频（默认） |
| `academic` | 🎓 | 学术笔记 | 学术演讲、研究报告、学术会议 |
| `actions` | ✅ | 行动清单 | 教程、操作指南、步骤说明 |
| `news` | 📰 | 新闻速报 | 采访、时事评论、新闻报道 |
| `investment` | 📈 | 投资分析 | 财经、股市、加密货币、宏观经济 |
| `podcast` | 🎙️ | 播客速览 | 对话节目、访谈、脱口秀 |
| `eli5` | 🧒 | 深入浅出 | 科技、科学、复杂专业主题 |
| `bullets` | ⚡ | 极简子弹 | 快速浏览、会议记录、备忘 |

---

### CLI 参考

#### `kd process <url>`

完整流程：检测字幕 → 转录（如需）→ 生成摘要。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--language`, `-l` | 自动检测 | 语言代码：`zh`、`yue`（粤语）、`en`、`ja`、`ko`… |
| `--style`, `-s` | `standard` | 摘要风格（运行 `kd styles` 查看全部） |
| `--provider`, `-p` | `google` | AI 提供商：`google` \| `openai` \| `anthropic` |
| `--model`, `-m` | 提供商默认 | AI 模型名称（如 `gemini-2.5-flash`） |
| `--prompt` | — | 自定义摘要提示词（覆盖 `--style`） |
| `--output`, `-o` | 标准输出 | 输出文件路径 |
| `--format`, `-f` | `markdown` | 输出格式：`markdown` \| `json` \| `text` |
| `--no-subtitles` | false | 跳过字幕检测，强制使用 ASR |
| `--no-summary` | false | 纯转录模式，无需 AI，无需 API 密钥 |
| `--transcriber` | `qwen3-asr` | ASR 引擎：`qwen3-asr` \| `mlx-whisper` |
| `--model-size` | `1.7b` | Qwen3-ASR 模型大小：`1.7b`（高精度）\| `0.6b`（更快） |
| `--asr-prompt` | — | ASR 上下文提示（如方言特征、专业领域等） |

#### `kd styles`

列出所有内置摘要风格及其提示词。

#### `kd subtitles <url>`

仅提取字幕，不进行 ASR 或 AI 摘要。

#### `kd config set <key> <value>`

| Key | 示例 |
|-----|------|
| `api-key` | `AIzaSy...` |
| `provider` | `google`, `openai`, `anthropic` |
| `model` | `gemini-2.5-flash` |
| `language` | `zh` |
| `transcriber` | `qwen3-asr` |

---

### MCP 服务器配置（Open CLAW / Claude Code）

#### 推荐工作流程（龙虾自行摘要）

在 `~/.claude.json` 中添加：

```json
{
  "mcpServers": {
    "openclaw-knowledge-distiller": {
      "command": "kd",
      "args": ["mcp-server"]
    }
  }
}
```

> **无需配置 API 密钥！** 龙虾使用自身 AI 能力完成摘要。

#### MCP 工具说明

| 工具 | 说明 |
|------|------|
| `transcribe_url` ⭐ | **推荐**：返回转录文本和摘要提示词，由 Open CLAW 自行完成摘要 |
| `list_styles` | 获取所有摘要风格的完整提示词 |
| `process_url` | 完整流程（需配置外部 AI API 密钥） |
| `get_status` | 查询 process_url 任务进度 |
| `get_result` | 获取已完成任务的结果 |
| `list_jobs` | 列出所有任务 |

#### 典型 Open CLAW 工作流程

```
# 第一步：获取转录和提示词
龙虾 → transcribe_url(url="https://www.bilibili.com/video/BV...", style="investment", language="zh")
     ← {
          "transcript": "今天我们来聊一下...",
          "suggested_prompt": "你是一位资深投资分析师...",
          "transcript_source": "qwen3-asr"  // 或 "subtitles"
        }

# 第二步：龙虾用自己的 AI + suggested_prompt 生成结构化摘要
# 无需任何额外 API 调用，零额外成本
```

---

### 系统要求

- Python 3.11+
- macOS Apple 芯片（M1/M2/M3/M4）— Qwen3-ASR MLX 本地推理必需
- `ffmpeg`：`brew install ffmpeg`
- Qwen3-ASR 模型会在首次使用时**自动下载**（约 1-2 GB）

---

## Acknowledgements · 致謝

This project stands on the shoulders of remarkable open-source work. We are deeply grateful to the following teams and individuals:

| Project | Authors | Contribution |
|---------|---------|-------------|
| **[Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR)** | Alibaba Qwen Team 阿里巴巴 Qwen 團隊 | The core ASR model powering local transcription. World-class multilingual speech recognition including Cantonese, Mandarin, and 50+ languages. |
| **[Apple MLX](https://github.com/ml-explore/mlx)** | Apple Machine Learning Research | The on-device ML framework enabling Qwen3-ASR to run efficiently on Apple Silicon. |
| **[mlx-community](https://huggingface.co/mlx-community)** | MLX Community Contributors | Quantized MLX model weights hosted on Hugging Face, making local inference accessible. |
| **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** | yt-dlp contributors | Robust YouTube, Bilibili, and Facebook audio download and subtitle extraction without requiring any API key. |
| **[mlx-whisper](https://github.com/ml-explore/mlx-examples)** | Apple MLX Examples Team | Alternative Apple Silicon ASR backend using OpenAI's Whisper architecture. |
| **[Pydantic](https://github.com/pydantic/pydantic)** | Samuel Colvin & contributors | Data validation and modelling powering all internal data structures. |
| **[Typer](https://github.com/tiangolo/typer)** | Sebastián Ramírez (tiangolo) | The elegant CLI framework behind the `kd` command interface. |
| **[Rich](https://github.com/Textualize/rich)** | Will McGugan & Textualize | Beautiful terminal output, progress bars, and formatted tables. |
| **[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)** | Anthropic & MCP contributors | The Model Context Protocol SDK enabling Claude Code / Open CLAW agent integration. |
| **[httpx](https://github.com/encode/httpx)** | Tom Christie & encode | Async HTTP client powering AI provider API calls. |

---

特別感謝 **阿里巴巴 Qwen 團隊**開發並開源 Qwen3-ASR 模型，令本地、免費、高精度的粵語及多語言轉錄成為可能。同時感謝 **yt-dlp 團隊**提供強大的音頻下載同字幕提取功能，支援 YouTube、Bilibili 同 Facebook 影片。

Special thanks to the **Alibaba Qwen Team** for developing and open-sourcing the Qwen3-ASR model, making high-accuracy local speech recognition in Cantonese and 50+ languages possible without any cloud cost. Also grateful to the **yt-dlp community** for robust audio download and subtitle extraction supporting YouTube, Bilibili, and Facebook videos.

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

*Powered by [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR) · [yt-dlp](https://github.com/yt-dlp/yt-dlp) · [Apple MLX](https://github.com/ml-explore/mlx) · [MCP](https://github.com/modelcontextprotocol/python-sdk)*
