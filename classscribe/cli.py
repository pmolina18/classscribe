"""ClassScribe CLI.

Commands:
  classscribe record [LABEL]        Record internal audio (Ctrl+C to stop).
  classscribe transcribe FILE       Transcribe an audio/video file.
  classscribe summarize TRANSCRIPT  Summarize an existing transcript.
  classscribe pipeline [LABEL]      record -> transcribe -> summarize.
  classscribe setup                 Download the local whisper model.
  classscribe config                Print the effective configuration.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import cloud_transcriber, recorder, summarizer, transcriber
from .config import (
    VALID_DIAGRAM_TYPES,
    VALID_TRANSCRIPTION_PROVIDERS,
    load_config,
)


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--workspace", help="Base folder for all outputs.")
    p.add_argument("--language", help="Transcription language code (e.g. es, en).")
    p.add_argument(
        "--transcription-provider", dest="transcription_provider",
        choices=VALID_TRANSCRIPTION_PROVIDERS,
        help="Transcription backend (default: groq).",
    )
    p.add_argument(
        "--diagram-type", dest="diagram_type",
        choices=VALID_DIAGRAM_TYPES,
        help="Mermaid diagram type (default: auto).",
    )


def _run_transcription(cfg, src: Path) -> dict:
    """Transcribe `src` using the configured provider. Returns output paths."""
    out_base = cfg.transcripts_dir / src.stem
    if cfg.transcription_provider == "local":
        model = transcriber.ensure_model(cfg.resolved_model_path(), cfg.model_url)
        return transcriber.transcribe(src, out_base, model, cfg.language)
    # Default provider: groq (cloud).
    return cloud_transcriber.transcribe_groq(
        src, out_base, cfg.llm_base_url, cfg.groq_whisper_model,
        cfg.llm_api_key(), cfg.language,
    )


def cmd_setup(args, cfg) -> int:
    cfg.ensure_dirs()
    path = transcriber.ensure_model(cfg.resolved_model_path(), cfg.model_url)
    print(f"Model ready: {path}")
    return 0


def cmd_config(args, cfg) -> int:
    eff = cfg.effective()
    width = max(len(k) for k in eff)
    print("Effective ClassScribe configuration:\n")
    for key, value in eff.items():
        print(f"  {key.ljust(width)}  {value}")
    return 0


def cmd_record(args, cfg) -> int:
    cfg.ensure_dirs()
    wav = recorder.record(cfg.recordings_dir, label=args.label,
                          duration=args.duration)
    print(f"\nRecorded: {wav}")
    return 0


def cmd_transcribe(args, cfg) -> int:
    cfg.ensure_dirs()
    src = Path(args.file).expanduser()
    outputs = _run_transcription(cfg, src)
    print(f"\nTranscript: {outputs['txt']}")
    return 0


def cmd_summarize(args, cfg) -> int:
    cfg.ensure_dirs()
    out = summarizer.summarize(
        Path(args.transcript).expanduser(), cfg.summaries_dir,
        cfg.llm_base_url, cfg.llm_model, cfg.llm_api_key(),
    )
    print(f"\nSummary: {out['summary']}\nOutline: {out['outline']}")
    return 0


def cmd_diagram(args, cfg) -> int:
    cfg.ensure_dirs()
    out = summarizer.diagram(
        Path(args.transcript).expanduser(), cfg.summaries_dir,
        cfg.llm_base_url, cfg.llm_model, cfg.llm_api_key(),
        diagram_type=cfg.diagram_type,
    )
    print(f"\nDiagram: {out['diagram']}")
    return 0


def cmd_pipeline(args, cfg) -> int:
    cfg.ensure_dirs()
    wav = recorder.record(cfg.recordings_dir, label=args.label,
                          duration=args.duration)
    outputs = _run_transcription(cfg, wav)
    summarizer.summarize(
        outputs["txt"], cfg.summaries_dir,
        cfg.llm_base_url, cfg.llm_model, cfg.llm_api_key(),
    )
    summarizer.diagram(
        outputs["txt"], cfg.summaries_dir,
        cfg.llm_base_url, cfg.llm_model, cfg.llm_api_key(),
        diagram_type=cfg.diagram_type,
    )
    print("\nDone: recording -> transcript -> summary + outline + diagram.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="classscribe", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("setup", help="Download the local whisper model.")
    _add_common(p); p.set_defaults(func=cmd_setup)

    p = sub.add_parser("config", help="Print the effective configuration.")
    _add_common(p); p.set_defaults(func=cmd_config)

    p = sub.add_parser("record", help="Record internal audio.")
    p.add_argument("label", nargs="?", help="Optional label for the file.")
    p.add_argument("--duration", default=None, metavar="DURATION",
                   help="Auto-stop after e.g. 90, 20s, 5m, 1h30m, or MM:SS "
                        "(omit for Ctrl+C).")
    _add_common(p); p.set_defaults(func=cmd_record)

    p = sub.add_parser("transcribe", help="Transcribe an audio/video file.")
    p.add_argument("file"); _add_common(p); p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("summarize", help="Summarize an existing transcript.")
    p.add_argument("transcript"); _add_common(p)
    p.set_defaults(func=cmd_summarize)

    p = sub.add_parser("diagram", help="Make a Mermaid diagram from a transcript.")
    p.add_argument("transcript"); _add_common(p)
    p.set_defaults(func=cmd_diagram)

    p = sub.add_parser("pipeline", help="record -> transcribe -> summarize.")
    p.add_argument("label", nargs="?")
    p.add_argument("--duration", default=None, metavar="DURATION",
                   help="Auto-stop recording after e.g. 90, 20s, 5m, 1h30m, "
                        "or 45:00 (omit for Ctrl+C).")
    _add_common(p); p.set_defaults(func=cmd_pipeline)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(
            workspace=getattr(args, "workspace", None),
            language=getattr(args, "language", None),
            transcription_provider=getattr(args, "transcription_provider", None),
            diagram_type=getattr(args, "diagram_type", None),
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    try:
        return args.func(args, cfg)
    except (recorder.RecordError, transcriber.TranscribeError,
            summarizer.SummaryError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
