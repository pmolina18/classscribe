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


@dataclass
class Config:
    # Where recordings, transcripts and summaries live.
    workspace: Path = field(default_factory=lambda: Path.home() / "ClassScribe")
    # Whisper language code, e.g. "es", "en". None = auto-detect.
    language: str | None = None
    # Path to the whisper.cpp GGML model.
    model_path: Path | None = None
    model_url: str = DEFAULT_MODEL_URL
    # LLM (summaries). OpenAI-compatible. Groq by default.
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_api_key_env: str = "GROQ_API_KEY"

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

    llm = data.get("llm", {})
    cfg.llm_base_url = llm.get("base_url", cfg.llm_base_url)
    cfg.llm_model = llm.get("model", cfg.llm_model)
    cfg.llm_api_key_env = llm.get("api_key_env", cfg.llm_api_key_env)

    # Environment overrides for the common knobs.
    if os.environ.get("CLASSSCRIBE_WORKSPACE"):
        cfg.workspace = Path(os.environ["CLASSSCRIBE_WORKSPACE"]).expanduser()
    if os.environ.get("CLASSSCRIBE_LANGUAGE"):
        cfg.language = os.environ["CLASSSCRIBE_LANGUAGE"]

    # CLI overrides (highest priority); ignore None values.
    for key, value in overrides.items():
        if value is None:
            continue
        if key == "workspace":
            cfg.workspace = Path(value).expanduser()
        elif hasattr(cfg, key):
            setattr(cfg, key, value)

    return cfg
