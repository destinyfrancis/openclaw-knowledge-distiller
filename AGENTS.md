# Open CLAW Knowledge Distiller

開源 Python CLI + MCP Server，將 YouTube / Bilibili / Facebook 影片自動轉化為結構化知識文章。
供 Codex / Open CLAW 龍蝦 agent 調用。

**GitHub**: https://github.com/destinyfrancis/openclaw-knowledge-distiller
**PyPI name**: `openclaw-knowledge-distiller`
**CLI command**: `kd`
**最後更新**: 2026-03-10

---

## 項目結構

```
knowledge-distiller/
├── pyproject.toml                         # uv/pip 項目配置，name = "openclaw-knowledge-distiller"
├── README.md                              # 三語 README (English · 繁體中文 · 简体中文)
└── src/
    └── knowledge_distiller/
        ├── __init__.py
        ├── cli.py                         # CLI 入口 (typer)：process, styles, subtitles, config, mcp-server
        ├── mcp_server.py                  # MCP Server (stdio)：transcribe_url, process_url, list_styles, get_status, get_result, list_jobs, configure
        ├── downloader.py                  # yt-dlp wrapper：fetch_metadata(), download_audio()
        ├── subtitle_extractor.py          # 字幕提取：extract_subtitles()
        ├── transcriber.py                 # ASR 轉錄：transcribe()，支援 qwen3-asr / mlx-whisper
        ├── summarizer.py                  # 摘要生成：generate_summary()，PROMPT_STYLES registry
        ├── providers.py                   # AI provider 抽象：GoogleProvider / OpenAIProvider / AnthropicProvider
        ├── models.py                      # Pydantic 數據模型：VideoMetadata, ArticleSummary, ProcessingStatus
        └── config.py                      # 配置管理：~/.config/knowledge-distiller/config.toml + keyring
```

---

## 核心架構設計

### Agent-first 設計原則

**`kd` 只負責轉錄，AI（龍蝦）負責摘要。**

```
Agent (Open CLAW / Codex)
  → transcribe_url(url, style="investment")
  ← { transcript: "...", suggested_prompt: "<full system prompt>", instructions: "..." }
  → Agent summarizes using its OWN AI (no external API key needed from kd)
```

- MCP Server 推薦工具：`transcribe_url`（返回文字稿 + 摘要 prompt，agent 自行做摘要）
- `process_url` 保留供需要外部 AI API 嘅場景

### 轉錄流程

```
URL → fetch_metadata() → has_subtitles?
  ├─ YES → extract_subtitles() → transcript（快）
  └─ NO  → download_audio() → transcriber.transcribe() → transcript（用本地 Qwen3-ASR）
```

---

## 8 種摘要風格（PROMPT_STYLES registry）

| Key | 名稱 | 適合場景 |
|-----|------|---------|
| `standard` | 標準摘要 | 一般影片（預設） |
| `academic` | 學術筆記 | 演講、論文討論 |
| `actions` | 行動清單 | 教學、How-to |
| `news` | 新聞速報 | 時事、訪談 |
| `investment` | 投資分析 | 財經、投資 |
| `podcast` | 播客速覽 | 對話、播客 |
| `eli5` | 小學生都明 | 科技、科學 |
| `bullets` | 子彈筆記 | 快速瀏覽 |

---

## CLI 常用指令

```bash
# 安裝
pip install openclaw-knowledge-distiller
# 或開發模式
uv sync && uv pip install -e .

# 基本用法（需要 AI API key 做摘要）
kd process "https://youtube.com/watch?v=xxx" --language zh
kd process "https://youtube.com/watch?v=xxx" --style investment
kd process "https://bilibili.com/video/BVxxx" --language yue --asr-prompt "粵語口語"

# 只轉錄，不摘要（唔需要 API key）
kd process "https://youtube.com/watch?v=xxx" --no-summary

# 列出所有摘要風格
kd styles

# 配置
kd config set provider google
kd config set api-key "AIza..."
kd config get

# 啟動 MCP Server
kd mcp-server
```

---

## MCP Server 工具

| 工具 | 推薦對象 | 說明 |
|------|---------|------|
| `transcribe_url` | Open CLAW / Codex agent | 返回文字稿 + suggested_prompt，agent 自己做摘要 |
| `process_url` | 外部 AI API 場景 | kd 直接調用 AI API 做完整摘要 |
| `list_styles` | - | 返回所有風格 key、名稱、description、完整 system_prompt |
| `get_status` | - | 查詢 job 進度 |
| `get_result` | - | 取得摘要結果 |
| `list_jobs` | - | 列出所有任務 |
| `configure` | - | 更新配置 |

### Codex MCP 配置（`~/.Codex.json`）

```json
{
  "mcpServers": {
    "knowledge-distiller": {
      "command": "kd",
      "args": ["mcp-server"]
    }
  }
}
```

---

## 開發指令

```bash
# 安裝依賴（開發模式）
uv sync
uv pip install -e .

# 執行測試
uv run python -m pytest
# 或
python3 -m pytest

# Lint
uv run ruff check src/
uv run ruff format src/
```

---

## 依賴說明

| 依賴 | 用途 |
|------|------|
| `yt-dlp` | 下載 YouTube / Bilibili / Facebook 音頻和字幕 |
| `qwen-asr` | 本地 Qwen3-ASR MLX 轉錄（Apple Silicon） |
| `mcp` | MCP stdio server |
| `typer` + `rich` | CLI 介面 |
| `httpx` | AI API HTTP 請求 |
| `pydantic` | 數據模型驗證 |
| `keyring` | API key 安全儲存 |
| `mlx-whisper` | 可選：Whisper ASR backend（`--transcriber mlx-whisper`） |

**系統需求**：macOS，Apple Silicon，`ffmpeg`（`brew install ffmpeg`）

---

## 版本歷史

### v0.1.0（2026-03-10）
- 初始版本：CLI + MCP Server
- 8 種摘要風格（PROMPT_STYLES registry）
- Agent-first 架構：`transcribe_url` 工具，agent 自行做摘要
- `list_styles` 工具返回完整 system_prompt
- 三語 README（English · 繁體中文 · 简体中文）
- GitHub: https://github.com/destinyfrancis/openclaw-knowledge-distiller
