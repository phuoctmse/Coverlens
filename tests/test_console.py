"""Printing reports must not crash on characters the console cannot encode."""

import io
import sys

import pytest

from coverlens.cli import safe_stdout


def test_unencodable_characters_are_replaced_not_fatal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    safe_stdout()
    print("50 000 USD")  # narrow no-break space, not in cp1252
    sys.stdout.flush()
    assert b"50?000 USD" in raw.getvalue()


def test_safe_stdout_tolerates_streams_without_reconfigure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    safe_stdout()  # no error
