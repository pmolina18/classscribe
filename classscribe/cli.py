"""ClassScribe CLI.

Commands:
  classscribe record [LABEL]        Record internal audio (Ctrl+C to stop),
                                    then transcribe and summarize it.
  classscribe transcribe FILE       Transcribe an audio/video file.
  classscribe summarize TRANSCRIPT  Summarize an existing transcript.
  classscribe pipeline [LABEL]      record -> transcribe -> summarize.
  classscribe setup                 Download the whisper model.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import recorder, summarizer, transcriber
from .config import load_config


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--workspace", help="Base folder for all outputs.")
    p.add_argument("--language", help="Whisper language code (e.g. es, en).")


def cmd_setup(args, cfg) -> int:
    cfg.ensure_dirs()
    path = transcriber.ensure_model(cfg.resolved_model_path(), cfg.model_url)
    print(f"Model ready: {path}")
    return 0


def cmd_record(args, cfg) -> int:
    cfg.ensure_dirs()
    wav = recorder.record(cfg.recordings_dir, label=args.label)
    print(f"\nRecorded: {wav}")
    return 0


def cmd_transcribe(args, cfg) -> int:
    cfg.ensure_dirs()
    model = transcriber.ensure_model(cfg.resolved_model_path(), cfg.model_url)
    src = Path(args.file).expanduser()
    out_base = cfg.transcripts_dir / src.stem
    outputs = transcriber.transcribe(src, out_base, model, cfg.language)
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


def cmd_pipeline(args, cfg) -> int:
    cfg.ensure_dirs()
    model = transcriber.ensure_model(cfg.resolved_model_path(), cfg.model_url)
    wav = recorder.record(cfg.recordings_dir, label=args.label)
    out_base = cfg.transcripts_dir / wav.stem
    outputs = transcriber.transcribe(wav, out_base, model, cfg.language)
    summarizer.summarize(
        outputs["txt"], cfg.summaries_dir,
        cfg.llm_base_url, cfg.llm_model, cfg.llm_api_key(),
    )
    print("\nDone: recording -> transcript -> summary + outline.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="classscribe", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("setup", help="Download the whisper model.")
    _add_common(p); p.set_defaults(func=cmd_setup)

    p = sub.add_parser("record", help="Record internal audio.")
    p.add_argument("label", nargs="?", help="Optional label for the file.")
    _add_common(p); p.set_defaults(func=cmd_record)

    p = sub.add_parser("transcribe", help="Transcribe an audio/video file.")
    p.add_argument("file"); _add_common(p); p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("summarize", help="Summarize an existing transcript.")
    p.add_argument("transcript"); _add_common(p)
    p.set_defaults(func=cmd_summarize)

    p = sub.add_parser("pipeline", help="record -> transcribe -> summarize.")
    p.add_argument("label", nargs="?")
    _add_common(p); p.set_defaults(func=cmd_pipeline)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(workspace=getattr(args, "workspace", None),
                      language=getattr(args, "language", None))
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
