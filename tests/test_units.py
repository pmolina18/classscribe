"""Unit tests for ClassScribe's pure logic (no network, no audio)."""
from __future__ import annotations

import pytest

from classscribe.config import VALID_DIAGRAM_TYPES, Config, load_config
from classscribe.recorder import RecordError, parse_duration
from classscribe.summarizer import VALID_DIAGRAM_TYPES as SUMM_TYPES
from classscribe.summarizer import clean_mermaid


# --- parse_duration ------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("90", 90),
    (90, 90),
    ("20s", 20),
    ("5m", 300),
    ("1h30m", 5400),
    ("45:00", 2700),
    ("1:30:00", 5400),
    ("0:45", 45),
    ("2h", 7200),
    (None, None),
    ("", None),
])
def test_parse_duration_valid(value, expected):
    assert parse_duration(value) == expected


@pytest.mark.parametrize("value", ["abc", "0", "00:00", "5x", "1:2:3:4", "-5"])
def test_parse_duration_invalid(value):
    with pytest.raises(RecordError):
        parse_duration(value)


# --- clean_mermaid -------------------------------------------------------

def test_clean_mermaid_extracts_block():
    raw = "Sure:\n```mermaid\nmindmap\n  root((X))\n```\nhope it helps"
    assert clean_mermaid(raw) == "```mermaid\nmindmap\n  root((X))\n```"


def test_clean_mermaid_none_when_absent():
    assert clean_mermaid("sorry, no diagram here") is None


def test_clean_mermaid_bare_block():
    raw = "```\nflowchart TD\n  A-->B\n```"
    out = clean_mermaid(raw)
    assert out is not None and out.startswith("```mermaid")


# --- config --------------------------------------------------------------

def test_default_provider_is_groq():
    assert Config().transcription_provider == "groq"


def test_cli_override_wins(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no config file in an empty dir
    cfg = load_config(transcription_provider="local")
    assert cfg.transcription_provider == "local"


def test_invalid_provider_rejected(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        load_config(transcription_provider="bogus")


def test_diagram_types_in_sync():
    assert VALID_DIAGRAM_TYPES == SUMM_TYPES
