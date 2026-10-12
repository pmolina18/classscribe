"""Configuration for ClassScribe.

Resolves settings from (in order of priority):
  1. CLI flags
  2. Environment variables
  3. A `.classscribe.toml` file in the working directory or home
  4. Built-in defaults

Nothing here is specific to any one user, course, or language.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILENAMES = (".classscribe.toml", "classscribe.toml")

DEFAULT_MODEL_FILE = "ggml-large-v3-turbo.bin"
DEFAULT_MODEL_URL = (
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"
    "ggml-large-v3-turbo.bin"
)

# Groq free-tier default. Swap via config/env for any OpenAI-compatible endpoint.
DEFAULT_LLM_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_LLM_MODEL = "llama-3.3-70b-versatile"

# Transcription provider default. "groq" works without a local GPU/model;
# "local" uses whisper.cpp fully offline. Default is cloud so the tool works
# for users who cannot run models locally.
DEFAULT_TRANSCRIPTION_PROVIDER = "groq"
VALID_TRANSCRIPTION_PROVIDERS = ("groq", "local")
DEFAULT_GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"

# Keep in sync with summarizer.VALID_DIAGRAM_TYPES.
VALID_DIAGRAM_TYPES = ("mindmap", "timeline", "flowchart", "auto")


@dataclass
class Config:
    # Where recordings, transcripts and summaries live.
    workspace: Path = field(default_factory=lambda: Path.home() / "ClassScribe")
    # Whisper language code, e.g. "es", "en". None = auto-detect.
    language: str | None = None
    # Transcription provider: "groq" (cloud, default) or "local" (whisper.cpp).
    transcription_provider: str = DEFAULT_TRANSCRIPTION_PROVIDER
    # Groq (cloud) transcription model.
    groq_whisper_model: str = DEFAULT_GROQ_WHISPER_MODEL
    # Path to the whisper.cpp GGML model (used only by the "local" provider).
    model_path: Path | None = None
    model_url: str = DEFAULT_MODEL_URL
    # LLM (summaries). OpenAI-compatible. Groq by default.
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_api_key_env: str = "GROQ_API_KEY"
    # Mermaid diagram type: mindmap | timeline | flowchart | auto.
    diagram_type: str = "auto"

    @property
    def recordings_dir(self) -> Path:
        return self.workspace / "recordings"

    @property
    def transcripts_dir(self) -> Path:
        return self.workspace / "transcripts"

    @property
    def summaries_dir(self) -> Path:
        return self.workspace / "summaries"

    @property
    def models_dir(self) -> Path:
        return self.workspace / "models"

    def resolved_model_path(self) -> Path:
        if self.model_path is not None:
            return self.model_path
        return self.models_dir / DEFAULT_MODEL_FILE

    def llm_api_key(self) -> str | None:
        return os.environ.get(self.llm_api_key_env)

    def validate(self) -> None:
        if self.transcription_provider not in VALID_TRANSCRIPTION_PROVIDERS:
            raise ValueError(
                f"invalid transcription_provider "
                f"'{self.transcription_provider}'. "
                f"Valid: {', '.join(VALID_TRANSCRIPTION_PROVIDERS)}"
            )
        if self.diagram_type not in VALID_DIAGRAM_TYPES:
            raise ValueError(
                f"invalid diagram_type '{self.diagram_type}'. "
                f"Valid: {', '.join(VALID_DIAGRAM_TYPES)}"
            )

    def effective(self) -> dict:
        """Human-readable snapshot of the resolved config (secrets redacted)."""
        key = self.llm_api_key()
        return {
            "workspace": str(self.workspace),
            "language": self.language or "(auto-detect)",
            "transcription_provider": self.transcription_provider,
            "groq_whisper_model": self.groq_whisper_model,
            "local_model_path": str(self.resolved_model_path()),
            "llm_base_url": self.llm_base_url,
            "llm_model": self.llm_model,
            "llm_api_key_env": self.llm_api_key_env,
            "llm_api_key_set": "yes" if key else "no",
            "diagram_type": self.diagram_type,
            "recordings_dir": str(self.recordings_dir),
            "transcripts_dir": str(self.transcripts_dir),
            "summaries_dir": str(self.summaries_dir),
        }

    def ensure_dirs(self) -> None:
        for d in (
            self.recordings_dir,
            self.transcripts_dir,
            self.summaries_dir,
            self.models_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


def _load_toml() -> dict:
    search = [Path.cwd()] + list(Path.cwd().parents) + [Path.home()]
    for base in search:
        for name in CONFIG_FILENAMES:
            candidate = base / name
            if candidate.is_file():
                with candidate.open("rb") as fh:
                    return tomllib.load(fh)
    return {}


def load_config(**overrides) -> Config:
    """Build a Config from file + env + overrides (CLI flags win)."""
    data = _load_toml()
    cfg = Config()

    if "workspace" in data:
        cfg.workspace = Path(data["workspace"]).expanduser()
    if "language" in data:
        cfg.language = data["language"] or None
    if "model_path" in data:
        cfg.model_path = Path(data["model_path"]).expanduser()
    if "model_url" in data:
        cfg.model_url = data["model_url"]

    transcription = data.get("transcription", {})
    cfg.transcription_provider = transcription.get(
        "provider", cfg.transcription_provider)
    cfg.groq_whisper_model = transcription.get(
        "groq_model", cfg.groq_whisper_model)

    llm = data.get("llm", {})
    cfg.llm_base_url = llm.get("base_url", cfg.llm_base_url)
    cfg.llm_model = llm.get("model", cfg.llm_model)
    cfg.llm_api_key_env = llm.get("api_key_env", cfg.llm_api_key_env)

    diagrams = data.get("diagrams", {})
    cfg.diagram_type = diagrams.get("type", cfg.diagram_type)

    # Environment overrides for the common knobs.
    if os.environ.get("CLASSSCRIBE_WORKSPACE"):
        cfg.workspace = Path(os.environ["CLASSSCRIBE_WORKSPACE"]).expanduser()
    if os.environ.get("CLASSSCRIBE_LANGUAGE"):
        cfg.language = os.environ["CLASSSCRIBE_LANGUAGE"]
    if os.environ.get("CLASSSCRIBE_TRANSCRIPTION_PROVIDER"):
        cfg.transcription_provider = os.environ[
            "CLASSSCRIBE_TRANSCRIPTION_PROVIDER"]
    if os.environ.get("CLASSSCRIBE_DIAGRAM_TYPE"):
        cfg.diagram_type = os.environ["CLASSSCRIBE_DIAGRAM_TYPE"]

    # CLI overrides (highest priority); ignore None values.
    for key, value in overrides.items():
        if value is None:
            continue
        if key == "workspace":
            cfg.workspace = Path(value).expanduser()
        elif hasattr(cfg, key):
            setattr(cfg, key, value)

    cfg.validate()
    return cfg
