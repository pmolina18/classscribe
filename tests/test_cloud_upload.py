"""Tests for the Groq upload path that need no network and no real ffmpeg."""
from __future__ import annotations

import subprocess

import pytest

from classscribe import cloud_transcriber as ct
from classscribe.transcriber import TranscribeError


def test_compress_uses_mono_aac(monkeypatch, tmp_path):
    src = tmp_path / "lecture.wav"
    src.write_bytes(b"RIFF" + b"\0" * 100)
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        # Simulate ffmpeg writing the output file (last argument).
        with open(cmd[-1], "wb") as fh:
            fh.write(b"aac-data")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(ct.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(ct.subprocess, "run", fake_run)

    out = ct._compress_for_upload(src, tmp_path)

    assert out.suffix == ".m4a"
    assert out.read_bytes() == b"aac-data"
    cmd = seen["cmd"]
    assert cmd[cmd.index("-c:a") + 1] == "aac"
    assert cmd[cmd.index("-ac") + 1] == "1"
    assert cmd[cmd.index("-b:a") + 1] == ct.UPLOAD_BITRATE


def test_compress_falls_back_without_ffmpeg(monkeypatch, tmp_path):
    src = tmp_path / "lecture.wav"
    src.write_bytes(b"x")
    monkeypatch.setattr(ct.shutil, "which", lambda _: None)
    assert ct._compress_for_upload(src, tmp_path) == src


def test_compress_falls_back_on_ffmpeg_failure(monkeypatch, tmp_path):
    src = tmp_path / "lecture.wav"
    src.write_bytes(b"x")
    monkeypatch.setattr(ct.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        ct.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "boom"),
    )
    assert ct._compress_for_upload(src, tmp_path) == src


def test_size_limit_checked_after_compression(monkeypatch, tmp_path):
    src = tmp_path / "lecture.wav"
    src.write_bytes(b"0123456789")
    monkeypatch.setattr(ct, "_compress_for_upload", lambda s, d: s)
    monkeypatch.setattr(ct, "GROQ_MAX_FILE_BYTES", 4)

    with pytest.raises(TranscribeError, match="100 MB limit"):
        ct.transcribe_groq(
            src, tmp_path / "out" / "lecture",
            "https://example.invalid/v1", "whisper-large-v3-turbo", "key",
        )


def test_m4a_mime_override(tmp_path):
    f = tmp_path / "a.m4a"
    f.write_bytes(b"x")
    body, _ = ct._multipart_body(f, {"model": "m"})
    assert b"Content-Type: audio/mp4" in body
