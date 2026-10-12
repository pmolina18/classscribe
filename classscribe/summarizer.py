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

# --- Diagram (Mermaid) generation ---------------------------------------

DIAGRAM_SYSTEM = (
    "You are a study assistant that turns lecture transcripts into Mermaid "
    "diagrams. Output ONLY a single Mermaid code block fenced with ```mermaid "
    "and ```; no prose before or after. Be faithful to the transcript and do "
    "not invent facts. Keep node labels short; put labels with special "
    "characters in double quotes."
)

# Prompt per diagram type. "auto" lets the model choose the best fit.
DIAGRAM_PROMPTS = {
    "mindmap": (
        "Build a Mermaid `mindmap` of the key concepts in this transcript and "
        "how they relate, with the lecture's main topic as the root."
    ),
    "timeline": (
        "Build a Mermaid `timeline` of the events/periods mentioned in this "
        "transcript, in chronological order."
    ),
    "flowchart": (
        "Build a Mermaid `flowchart TD` showing the process, argument flow, or "
        "causal relationships described in this transcript."
    ),
    "auto": (
        "Choose the Mermaid diagram type that best represents this transcript "
        "(mindmap for concept-heavy content, timeline for chronological "
        "content, flowchart for processes or causal chains) and build it."
    ),
}
VALID_DIAGRAM_TYPES = tuple(DIAGRAM_PROMPTS.keys())

DIAGRAM_PROMPT = """\
{instruction}

Transcript:
---
{transcript}
---
"""


class SummaryError(RuntimeError):
    pass


def _version() -> str:
    try:
        from . import __version__
        return __version__
    except Exception:
        return "0"


def clean_mermaid(raw: str) -> str | None:
    """Extract a single ```mermaid ...``` block from an LLM response.

    Returns the full fenced block (including the fences), or None if no
    mermaid block could be found. This is intentionally light; richer
    validation/repair is tracked as a separate issue.
    """
    text = raw.strip()
    lower = text.lower()
    start = lower.find("```mermaid")
    if start == -1:
        # Maybe the model emitted a bare block without the language tag.
        if text.startswith("```") and text.rstrip().endswith("```"):
            inner = text.strip("`").strip()
            return f"```mermaid\n{inner}\n```"
        return None
    # Find the closing fence after the opening one.
    end = text.find("```", start + len("```mermaid"))
    if end == -1:
        return None
    inner = text[start + len("```mermaid"):end].strip()
    if not inner:
        return None
    return f"```mermaid\n{inner}\n```"


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
    req.add_header("Accept", "application/json")
    # A real User-Agent is required: the default "Python-urllib/x.y" is often
    # rejected by Cloudflare at the api.groq.com edge with HTTP 403 code 1010.
    req.add_header("User-Agent", f"classscribe/{_version()}")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        if e.code == 403 and "1010" in detail:
            raise SummaryError(
                "LLM endpoint returned a Cloudflare 403 (code 1010): the "
                "request was blocked at the edge, not by your API key. This "
                "usually means a missing/!blocked User-Agent or a network/VPN "
                "that Cloudflare distrusts. Try again, or from another network."
            ) from e
        if e.code == 404 and "model_not_found" in detail:
            raise SummaryError(
                f"The model '{model}' is not available on your account/tier. "
                "Groq rotates models (e.g. llama-3.3-70b-versatile was retired). "
                "Set a current one via [llm] model or by checking "
                "https://console.groq.com/docs/models (e.g. openai/gpt-oss-20b)."
            ) from e
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
    text, stem = _load_transcript(transcript_path, base_url, api_key)
    out_dir.mkdir(parents=True, exist_ok=True)

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


def diagram(
    transcript_path: Path,
    out_dir: Path,
    base_url: str,
    model: str,
    api_key: str | None,
    diagram_type: str = "auto",
) -> dict[str, Path]:
    """Generate <name>-diagram.md (a Mermaid diagram) from a transcript."""
    if diagram_type not in DIAGRAM_PROMPTS:
        raise SummaryError(
            f"invalid diagram type '{diagram_type}'. "
            f"Valid: {', '.join(VALID_DIAGRAM_TYPES)}"
        )
    text, stem = _load_transcript(transcript_path, base_url, api_key)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating diagram ({diagram_type})...")
    raw = _chat(
        base_url, model, api_key or "", DIAGRAM_SYSTEM,
        DIAGRAM_PROMPT.format(
            instruction=DIAGRAM_PROMPTS[diagram_type], transcript=text),
    )
    block = clean_mermaid(raw)
    if block is None:
        # No parseable block; keep the raw output with a warning so the user
        # can fix it rather than losing the result. (Repair is a separate issue.)
        body = (
            "<!-- WARNING: could not detect a valid Mermaid block in the "
            "model output; raw response kept below for manual fixing. -->\n\n"
            + raw
        )
    else:
        body = block

    diagram_path = out_dir / f"{stem}-diagram.md"
    diagram_path.write_text(
        f"# Diagram — {stem}\n\n{body}\n", encoding="utf-8")
    return {"diagram": diagram_path}


def _load_transcript(
    transcript_path: Path, base_url: str, api_key: str | None,
) -> tuple[str, str]:
    """Shared guard: validate inputs and return (transcript_text, stem)."""
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
    return text, transcript_path.stem
