"""LLM summaries via any OpenAI-compatible chat endpoint.

Defaults to Groq Cloud's free tier. Point `base_url`/`model` at Ollama
(http://localhost:11434/v1) for a fully local, private alternative.

No third-party SDK required: a single POST with urllib keeps dependencies at
zero and makes the integration easy to read on a portfolio.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

SUMMARY_SYSTEM = (
    "You are a study assistant. Given a raw lecture transcript, produce clear, "
    "faithful study material. Never invent facts not supported by the "
    "transcript. Write in the same language as the transcript."
)

SUMMARY_PROMPT = """\
Here is a lecture transcript. Produce a study SUMMARY in Markdown with:
- A short overview (2-3 sentences).
- Key points (bullets).
- Important concepts and their definitions.
- A short glossary of terms.

Transcript:
---
{transcript}
---
"""

OUTLINE_PROMPT = """\
Here is a lecture transcript. Produce a hierarchical OUTLINE in Markdown
(nested bullets) suitable for quick revision. Be faithful to the transcript;
do not invent content.

Transcript:
---
{transcript}
---
"""


class SummaryError(RuntimeError):
    pass


def _chat(base_url: str, model: str, api_key: str, system: str, user: str) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise SummaryError(f"LLM API error {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise SummaryError(f"Could not reach LLM endpoint {url}: {e.reason}") from e

    try:
        return body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise SummaryError(f"Unexpected LLM response shape: {body}") from e


def summarize(
    transcript_path: Path,
    out_dir: Path,
    base_url: str,
    model: str,
    api_key: str | None,
) -> dict[str, Path]:
    """Generate <name>-summary.md and <name>-outline.md from a transcript."""
    if not transcript_path.is_file():
        raise SummaryError(f"Transcript not found: {transcript_path}")
    if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
        raise SummaryError(
            "No LLM API key found. Set the key env var (default GROQ_API_KEY), "
            "or point base_url at a local Ollama endpoint."
        )

    text = transcript_path.read_text(encoding="utf-8").strip()
    if not text:
        raise SummaryError(f"Transcript is empty: {transcript_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = transcript_path.stem

    print("Generating summary...")
    summary = _chat(base_url, model, api_key or "", SUMMARY_SYSTEM,
                    SUMMARY_PROMPT.format(transcript=text))
    print("Generating outline...")
    outline = _chat(base_url, model, api_key or "", SUMMARY_SYSTEM,
                    OUTLINE_PROMPT.format(transcript=text))

    summary_path = out_dir / f"{stem}-summary.md"
    outline_path = out_dir / f"{stem}-outline.md"
    summary_path.write_text(summary + "\n", encoding="utf-8")
    outline_path.write_text(outline + "\n", encoding="utf-8")

    return {"summary": summary_path, "outline": outline_path}
