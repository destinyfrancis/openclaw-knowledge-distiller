"""ASR transcription backends: Qwen3-ASR MLX (primary), mlx-whisper (secondary)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Callable

# Supported Qwen3-ASR model sizes (matched to qwen3-asr-swift / mlx-community)
QWEN3_MODELS = {
    "1.7b": "mlx-community/Qwen3-ASR-1.7B-8bit",
    "0.6b": "mlx-community/Qwen3-ASR-0.6B-4bit",
}

WHISPER_MODELS = {
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "base": "mlx-community/whisper-base-mlx",
}


def transcribe(
    audio_path: Path,
    language: str | None = None,
    backend: str = "qwen3-asr",
    model_size: str = "1.7b",
    custom_prompt: str = "",
    progress_callback: Callable[[float, str], None] | None = None,
) -> str:
    """
    Transcribe audio file to text.

    Args:
        audio_path: Path to audio file (MP3/WAV/M4A etc.)
        language: ISO-639-1 or Qwen3-ASR language code (e.g. "zh", "yue", "en"),
                  or None for auto-detect
        backend: "qwen3-asr" (default, Apple Silicon), "mlx-whisper"
        model_size: For qwen3-asr: "1.7b" or "0.6b"; for whisper: "large-v3", "small", "base"
        custom_prompt: Custom context hint for Qwen3-ASR transcription
        progress_callback: Called with (progress 0.0-1.0, phase_message)

    Returns:
        Transcribed text string.

    Notes:
        - Neither backend requires an API key — all inference is local on Apple Silicon.
        - Qwen3-ASR supports Cantonese ("yue"), Mandarin ("zh"), 50+ other languages.
        - mlx-whisper supports general multilingual transcription.
    """
    if backend == "qwen3-asr":
        return _transcribe_qwen3_mlx(audio_path, language, model_size, custom_prompt, progress_callback)
    elif backend == "mlx-whisper":
        return _transcribe_mlx_whisper(audio_path, language, model_size, progress_callback)
    else:
        raise ValueError(f"Unknown transcription backend: {backend!r}. Choose: qwen3-asr, mlx-whisper")


# ─── Qwen3-ASR MLX (primary, no API key needed) ───────────────────────────────

def _transcribe_qwen3_mlx(
    audio_path: Path,
    language: str | None,
    model_size: str,
    custom_prompt: str,
    progress_callback: Callable[[float, str], None] | None,
) -> str:
    """
    Transcribe via Qwen3-ASR using the qwen-asr Python package.
    Model is downloaded once to ~/Library/Caches/qwen3-speech/ (or HF cache).
    No API key required.
    """
    try:
        from qwen_asr import Qwen3ASRModel  # type: ignore[import]
    except ImportError as e:
        raise RuntimeError(
            "qwen3-asr not installed.\n"
            "Install: pip install qwen-asr\n"
            "Or with uv: uv add qwen-asr"
        ) from e

    model_id = QWEN3_MODELS.get(model_size.lower(), QWEN3_MODELS["1.7b"])

    if progress_callback:
        progress_callback(0.05, f"Loading Qwen3-ASR {model_size.upper()} model...")

    model = Qwen3ASRModel.from_pretrained(model_id)

    if progress_callback:
        progress_callback(0.3, "Transcribing with Qwen3-ASR...")

    lang_code = language or "auto"
    results = model.transcribe(
        audio=str(audio_path),
        language=lang_code,
        context=custom_prompt,
    )

    if progress_callback:
        progress_callback(1.0, "Transcription complete")

    # results is List[ASRTranscription]; each has .text attribute
    if not results:
        return ""
    return results[0].text.strip()


def _transcribe_qwen3_mlx_chunked(
    audio_path: Path,
    language: str | None,
    model_size: str,
    custom_prompt: str,
    chunk_seconds: int = 60,
    progress_callback: Callable[[float, str], None] | None = None,
) -> str:
    """
    Chunk-based Qwen3-ASR transcription for audio > 90s.
    Uses ffmpeg to split audio into overlapping chunks.
    """
    try:
        from qwen_asr import Qwen3ASRModel  # type: ignore[import]
    except ImportError as e:
        raise RuntimeError("qwen3-asr not installed. Run: pip install qwen-asr") from e

    model_id = QWEN3_MODELS.get(model_size.lower(), QWEN3_MODELS["1.7b"])

    if progress_callback:
        progress_callback(0.05, "Loading Qwen3-ASR model...")
    model = Qwen3ASRModel.from_pretrained(model_id)

    # Get duration
    duration = _get_audio_duration(audio_path)
    if duration is None or duration <= chunk_seconds:
        # Short audio: single pass
        return _transcribe_qwen3_mlx(audio_path, language, model_size, custom_prompt, progress_callback)

    # Split into chunks
    overlap = 6  # seconds of overlap between chunks
    chunks: list[tuple[float, Path]] = []
    start = 0.0
    with tempfile.TemporaryDirectory(prefix="kd_chunks_") as tmp_dir:
        chunk_dir = Path(tmp_dir)
        while start < duration:
            end = min(start + chunk_seconds, duration)
            chunk_path = chunk_dir / f"chunk_{int(start):05d}.wav"
            _extract_chunk(audio_path, chunk_path, start, end)
            chunks.append((start, chunk_path))
            if end >= duration:
                break
            start += chunk_seconds - overlap

        texts: list[str] = []
        for i, (offset, chunk_path) in enumerate(chunks):
            if progress_callback:
                progress_callback(0.1 + 0.8 * i / len(chunks), f"Chunk {i+1}/{len(chunks)}...")

            lang_code = language or "auto"
            results = model.transcribe(audio=str(chunk_path), language=lang_code, context=custom_prompt)
            chunk_text = results[0].text.strip() if results else ""
            texts.append(chunk_text)

    if progress_callback:
        progress_callback(1.0, "Transcription complete")

    return "\n".join(t for t in texts if t)


def _get_audio_duration(path: Path) -> float | None:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        import json
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return None


def _extract_chunk(src: Path, dest: Path, start: float, end: float) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ss", str(start), "-to", str(end),
         "-ar", "16000", "-ac", "1", "-f", "wav", str(dest)],
        capture_output=True, timeout=120,
    )


# ─── mlx-whisper (fallback, no API key needed) ────────────────────────────────

def _transcribe_mlx_whisper(
    audio_path: Path,
    language: str | None,
    model_size: str,
    progress_callback: Callable[[float, str], None] | None,
) -> str:
    """
    Transcribe via mlx-whisper on Apple Silicon.
    No API key required.
    """
    try:
        import mlx_whisper
    except ImportError as e:
        raise RuntimeError(
            "mlx-whisper not installed.\n"
            "Install: pip install mlx-whisper\n"
            "Or: uv add mlx-whisper"
        ) from e

    model_id = WHISPER_MODELS.get(model_size, WHISPER_MODELS["large-v3"])

    if progress_callback:
        progress_callback(0.0, f"Loading Whisper {model_size} model...")

    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=model_id,
        language=language,
        verbose=False,
    )

    if progress_callback:
        progress_callback(1.0, "Transcription complete")

    return result.get("text", "").strip()


# ─── Utilities ────────────────────────────────────────────────────────────────

def available_backends() -> list[str]:
    """Return list of available transcription backends on this system."""
    backends = []
    try:
        import qwen_asr  # noqa: F401
        backends.append("qwen3-asr")
    except ImportError:
        pass
    try:
        import mlx_whisper  # noqa: F401
        backends.append("mlx-whisper")
    except ImportError:
        pass
    return backends


def default_backend() -> str:
    """Pick best available backend."""
    backends = available_backends()
    if backends:
        return backends[0]
    raise RuntimeError(
        "No transcription backend available.\n"
        "Install Qwen3-ASR: pip install qwen-asr\n"
        "Install mlx-whisper: pip install mlx-whisper"
    )
