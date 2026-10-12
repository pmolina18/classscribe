# ClassScribe

**Turn any audio playing on your Mac into study notes — fully local transcription, free AI summaries.**

ClassScribe captures the internal audio of your Mac (a lecture video, a recorded
call, a podcast), transcribes it **locally and offline** with
[whisper.cpp](https://github.com/ggerganov/whisper.cpp) (Metal-accelerated on
Apple Silicon), and generates a study **summary** and **outline** with a free
LLM. No subscriptions, no uploads of your audio — the transcription never leaves
your machine.

```
┌───────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────────┐
│  System   │ ──▶ │  BlackHole   │ ──▶ │  whisper.cpp  │ ──▶ │  LLM (Groq free) │
│  audio    │     │ (virtual mic)│     │  local, Metal │     │  summary+outline │
└───────────┘     └──────────────┘     └───────────────┘     └──────────────────┘
     play a lecture      ffmpeg capture      .txt/.srt/.vtt        .md study notes
```

## Why

I built this to study for my university degree: record each video lecture, get a
faithful transcript, and have an LLM turn it into a revision summary and a
hierarchical outline — all automatically, all free. It works for any audio your
Mac can play.

## Features

- 🎙️ **Capture internal audio** on macOS via BlackHole (what you *hear*, cleanly, no microphone).
- 📝 **Local transcription** with whisper.cpp + `large-v3-turbo` — offline, private, GPU-accelerated.
- 🧠 **Free AI summaries** via [Groq Cloud](https://console.groq.com) (free tier), or any OpenAI-compatible endpoint — including **Ollama** for 100% local, private summaries.
- 🧩 **Outputs**: `.txt`, `.srt`, `.vtt` transcripts + `-summary.md` and `-outline.md`.
- 🛠️ **One command**: `classscribe pipeline` records → transcribes → summarizes.

## Requirements (all free)

| Tool | Install | Purpose |
|------|---------|---------|
| [BlackHole 2ch](https://existential.audio/blackhole/) | `brew install blackhole-2ch` | Capture internal audio |
| [ffmpeg](https://ffmpeg.org) | `brew install ffmpeg` | Audio I/O |
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | `brew install whisper-cpp` | Local transcription |
| Python ≥ 3.11 | `brew install python` | Runs ClassScribe |
| A free [Groq API key](https://console.groq.com/keys) | — | AI summaries (optional) |

> **macOS only** for recording (BlackHole + avfoundation). Transcription and
> summarization work anywhere whisper.cpp runs.

## Install

```bash
git clone https://github.com/pmolina18/classscribe.git
cd classscribe
pip install -e .
```

Download the whisper model (~1.5 GB, one time):

```bash
classscribe setup
```

## Audio routing (one-time macOS setup)

To capture what you hear *and* keep hearing it, create a **Multi-Output Device**:

1. Open **Audio MIDI Setup**.
2. Click **+** (bottom-left) → **Create Multi-Output Device**.
3. Check both **BlackHole 2ch** and your speakers/headphones.
4. Enable **Drift Correction** on BlackHole.
5. Before recording, set system output (🔊 menu) to that Multi-Output Device.

## Configure the LLM

Get a free key at [console.groq.com/keys](https://console.groq.com/keys), then:

```bash
export GROQ_API_KEY="gsk_..."
```

Prefer **fully local** summaries? Run [Ollama](https://ollama.com) and point the
config at it — see `.classscribe.toml.example`. No API key, nothing leaves your Mac.

## Usage

**All in one** (record → transcribe → summarize):

```bash
classscribe pipeline my-lecture
# plays? press Ctrl+C to stop → transcript + summary appear automatically
```

**Step by step:**

```bash
classscribe record my-lecture        # Ctrl+C to stop
classscribe transcribe ~/ClassScribe/recordings/my-lecture-*.wav
classscribe summarize ~/ClassScribe/transcripts/my-lecture-*.txt
```

**Transcribe a file you already have** (no recording needed):

```bash
classscribe transcribe ~/Downloads/lecture.mp4 --language es
```

Outputs land in `~/ClassScribe/{recordings,transcripts,summaries}/` (configurable).

## Configuration

Copy `.classscribe.toml.example` to `.classscribe.toml` and edit, or use flags
(`--workspace`, `--language`) / env vars (`CLASSSCRIBE_WORKSPACE`,
`CLASSSCRIBE_LANGUAGE`, `GROQ_API_KEY`).

## Privacy & cost

- **Audio & transcription stay on your Mac.** whisper.cpp is fully offline.
- **Summaries** send the *transcript text* to the LLM endpoint you choose. With
  Groq that's a free-tier cloud call; with Ollama it stays local.
- Groq's free tier has rate limits (fine for class notes). No credit card.

## License

MIT — see [LICENSE](LICENSE).
