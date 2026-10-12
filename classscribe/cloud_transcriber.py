"""Cloud transcription via Groq's OpenAI-compatible Whisper endpoint.

Uploads audio to `POST {base_url}/audio/transcriptions` with
`response_format=verbose_json`, then builds .txt / .srt / .vtt from the
returned segments — matching the local whisper.cpp backend's outputs.

No third-party SDK: the multipart/form-data body is assembled by hand with
urllib, keeping dependencies at zero. Groq free tier allows files up to 100 MB.
"""
from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .transcriber import TranscribeError

# Groq's documented hard cap for the free/dev tier (per console.groq.com/docs).
GROQ_MAX_FILE_BYTES = 100 * 1024 * 1024


def _version() -> str:
    try:
        from . import __version__
        return __version__
    except Exception:
        return "0"


def _fmt_timestamp(seconds: float, sep: str) -> str:
    """Format seconds as HH:MM:SS<sep>mmm (sep is ',' for SRT, '.' for VTT)."""
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def _build_srt(segments: list[dict]) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _fmt_timestamp(float(seg.get("start", 0.0)), ",")
        end = _fmt_timestamp(float(seg.get("end", 0.0)), ",")
        text = str(seg.get("text", "")).strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def _build_vtt(segments: list[dict]) -> str:
    out = ["WEBVTT\n"]
    for seg in segments:
        start = _fmt_timestamp(float(seg.get("start", 0.0)), ".")
        end = _fmt_timestamp(float(seg.get("end", 0.0)), ".")
        text = str(seg.get("text", "")).strip()
        out.append(f"{start} --> {end}\n{text}\n")
    return "\n".join(out)


def _multipart_body(
    file_path: Path, fields: dict[str, str],
) -> tuple[bytes, str]:
    """Assemble a multipart/form-data body. Returns (body, content_type)."""
    boundary = f"----classscribe{uuid.uuid4().hex}"
    crlf = b"\r\n"
    parts: list[bytes] = []

    for name, value in fields.items():
        parts.append(f"--{boundary}".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{name}"'.encode())
        parts.append(b"")
        parts.append(value.encode("utf-8"))

    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    parts.append(f"--{boundary}".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; '
        f'filename="{file_path.name}"'.encode()
    )
    parts.append(f"Content-Type: {mime}".encode())
    parts.append(b"")
    parts.append(file_path.read_bytes())

    parts.append(f"--{boundary}--".encode())
    parts.append(b"")

    body = crlf.join(parts)
    return body, f"multipart/form-data; boundary={boundary}"


def transcribe_groq(
    source: Path,
    out_base: Path,
    base_url: str,
    model: str,
    api_key: str | None,
    language: str | None = None,
) -> dict[str, Path]:
    """Transcribe `source` via Groq into out_base.{txt,srt,vtt}."""
    if not source.is_file():
        raise TranscribeError(f"Input file not found: {source}")
    if not api_key:
        raise TranscribeError(
            "No API key for cloud transcription. Set GROQ_API_KEY (or the "
            "configured key env var), or use --transcription-provider local."
        )

    size = source.stat().st_size
    if size > GROQ_MAX_FILE_BYTES:
        mb = size / (1024 * 1024)
        raise TranscribeError(
            f"File is {mb:.0f} MB, over Groq's 100 MB limit. Compress/segment "
            "it, or use --transcription-provider local (no size limit)."
        )

    out_base.parent.mkdir(parents=True, exist_ok=True)

    fields = {"model": model, "response_format": "verbose_json"}
    if language:
        fields["language"] = language

    body, content_type = _multipart_body(source, fields)
    url = base_url.rstrip("/") + "/audio/transcriptions"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", content_type)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", f"classscribe/{_version()}")
    req.add_header("Authorization", f"Bearer {api_key}")

    print(f"Transcribing with Groq ({model})...")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        if e.code == 413:
            raise TranscribeError(
                "Groq rejected the file as too large (413). Segment it or use "
                "--transcription-provider local."
            ) from e
        if e.code == 429:
            raise TranscribeError(
                "Groq rate limit hit (429). Wait a moment and retry, or use "
                "--transcription-provider local."
            ) from e
        if e.code == 404 and "model_not_found" in detail:
            raise TranscribeError(
                f"Transcription model '{model}' not available on your tier. "
                "Pick a current one from console.groq.com/docs/models "
                "(e.g. whisper-large-v3-turbo) via [transcription] groq_model."
            ) from e
        raise TranscribeError(f"Groq transcription error {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise TranscribeError(f"Could not reach Groq at {url}: {e.reason}") from e

    text = str(data.get("text", "")).strip()
    segments = data.get("segments") or []

    txt_path = out_base.with_suffix(".txt")
    srt_path = out_base.with_suffix(".srt")
    vtt_path = out_base.with_suffix(".vtt")
    txt_path.write_text(text + "\n", encoding="utf-8")
    # Segments power timestamps; if absent, fall back to a single cue.
    if not segments and text:
        segments = [{"start": 0.0, "end": 0.0, "text": text}]
    srt_path.write_text(_build_srt(segments), encoding="utf-8")
    vtt_path.write_text(_build_vtt(segments), encoding="utf-8")

    return {"txt": txt_path, "srt": srt_path, "vtt": vtt_path}
