# Reddit Post — Open CLAW Subreddit

## 標題
> Built an MCP skill for Open CLAW: paste a YouTube/Bilibili URL, your agent reads it for you — because opportunity cost is real

---

## 正文

There's more worth watching than ever — interviews with practitioners, AI research breakdowns, founder podcasts, conference talks. The signal density is genuinely high. But so is the opportunity cost of sitting through a 90-minute episode to extract 10 minutes of actual insight.

On top of that, every two months there's a new frontier model to evaluate, new APIs to test, new patterns to vibe code into your workflow. The backlog of "things I should watch" grows faster than I can clear it.

So I built **Open CLAW Knowledge Distiller** (`kd`) — an MCP server that gives your Open CLAW agent the ability to process YouTube and Bilibili videos directly, so you can route the cognitive work to your agent instead of your calendar.

**How it's designed**

The core idea: *your Open CLAW agent is the AI — `kd` just handles what it can't do itself.*

When your agent calls `transcribe_url`:

1. `kd` checks for existing subtitles → extracts them directly if available (fast path)
2. If no subtitles → downloads audio and transcribes locally using **Qwen3-ASR MLX** on Apple Silicon — no API key, no cloud, runs entirely on your machine
3. Returns the raw transcript + a ready-to-use system prompt for your chosen summarization style

Your Open CLAW agent then does the actual summarization using its own intelligence. `kd` never calls an external AI API — it's purely the transcription pipeline.

**Install and connect**

```bash
brew install ffmpeg
pip install openclaw-knowledge-distiller
```

Add to your Open CLAW MCP config:

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

Once connected, your agent gets access to `transcribe_url` and `list_styles`. From there it can handle video URLs as naturally as any other input.

**8 summarization styles your agent can choose from**

`standard` · `academic` · `actions` · `news` · `investment` · `podcast` · `eli5` · `bullets`

Each style ships with a full system prompt that gets passed back to your agent — so it knows exactly how to structure its output. Run `kd styles` to see them all, or pass a fully custom prompt.

**What's been tested**

- ✅ Subtitle extraction (skips ASR entirely when subtitles exist)
- ✅ End-to-end `process` pipeline
- ✅ MCP stdio handshake working
- ✅ 50+ languages including Cantonese

The ASR path auto-downloads the Qwen3-ASR model (~1-2 GB) on first use. Requires Apple Silicon (M1 and above).

**Links**

- GitHub: https://github.com/destinyfrancis/openclaw-knowledge-distiller
- PyPI: `pip install openclaw-knowledge-distiller`

Open to feedback — especially from anyone building research or knowledge management workflows on top of Open CLAW.
