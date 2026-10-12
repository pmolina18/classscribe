"""Internal-audio recording via BlackHole + ffmpeg (macOS).

Captures whatever is playing on the Mac (a lecture video, a call, a podcast)
by reading the BlackHole virtual audio device through ffmpeg's avfoundation
input. Produces a 16 kHz mono WAV, the ideal input for whisper.cpp.

For capture to work the Mac's audio OUTPUT must be routed to BlackHole (or to
a Multi-Output Device that includes it); otherwise it records silence.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

AVF_DEVICE_RE = re.compile(r"\]\s*\[(\d+)\]\s*(.+)$")


class RecordError(RuntimeError):
    pass


def _require(binary: str) -> None:
    if shutil.which(binary) is None:
        raise RecordError(
            f"'{binary}' not found on PATH. Install it (see README) and retry."
        )


def find_blackhole_index(name_hint: str = "blackhole") -> int:
    """Return the avfoundation audio-device index for BlackHole."""
    _require("ffmpeg")
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "avfoundation",
         "-list_devices", "true", "-i", ""],
        capture_output=True, text=True,
    )
    # ffmpeg prints the device list to stderr.
    in_audio = False
    for line in proc.stderr.splitlines():
        low = line.lower()
        if "audio devices" in low:
            in_audio = True
            continue
        if in_audio:
            m = AVF_DEVICE_RE.search(line)
            if m and name_hint.lower() in m.group(2).lower():
                return int(m.group(1))
    raise RecordError(
        f"Could not find a '{name_hint}' audio device. Is BlackHole installed "
        "and is the system output routed through it?"
    )


def record(
    out_dir: Path,
    label: str | None = None,
    device_index: int | None = None,
) -> Path:
    """Record internal audio until Ctrl+C. Returns the WAV path.

    ffmpeg exits non-zero on SIGINT; that is expected and not an error.
    """
    _require("ffmpeg")
    out_dir.mkdir(parents=True, exist_ok=True)

    idx = device_index if device_index is not None else find_blackhole_index()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = f"{label}-{stamp}" if label else stamp
    out = out_dir / f"{base}.wav"

    print(f"Recording internal audio (BlackHole index {idx}).")
    print(f"Output: {out}")
    print("Press Ctrl+C to stop.\n", flush=True)

    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-stats",
             "-f", "avfoundation", "-i", f":{idx}",
             "-ac", "1", "-ar", "16000", str(out)],
            check=False,
        )
    except KeyboardInterrupt:
        pass

    if not out.exists() or out.stat().st_size == 0:
        raise RecordError(
            "No audio captured (empty file). Was the system output set to the "
            "Multi-Output Device that includes BlackHole?"
        )

    print(f"\nSaved recording: {out}", file=sys.stderr)
    return out
