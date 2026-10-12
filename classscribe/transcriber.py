"""Local transcription with whisper.cpp (Metal-accelerated on Apple Silicon).

Converts any ffmpeg-readable audio/video to 16 kHz mono WAV, then runs the
whisper-cli binary to produce .txt / .srt / .vtt. Fully offline, no cost.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

WHISPER_BINARIES = ("whisper-cli", "whisper-cpp", "main")


class TranscribeError(RuntimeError):
    pass


def _whisper_binary() -> str:
    for name in WHISPER_BINARIES:
        if shutil.which(name):
            return name
    raise TranscribeError(
        "whisper.cpp not found (looked for: "
        f"{', '.join(WHISPER_BINARIES)}). Install it: `brew install whisper-cpp`."
    )


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise TranscribeError("'ffmpeg' not found on PATH. Install it and retry.")


def ensure_model(model_path: Path, model_url: str) -> Path:
    """Download the GGML model if it is not present yet."""
    if model_path.exists() and model_path.stat().st_size > 0:
        return model_path
    model_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading model (~1.5 GB) to {model_path} ...")

    def _hook(blocks: int, bsize: int, total: int) -> None:
        if total > 0:
            pct = min(100, blocks * bsize * 100 // total)
            print(f"\r  {pct:3d}%", end="", flush=True)

    tmp = model_path.with_suffix(model_path.suffix + ".part")
    urllib.request.urlretrieve(model_url, tmp, _hook)
    print()
    tmp.replace(model_path)
    return model_path


def transcribe(
    source: Path,
    out_base: Path,
    model_path: Path,
    language: str | None = None,
) -> dict[str, Path]:
    """Transcribe `source` into out_base.{txt,srt,vtt}. Returns the paths."""
    _require_ffmpeg()
    binary = _whisper_binary()

    if not source.is_file():
        raise TranscribeError(f"Input file not found: {source}")
    if not model_path.is_file():
        raise TranscribeError(f"Model not found: {model_path}")

    out_base.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        wav = Path(tmp.name)
        print("Preparing audio (16 kHz mono)...")
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(source), "-ac", "1", "-ar", "16000", "-vn", str(wav)],
            check=True,
        )

        cmd = [binary, "-m", str(model_path), "-f", str(wav),
               "-otxt", "-osrt", "-ovtt", "-of", str(out_base), "-pp"]
        if language:
            cmd += ["-l", language]
        print("Transcribing with whisper.cpp...")
        subprocess.run(cmd, check=True)

    return {
        "txt": out_base.with_suffix(".txt"),
        "srt": out_base.with_suffix(".srt"),
        "vtt": out_base.with_suffix(".vtt"),
    }
