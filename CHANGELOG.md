# Changelog

## v0.1.0 (2026-10-12)

First public release.

### Features

- `classscribe record`: captures your Mac's internal audio through BlackHole.
  `--duration` accepts `90`, `20s`, `5m`, `1h30m`, `45:00` or `1:30:00`; leave
  it out to stop with Ctrl+C.
- `classscribe transcribe`: two backends.
  - `groq` (default): Groq's hosted Whisper (`whisper-large-v3-turbo`). Audio
    is compressed to 32 kbps mono AAC before upload, so the 100 MB free-tier
    limit covers about 7 hours.
  - `local`: whisper.cpp, fully offline (`classscribe setup` downloads the
    model).
  Both write `.txt`, `.srt` and `.vtt`.
- `classscribe summarize`: writes a study summary and a hierarchical outline.
- `classscribe diagram`: writes a Mermaid diagram (`mindmap`, `timeline`,
  `flowchart` or `auto`) that renders on GitHub.
- `classscribe pipeline`: record, transcribe, summarize and diagram in one
  command.
- `classscribe config`: prints the settings in effect, without showing the key.
- Configuration through flags, environment variables or `.classscribe.toml`.
- Works with any OpenAI-compatible LLM endpoint, including Ollama for fully
  local notes.

### Notes

- No Python dependencies; ffmpeg is required, and whisper.cpp only for the
  `local` backend.
- CI runs ruff and pytest on Python 3.11 and 3.12.
