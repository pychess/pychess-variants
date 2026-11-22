"""Ensure new and edited blog posts apply the same image validation."""

from pathlib import Path


def test_create_and_update_validate_cover_urls():
    source = (Path(__file__).resolve().parents[1] / "server/views/ublog.py").read_text()
    assert source.count("errors = _validate_full(values)") >= 2
